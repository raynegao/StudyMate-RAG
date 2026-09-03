from __future__ import annotations

import json
import stat
from pathlib import Path

from scripts.run_docker_e2e import prepare_bind_directory

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
