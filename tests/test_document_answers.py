from __future__ import annotations

from dataclasses import replace
import json
import os
import subprocess
from types import SimpleNamespace

import chromadb
import pytest
from streamlit.testing.v1 import AppTest

from app.core.config import settings
from app.core.errors import DocumentNotFoundError, LLMOutputLimitError, SummaryCitationError, SummaryTooLargeError
from app.services import llm_service, rag_service, summary_service, vector_store
from app.services.vector_store import RetrievedChunk
from frontend import streamlit_app

DOC_A, DOC_B = "a" * 32, "b" * 32


def source(index=0, text="这是公开虚构资料。", document_id=DOC_A):
    return RetrievedChunk(f"{document_id}:p{index+1}:c0", document_id, "public.pdf", index+1, 0, text)


@pytest.mark.parametrize("question", ["这份资料的核心概念是什么？", "总结主要内容", "文档概览", "Summarize this document",
                                      "请概括这份资料的主要内容。", "概括"])
def test_auto_overview_routing(question, monkeypatch):
    monkeypatch.setattr(summary_service, "summarize_document", lambda doc, q: {"doc": doc, "question": q})
    monkeypatch.setattr(rag_service, "embed_texts", lambda texts: pytest.fail("overview must not use similarity retrieval"))
    assert rag_service.answer_question(question, document_id=DOC_A)["doc"] == DOC_A


@pytest.mark.parametrize("question", ["总结第三章的公式", "概括一下能量守恒定律", "主要内容里提到的三种学习方法是什么",
                                      "Summarize the chapter on recursion", "这份资料的核心概念和第二章有什么关系"])
def test_targeted_questions_keep_similarity_retrieval(question, monkeypatch):
    monkeypatch.setattr(summary_service, "summarize_document", lambda doc, q: pytest.fail("targeted question must not summarize"))
    monkeypatch.setattr(rag_service, "has_documents", lambda: True)
    monkeypatch.setattr(rag_service, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(rag_service, "query_chunks", lambda vector, k, doc: [source()])
    monkeypatch.setattr(rag_service, "answer_from_chunks", lambda q, chunks: {"routed": "question"})
    assert rag_service.answer_question(question, document_id=DOC_A) == {"routed": "question"}


def test_overview_requires_document_and_validates_api_id(client):
    assert client.post("/api/chat", json={"question": "概括这份资料"}).status_code == 400
    for bad_id in ["../private", "*", "g" * 32]:
        assert client.post("/api/chat", json={"question": "概括", "document_id": bad_id}).status_code == 422


def test_scoped_api_passes_selected_id_and_summary_metadata(client, monkeypatch):
    def respond(q, k, doc, mode):
        assert (doc, mode) == (DOC_A, "summary")
        return {"answer": "公开摘要 [S1]", "status": "answered", "sources": [], "metadata": {"chunks_covered": 30}}
    monkeypatch.setattr(rag_service, "answer_question", respond)
    response = client.post("/api/chat", json={"question": "核心概念", "document_id": DOC_A, "mode": "summary"})
    assert response.status_code == 200
    assert response.json()["metadata"]["chunks_covered"] == 30


def test_real_chroma_scope_and_source_order(tmp_path, monkeypatch):
    db = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = db.create_collection("scoped_test", embedding_function=None)
    collection.add(
        ids=["last", "other", "first"], embeddings=[[1.0, 0.0]] * 3,
        documents=["文档 A 最后页", "文档 B 不能混入", "文档 A 首页"],
        metadatas=[{"document_id": d, "filename": "public.pdf", "page_number": p, "chunk_index": 0}
                   for d, p in [(DOC_A, 9), (DOC_B, 1), (DOC_A, 1)]],
    )
    monkeypatch.setattr(vector_store, "_collection", lambda: collection)
    chunks = vector_store.get_document_chunks(DOC_A.upper())
    assert [c.page_number for c in chunks] == [1, 9]
    assert all(c.document_id == DOC_A for c in vector_store.query_chunks([1.0, 0.0], 6, DOC_A))
    assert vector_store.get_document_chunks("c" * 32) == []


def test_specific_question_is_scoped_without_fallback(monkeypatch):
    monkeypatch.setattr(rag_service, "has_documents", lambda: True)
    monkeypatch.setattr(rag_service, "embed_texts", lambda texts: [[1.0, 0.0]])
    calls = []
    def retrieve(vector, k, doc):
        calls.append(doc)
        return []
    monkeypatch.setattr(rag_service, "query_chunks", retrieve)
    with pytest.raises(DocumentNotFoundError):
        rag_service.answer_question("有效期多久？", document_id=DOC_A)
    assert calls == [DOC_A]


def test_summary_reads_every_chunk_including_tail(monkeypatch):
    chunks = [source(i, f"第 {i+1} 部分的事实") for i in range(20)]
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: chunks)
    prompts = []
    def generate(prompt):
        prompts.append(prompt)
        return "开头和最后的事实 [S1] [S20]"
    monkeypatch.setattr(summary_service, "complete_answer", generate)
    result = summary_service.summarize_document(DOC_A, "核心概念")
    assert all(c.text in prompts[0] for c in chunks)
    assert result["metadata"]["chunks_covered"] == 20
    assert result["metadata"]["indexed_pages_covered"] == 20
    assert result["sources"][-1]["cited"] is True


def section_or_synthesis(prompts, lock=None, delay=0.0, active=None):
    """Fake model: a section cites its own first label, the synthesis cites S1 and S3."""
    import re
    import threading
    import time

    lock = lock or threading.Lock()

    def generate(prompt):
        with lock:
            prompts.append(prompt)
            if active is not None:
                active["now"] += 1
                active["max"] = max(active["max"], active["now"])
        time.sleep(delay)
        if active is not None:
            with lock:
                active["now"] -= 1
        if "<不可信摘要>" in prompt:
            return "完整概览 [S1] [S3]"
        label = re.search(r"\[(S\d+)\]", prompt).group(1)
        return f"{label} 部分要点 [{label}]"
    return generate


def test_large_summary_maps_all_sections_then_synthesizes(monkeypatch):
    chunks = [source(i, f"section-{i} " + "课" * 7000) for i in range(3)]
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: chunks)
    prompts = []
    monkeypatch.setattr(summary_service, "complete_answer", section_or_synthesis(prompts))
    result = summary_service.summarize_document(DOC_A, "主要内容")
    assert len(prompts) == 4
    sections, synthesis = prompts[:3], prompts[3]
    assert all(sum(chunk.text in prompt for prompt in sections) == 1 for chunk in chunks)
    # Section notes reach the synthesis in page order regardless of completion order.
    assert synthesis.index("S1 部分要点") < synthesis.index("S2 部分要点") < synthesis.index("S3 部分要点")
    assert result["metadata"]["batches"] == 3


@pytest.mark.parametrize("concurrency", [1, 3])
def test_summary_sections_run_with_bounded_concurrency(monkeypatch, concurrency):
    chunks = [source(i, f"section-{i} " + "课" * 7000) for i in range(8)]
    monkeypatch.setattr(summary_service, "settings", replace(settings, summary_concurrency=concurrency))
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: chunks)
    prompts, active = [], {"now": 0, "max": 0}
    monkeypatch.setattr(summary_service, "complete_answer", section_or_synthesis(prompts, delay=0.05, active=active))
    result = summary_service.summarize_document(DOC_A, "主要内容")
    assert active["max"] == concurrency
    assert len(prompts) == 9 and "<不可信摘要>" in prompts[-1]
    assert [f"S{i}" in prompts[-1] for i in range(1, 9)] == [True] * 8
    assert result["metadata"]["batches"] == 8


def test_failed_section_stops_unstarted_sections_and_synthesis(monkeypatch):
    import threading
    import time

    chunks = [source(i, f"section-{i} " + "课" * 7000) for i in range(8)]
    monkeypatch.setattr(summary_service, "settings", replace(settings, summary_concurrency=2))
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: chunks)
    calls, lock = [], threading.Lock()

    def generate(prompt):
        with lock:
            calls.append(prompt)
        if "section-0" in prompt:
            return "没有引用的摘要"
        time.sleep(0.2)
        return "其他部分 [S2]"
    monkeypatch.setattr(summary_service, "complete_answer", generate)
    with pytest.raises(SummaryCitationError):
        summary_service.summarize_document(DOC_A, "主要内容")
    assert len(calls) < 8
    assert not any("<不可信摘要>" in prompt for prompt in calls)


@pytest.mark.parametrize("answer", ["无引用摘要", "摘要 [S99]"])
def test_summary_rejects_invalid_or_missing_citations(monkeypatch, answer, client):
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: [source()])
    monkeypatch.setattr(summary_service, "complete_answer", lambda prompt: answer)
    with pytest.raises(SummaryCitationError):
        summary_service.summarize_document(DOC_A, "概括")
    response = client.post("/api/chat", json={"question": "概括", "document_id": DOC_A, "mode": "summary"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "summary_citations_invalid"
    assert "summary_citations_invalid" in streamlit_app.ERROR_MESSAGES


def test_summary_over_budget_fails_before_external_calls(monkeypatch):
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: [source(i, "课" * 7000) for i in range(9)])
    monkeypatch.setattr(summary_service, "complete_answer", lambda prompt: pytest.fail("must preflight the entire document"))
    with pytest.raises(SummaryTooLargeError):
        summary_service.summarize_document(DOC_A, "概括")


def test_summary_missing_document_does_not_call_llm(monkeypatch):
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: [])
    monkeypatch.setattr(summary_service, "complete_answer", lambda prompt: pytest.fail("no document"))
    with pytest.raises(DocumentNotFoundError):
        summary_service.summarize_document(DOC_A, "概括")


def test_explicit_local_mode_does_not_read_or_send_for_summary(monkeypatch):
    monkeypatch.setattr(summary_service, "settings", replace(settings, chat_mode="retrieval_only"))
    monkeypatch.setattr(summary_service, "get_document_chunks", lambda doc: pytest.fail("local summary unavailable"))
    monkeypatch.setattr(summary_service, "complete_answer", lambda prompt: pytest.fail("no external request"))
    assert summary_service.summarize_document(DOC_A, "概括")["status"] == "retrieval_only"


def test_course_default_is_deepseek_without_exposing_key():
    run = subprocess.run(["bash", "scripts/run_real_course.sh", "--print-config"], check=True, text=True,
                         capture_output=True, env={**os.environ, "STUDYMATE_COURSE_MODE": "generation"})
    result = json.loads(run.stdout)
    assert result["chat_mode"] == "generation"
    assert "deepseek_api_key" not in result


def test_generation_disables_thinking_and_reserves_answer_budget(monkeypatch):
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="完整回答 [S1]"), finish_reason="stop")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm_service, "_get_deepseek_client", lambda: client)
    assert llm_service.complete_answer("公开虚构问题") == "完整回答 [S1]"
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert captured["max_tokens"] == 4096


def test_specific_qa_retains_reasoning_with_larger_output_budget(monkeypatch):
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="精确回答 [S1]"), finish_reason="stop")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm_service, "_get_deepseek_client", lambda: client)
    assert llm_service.complete_reasoned_answer("公开问题") == "精确回答 [S1]"
    assert captured["extra_body"]["thinking"]["type"] == "enabled"
    assert captured["max_tokens"] == 4096


@pytest.mark.parametrize("content", ["", "未完整生成的回答 [S1]"])
def test_truncated_provider_answer_is_not_reported_as_success(monkeypatch, content):
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs:
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="length")]))))
    monkeypatch.setattr(llm_service, "_get_deepseek_client", lambda: client)
    with pytest.raises(LLMOutputLimitError):
        llm_service.complete_answer("公开虚构问题")


def test_frontend_selects_document_sends_scope_and_hides_stale_answer(monkeypatch):
    captured = []
    def post(path, **kwargs):
        captured.append(kwargs["json"])
        return {"answer": "摘要 A [S1]", "status": "answered", "sources": [],
                "metadata": {"coverage": "all_indexed_text", "indexed_pages_covered": 20, "chunks_covered": 25}}, None
    monkeypatch.setattr(streamlit_app, "api_post", post)
    def app(runtime, documents):
        from frontend.streamlit_app import render_chat
        render_chat(runtime, documents)
    at = AppTest.from_function(app, args=(
        {"chat_mode": "generation", "default_top_k": 6, "summary_request_timeout_seconds": 330},
        [{"document_id": DOC_A, "filename": "new.pdf"}, {"document_id": DOC_B, "filename": "other.pdf"}],
    )).run()
    assert not at.exception
    assert at.selectbox[0].value == DOC_A
    at.radio[0].set_value("概括全文").run()
    at.button(key="submit-reading").click().run()
    assert not at.exception
    assert captured[0]["document_id"] == DOC_A
    assert captured[0]["mode"] == "summary"
    assert any("可提取文字的 20 页" in c.value for c in at.caption)
    at.selectbox[0].set_value(DOC_B).run()
    assert not any("摘要 A" in m.value for m in at.markdown)
