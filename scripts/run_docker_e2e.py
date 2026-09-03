#!/usr/bin/env python3
"""Run an isolated real-stack Docker E2E check with the public demo PDF."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT_DIR / ".env.local"
DEMO_PDF = ROOT_DIR / "output" / "pdf" / "studymate-demo-course.pdf"
RESULT_PATH = ROOT_DIR / "output" / "e2e" / "docker-e2e-result.json"


def free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def wait_for_health(url: str, *, timeout_seconds: float = 240) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            try:
                return response.json()
            except ValueError:
                return {"status": response.text.strip()}
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def request_json(method: str, url: str, **kwargs) -> dict[str, Any]:
    response = requests.request(method, url, timeout=kwargs.pop("timeout", 360), **kwargs)
    if not response.ok:
        detail = response.text.strip().replace("\n", " ")[:1000]
        raise RuntimeError(
            f"{method} {url} returned HTTP {response.status_code}: {detail}"
        )
    return response.json()


def compose_command(env_file: Path | None, project_name: str) -> list[str]:
    command = ["docker", "compose"]
    if env_file is not None:
        command.extend(["--env-file", str(env_file)])
    command.extend(["-p", project_name])
    return command


def prepare_bind_directory(path: Path) -> None:
    path.mkdir()
    path.chmod(0o777)


def make_bind_mounts_removable(
    compose: list[str], *, compose_env: dict[str, str]
) -> None:
    """Restore host-runner access to files written by container UID 10001."""
    subprocess.run(
        [
            *compose,
            "run",
            "--rm",
            "--no-deps",
            "--user",
            "0",
            "backend",
            "sh",
            "-c",
            "chmod -R a+rwX /app/data/uploads /app/data/chroma_db",
        ],
        cwd=ROOT_DIR,
        env=compose_env,
        check=False,
    )


def run_e2e(*, env_file: Path | None, output_path: Path) -> dict[str, Any]:
    if not DEMO_PDF.exists():
        raise FileNotFoundError(f"Missing public demo PDF: {DEMO_PDF}")
    if env_file is not None and not env_file.exists():
        raise FileNotFoundError(f"Environment file does not exist: {env_file}")
    if env_file is None and not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("Provide --env-file or set DEEPSEEK_API_KEY.")

    backend_port = free_port()
    frontend_port = free_port()
    project_name = f"studymate-e2e-{uuid4().hex[:8]}"
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="studymate-e2e-") as temp_dir:
        temp_path = Path(temp_dir)
        upload_dir = temp_path / "uploads"
        chroma_dir = temp_path / "chroma"
        # Linux bind mounts preserve host permissions. The production container
        # runs as UID 10001, so isolated runner directories must be writable by
        # that non-root user. The parent directory is temporary and removed at exit.
        prepare_bind_directory(upload_dir)
        prepare_bind_directory(chroma_dir)
        compose_env = os.environ.copy()
        compose_env.update(
            {
                "STUDYMATE_BACKEND_PUBLISHED_PORT": str(backend_port),
                "STUDYMATE_FRONTEND_PUBLISHED_PORT": str(frontend_port),
                "STUDYMATE_HOST_UPLOAD_DIR": str(upload_dir),
                "STUDYMATE_HOST_CHROMA_DIR": str(chroma_dir),
                "STUDYMATE_HF_CACHE_VOLUME": "studymate_hf_cache",
            }
        )
        compose = compose_command(env_file, project_name)
        backend_url = f"http://127.0.0.1:{backend_port}"
        frontend_url = f"http://127.0.0.1:{frontend_port}"

        try:
            subprocess.run(
                [*compose, "up", "--build", "--detach"],
                cwd=ROOT_DIR,
                env=compose_env,
                check=True,
            )
            backend_health = wait_for_health(f"{backend_url}/health")
            frontend_health = wait_for_health(f"{frontend_url}/_stcore/health")

            with DEMO_PDF.open("rb") as file:
                upload = request_json(
                    "POST",
                    f"{backend_url}/api/upload",
                    files={"file": ("星际导航课程讲义.pdf", file, "application/pdf")},
                )
            document_id = upload["document_id"]
            before_restart = request_json("GET", f"{backend_url}/api/documents")
            chat = request_json(
                "POST",
                f"{backend_url}/api/chat",
                json={
                    "question": "蓝色令牌的有效期是多少？它有什么用途？",
                    "top_k": 4,
                },
            )
            if "三个星港周期" not in chat["answer"] or "双重校验" not in chat["answer"]:
                raise AssertionError("DeepSeek answer is missing expected public-demo facts.")
            cited_sources = [source for source in chat["sources"] if source["cited"]]
            if not cited_sources:
                raise AssertionError("DeepSeek answer did not include a valid citation.")

            subprocess.run(
                [*compose, "restart", "backend"],
                cwd=ROOT_DIR,
                env=compose_env,
                check=True,
            )
            wait_for_health(f"{backend_url}/health")
            after_restart = request_json("GET", f"{backend_url}/api/documents")
            persisted_ids = {
                document["document_id"] for document in after_restart["documents"]
            }
            if document_id not in persisted_ids:
                raise AssertionError("Document or Chroma index did not survive restart.")

            deletion = request_json(
                "DELETE",
                f"{backend_url}/api/documents/{document_id}",
            )
            after_delete = request_json("GET", f"{backend_url}/api/documents")
            if any(
                document["document_id"] == document_id
                for document in after_delete["documents"]
            ):
                raise AssertionError("Document remained after E2E cleanup request.")

            result = {
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "environment": "isolated Docker Compose project with real BGE, ChromaDB and DeepSeek",
                "public_fixture": str(DEMO_PDF.relative_to(ROOT_DIR)),
                "backend_health": backend_health,
                "frontend_health": frontend_health,
                "upload": {
                    "filename": upload["filename"],
                    "chunk_count": upload["chunk_count"],
                },
                "deepseek_answer_correct": True,
                "cited_source_count": len(cited_sources),
                "listed_before_restart": any(
                    document["document_id"] == document_id
                    for document in before_restart["documents"]
                ),
                "persistence_after_backend_restart": True,
                "delete_status": deletion["status"],
                "isolated_cleanup_verified": True,
                "duration_seconds": time.perf_counter() - started,
            }
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return result
        except Exception:
            subprocess.run(
                [*compose, "ps"],
                cwd=ROOT_DIR,
                env=compose_env,
                check=False,
            )
            subprocess.run(
                [*compose, "logs", "--no-color", "backend", "frontend"],
                cwd=ROOT_DIR,
                env=compose_env,
                check=False,
            )
            raise
        finally:
            # Stop writers first, then use the already-built backend image as root
            # to make nested bind-mount files removable by a non-root CI runner.
            subprocess.run(
                [*compose, "stop"],
                cwd=ROOT_DIR,
                env=compose_env,
                check=False,
            )
            make_bind_mounts_removable(compose, compose_env=compose_env)
            subprocess.run(
                [*compose, "down", "--remove-orphans"],
                cwd=ROOT_DIR,
                env=compose_env,
                check=False,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE if DEFAULT_ENV_FILE.exists() else None,
        help="Compose environment file. Omit when DEEPSEEK_API_KEY is exported.",
    )
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_e2e(env_file=args.env_file, output_path=args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
