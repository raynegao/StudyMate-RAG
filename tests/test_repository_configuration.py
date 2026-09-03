from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_compose_publishes_services_on_loopback_by_default():
    compose = (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    assert (
        '"${STUDYMATE_PUBLISHED_HOST:-127.0.0.1}:'
        '${STUDYMATE_BACKEND_PUBLISHED_PORT:-8000}:8000"' in compose
    )
    assert (
        '"${STUDYMATE_PUBLISHED_HOST:-127.0.0.1}:'
        '${STUDYMATE_FRONTEND_PUBLISHED_PORT:-8501}:8501"' in compose
    )


def test_dependabot_covers_python_docker_and_github_actions():
    dependabot = (ROOT_DIR / ".github" / "dependabot.yml").read_text(
        encoding="utf-8"
    )

    assert "package-ecosystem: pip" in dependabot
    assert "package-ecosystem: docker" in dependabot
    assert "package-ecosystem: github-actions" in dependabot


def test_dependabot_pip_compile_keeps_cpu_torch_and_unsafe_runtime_dependency():
    requirements = (ROOT_DIR / "backend" / "requirements.in").read_text(
        encoding="utf-8"
    )
    pip_tools = (ROOT_DIR / "backend" / ".pip-tools.toml").read_text(
        encoding="utf-8"
    )

    assert "--find-links https://download.pytorch.org/whl/cpu/torch/" in requirements
    assert "setuptools==83.0.0" in requirements
    assert pip_tools.count("allow-unsafe = true") == 2
