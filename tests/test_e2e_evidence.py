from __future__ import annotations

import json
import stat
from pathlib import Path

from scripts.run_docker_e2e import make_bind_mounts_removable, prepare_bind_directory

RESULT_PATH = Path("output/e2e/docker-e2e-result.json")


def test_committed_real_stack_evidence_is_complete():
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    assert result["backend_health"]["status"] == "ok"
    assert result["frontend_health"]["status"] == "ok"
    assert result["upload"]["chunk_count"] > 0
    assert result["deepseek_answer_correct"] is True
    assert result["cited_source_count"] > 0
    assert result["listed_before_restart"] is True
    assert result["persistence_after_backend_restart"] is True
    assert result["delete_status"] == "deleted"
    assert result["isolated_cleanup_verified"] is True


def test_e2e_bind_directory_is_writable_by_non_root_container(tmp_path):
    bind_dir = tmp_path / "bind"

    prepare_bind_directory(bind_dir)

    assert stat.S_IMODE(bind_dir.stat().st_mode) == 0o777


def test_e2e_cleanup_uses_root_container_for_nested_bind_files(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr("scripts.run_docker_e2e.subprocess.run", fake_run)

    make_bind_mounts_removable(
        ["docker", "compose", "-p", "isolated-test"],
        compose_env={"STUDYMATE_HOST_UPLOAD_DIR": "/tmp/uploads"},
    )

    command, kwargs = calls[0]
    assert command[:5] == ["docker", "compose", "-p", "isolated-test", "run"]
    assert "--user" in command
    assert command[command.index("--user") + 1] == "0"
    assert command[-1] == "chmod -R a+rwX /app/data/uploads /app/data/chroma_db"
    assert kwargs["check"] is False
