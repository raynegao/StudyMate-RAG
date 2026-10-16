from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import httpx
from openai import OpenAI
import pytest

from app.core.config import settings
from app.core.errors import EmbeddingInputTooLongError, LLMTimeoutError
from app.services.chunking import split_pages_into_chunks
from app.services.pdf_parser import PageText
from app.services.vector_store import RetrievedChunk

ROOT = Path(__file__).resolve().parents[1]


def chunk(distance=0.2):
    return RetrievedChunk("audit:p1:c0", "a" * 32, "public.pdf", 1, 0, "令牌有效期为三天。", distance)


def test_frontend_launcher_applies_upload_override_to_streamlit_server(tmp_path):
    # Exercise the actual launcher, including its Python-version preflight.
    fake_python = tmp_path / "python"
    fake_python.write_text(
        f"#!{Path(sys.executable).resolve()}\nimport json,sys\nif '-m' in sys.argv: print(json.dumps(sys.argv[1:]))\n"
    )
    fake_python.chmod(0o755)
    run = subprocess.run(
        ["bash", "scripts/run_frontend.sh"], cwd=ROOT, check=True, capture_output=True, text=True,
        env={**os.environ, "PYTHON_BIN": str(fake_python), "STUDYMATE_MAX_UPLOAD_SIZE_MB": "70"},
    )
    argv = json.loads(run.stdout)
    assert argv[argv.index("--server.maxUploadSize") + 1] == "70"


def test_course_profile_is_repeatable_local_only_and_separate():
    run = subprocess.run(
        ["bash", "scripts/run_real_course.sh", "--print-config"], cwd=ROOT,
        check=True, capture_output=True, text=True,
        env={**os.environ, "STUDYMATE_COURSE_MODE": "retrieval_only", "STUDYMATE_CHAT_MODE": "generation", "DEEPSEEK_API_KEY": "placeholder"},
    )
    config = json.loads(run.stdout)
    assert config["chat_mode"] == "retrieval_only"
    assert config["max_upload_size_mb"] == 70
    assert config["upload_profile"] == config["chroma_profile"] == "real-course-v2"
    assert "placeholder" not in run.stdout


def test_course_all_launcher_prints_url_and_cleans_up(tmp_path):
    fake_python = tmp_path / "python"
    fake_python.write_text(f"#!{Path(sys.executable).resolve()}\n# Exit immediately instead of starting servers or touching data.\n")
    fake_python.chmod(0o755)
    run = subprocess.run(
        ["bash", "scripts/run_real_course.sh", "all"], cwd=ROOT,
        capture_output=True, text=True, timeout=15,
        # The placeholder key satisfies the launcher's preflight on machines without
        # .env.local (such as CI); the fake interpreter exits before any request is made.
        env={**os.environ, "PYTHON_BIN": str(fake_python), "STUDYMATE_COURSE_FRONTEND_PORT": "18502",
             "DEEPSEEK_API_KEY": "placeholder"},
    )
    assert run.returncode == 1  # A stopped child causes the launcher to exit.
    assert "placeholder" not in run.stdout
    assert "http://127.0.0.1:18502（Ctrl+C" in run.stdout
    assert "unbound variable" not in run.stderr


def test_runtime_config_exposes_no_storage_paths_or_credentials(client, monkeypatch):
    from app.api import health
    monkeypatch.setattr(health, "settings", replace(settings, knowledge_base_name="测试库", max_upload_size_mb=70, llm_timeout_seconds=80,
                                                         summary_concurrency=4))
    data = client.get("/api/config").json()
    assert data == {
        "knowledge_base_name": "测试库", "max_upload_size_mb": 70,
        "chat_mode": "generation", "default_top_k": settings.default_top_k,
        "llm_provider": settings.llm_provider,
        "chat_request_timeout_seconds": 110,
        # Two rounds of four section calls plus one synthesis call: 3 x 80 + 60.
        "summary_request_timeout_seconds": 300,
    }


@pytest.mark.parametrize("provider,key_env", [("deepseek", "DEEPSEEK_API_KEY"), ("gemini", "GEMINI_API_KEY")])
def test_course_launcher_checks_the_selected_provider_key(tmp_path, provider, key_env):
    fake_python = tmp_path / "python"
    fake_python.write_text(f"#!{Path(sys.executable).resolve()}\n# Exit immediately; never prepares or serves data.\n")
    fake_python.chmod(0o755)
    base_env = {k: v for k, v in os.environ.items() if k not in ("DEEPSEEK_API_KEY", "GEMINI_API_KEY")}
    env = {**base_env, "STUDYMATE_ENV_FILE": str(tmp_path / "missing.env"),
           "STUDYMATE_COURSE_MODE": "generation", "STUDYMATE_LLM_PROVIDER": provider}
    # In generation mode the key preflight runs before any Python or data access; the fake
    # interpreter guarantees nothing is prepared or served even if that ever changed.
    missing = subprocess.run(["bash", "scripts/run_real_course.sh", "all"], cwd=ROOT, capture_output=True,
                             text=True, env={**env, "PYTHON_BIN": str(fake_python)}, timeout=15)
    assert missing.returncode == 1 and key_env in missing.stderr
    assert missing.stdout == ""  # Stopped at the preflight, not after launching servers.
    configured = subprocess.run(["bash", "scripts/run_real_course.sh", "--print-config"], cwd=ROOT,
                                check=True, capture_output=True, text=True, env={**env, key_env: "placeholder"})
    config = json.loads(configured.stdout)
    assert (config["llm_provider"], config["llm_configured"]) == (provider, True)
    assert "placeholder" not in configured.stdout
    local = subprocess.run(["bash", "scripts/run_real_course.sh", "--print-config"], cwd=ROOT, check=True,
                           capture_output=True, text=True,
                           env={**env, key_env: "placeholder", "STUDYMATE_COURSE_MODE": "retrieval_only"})
    assert json.loads(local.stdout)["llm_configured"] is False


def test_token_budget_preserves_tail_and_sentences():
    text = "开头介绍。" + "课程概念。" * 160 + "尾部答案为九十天。"
    chunks = split_pages_into_chunks(
        [PageText(9, text)], document_id="a"*32, filename="public.pdf",
        chunk_size=1000, chunk_overlap=60, token_count=lambda t: len(t)+2,
        max_tokens=128, sentence_boundaries=True,
    )
    assert len(chunks) > 1
    assert all(len(c.text)+2 <= 128 and c.page_number == 9 for c in chunks)
    assert chunks[-1].text.endswith("尾部答案为九十天。")
    assert all(c.text.endswith("。") for c in chunks)


def test_encoder_refuses_silent_truncation(monkeypatch):
    from app.services import embedding_service

    class Model:
        max_seq_length = 8

        def tokenizer(self, texts, **kwargs):
            return {"length": [len(t)+2 for t in texts]}

        def encode(self, *args, **kwargs):
            pytest.fail("oversized input must not reach encode")

    monkeypatch.setattr(embedding_service, "_get_embedding_model", lambda: Model())
    with pytest.raises(EmbeddingInputTooLongError):
        embedding_service.embed_texts(["长" * 9])


def test_overlong_query_returns_actionable_422(client, monkeypatch):
    from app.services import rag_service
    monkeypatch.setattr(rag_service, "has_documents", lambda: True)

    def reject(texts):
        raise EmbeddingInputTooLongError("private encoder diagnostics")

    monkeypatch.setattr(rag_service, "embed_texts", reject)
    response = client.post("/api/chat", json={"question": "长" * 600})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "embedding_input_too_long"
    assert "private encoder" not in response.text


def test_provider_timeout_is_bounded_and_not_retried(monkeypatch):
    from app.services import llm_service
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("test timeout", request=request)

    with OpenAI(
        api_key="placeholder", base_url="https://example.invalid", max_retries=0,
        timeout=httpx.Timeout(30, connect=5), http_client=httpx.Client(transport=httpx.MockTransport(timeout)),
    ) as provider:
        monkeypatch.setattr(llm_service, "_get_llm_client", lambda: provider)
        with pytest.raises(LLMTimeoutError):
            llm_service.complete_answer("虚构问题")
    assert len(calls) == 1
    assert calls[0].extensions["timeout"]["read"] == 30


def test_actual_sdk_client_config_and_reuse():
    from app.services.llm_service import _cached_client
    client = _cached_client("placeholder", "https://example.invalid", 17)
    assert client.timeout.read == 17
    assert client.timeout.connect == 5
    assert client.max_retries == 0
    assert client is _cached_client("placeholder", "https://example.invalid", 17)
    client.close()
    _cached_client.cache_clear()


def test_timeout_has_distinct_api_status(client, monkeypatch):
    def fail(*args):
        raise LLMTimeoutError("private provider URL")
    monkeypatch.setattr("app.services.rag_service.answer_question", fail)
    response = client.post("/api/chat", json={"question": "虚构问题"})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "llm_timeout"
    assert "private provider" not in response.text


@pytest.mark.parametrize("answer", ["未给出引用的断言", "三天 [S99]", "三天 [S1] [S0]", "资料中没有足够信息，无法回答。"])
def test_unsupported_or_invalid_citations_do_not_claim_answered(monkeypatch, answer):
    from app.services import rag_service
    monkeypatch.setattr(rag_service, "complete_answer", lambda prompt: answer)
    response = rag_service.answer_from_chunks("有效期？", [chunk()])
    assert response["status"] == "insufficient_evidence"
    assert not any(s["cited"] for s in response["sources"])


def test_low_relevance_skips_generation(monkeypatch):
    from app.services import rag_service
    monkeypatch.setattr(rag_service, "complete_answer", lambda prompt: pytest.fail("irrelevant context sent to LLM"))
    response = rag_service.answer_from_chunks("资料外问题", [chunk(1.8)])
    assert response["status"] == "insufficient_evidence"
    assert response["sources"] == []


def test_private_profile_never_generates_even_with_relevant_context(monkeypatch):
    from app.services import rag_service
    monkeypatch.setattr(rag_service, "settings", replace(settings, chat_mode="retrieval_only"))
    monkeypatch.setattr(rag_service, "complete_answer", lambda prompt: pytest.fail("private content sent to LLM"))
    response = rag_service.answer_from_chunks("有效期？", [chunk()])
    assert response["status"] == "retrieval_only"
    assert response["sources"][0]["text"] == "令牌有效期为三天。"
    assert response["sources"][0]["cited"] is False


def test_alternative_pages_do_not_inflate_original_page_metric():
    from scripts.evaluate_rag import evaluate_retrieval
    q = {"id":"case", "gold_document":"public.pdf", "gold_page":2, "accepted_pages":[1,2]}
    metrics = evaluate_retrieval([q], {"case":[(chunk(),0.8)]}, top_k=1, retrieval_latencies_ms=[1])
    assert metrics["recall_at_k"] == 1
    assert metrics["strict_original_page_recall_at_k"] == 0


def test_minimum_answer_rubric_preserves_original_keyword_metric(monkeypatch):
    from scripts import evaluate_rag
    monkeypatch.setattr(evaluate_rag, "settings", replace(settings, deepseek_api_key="placeholder"))
    monkeypatch.setattr(evaluate_rag, "answer_from_chunks", lambda question, chunks: {
        "answer": "8.4 GHz [S1]", "status": "answered", "sources": [{"chunk_id": chunk().chunk_id}],
    })
    question = {
        "id": "case", "question": "使用哪个频段？", "gold_document": "public.pdf", "gold_page": 1,
        "answer_keywords": ["8.4 GHz", "状态摘要"], "answer_required_keywords": ["8.4 GHz"],
    }
    result = evaluate_rag.evaluate_answers([question], {"case": [(chunk(), 0.8)]})
    assert result["answer_accuracy"] == 1
    assert result["original_keyword_accuracy"] == 0
    assert result["citation_accuracy"] == 1


def test_public_answerability_set_has_both_kinds_and_fixed_held_out_split():
    data = json.loads((ROOT / "evaluation/answerability_benchmark.json").read_text())
    cases = data["questions"]
    assert len({q["id"] for q in cases}) == len(cases) == 18
    held_out = [q for q in cases if q["split"] == "held_out"]
    assert sum(q["kind"] == "answerable" for q in held_out) == 6
    assert sum(q["kind"] == "out_of_domain" for q in held_out) == 3
    assert sum(q["kind"] == "missing_fact" for q in held_out) == 3


def test_settings_read_environment_at_construction(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("STUDYMATE_TOP_K", "3")
    monkeypatch.setenv("STUDYMATE_CHAT_MODE", "retrieval_only")
    monkeypatch.setenv("STUDYMATE_LOG_LEVEL", "debug")
    fresh = Settings()
    assert (fresh.default_top_k, fresh.chat_mode, fresh.log_level) == (3, "retrieval_only", "DEBUG")
    assert settings.default_top_k == 6
    monkeypatch.setenv("STUDYMATE_CHAT_MODE", "bogus")
    with pytest.raises(ValueError):
        Settings()


def test_summary_budget_follows_concurrency_rounds():
    from app.core.config import Settings

    base = replace(settings, llm_timeout_seconds=30)
    assert replace(base, summary_concurrency=1).summary_request_timeout_seconds == 330
    assert replace(base, summary_concurrency=4).summary_request_timeout_seconds == 150
    assert replace(base, summary_concurrency=8).summary_request_timeout_seconds == 120
    for invalid in ("0", "9"):
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("STUDYMATE_SUMMARY_CONCURRENCY", invalid)
            with pytest.raises(ValueError):
                Settings()
