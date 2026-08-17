from __future__ import annotations

import json
from pathlib import Path

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
