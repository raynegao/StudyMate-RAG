from copy import deepcopy
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from frontend import streamlit_app as ui

DOC = "a" * 32
RUNTIME = {"chat_mode": "generation", "default_top_k": 6,
           "summary_request_timeout_seconds": 330, "max_upload_size_mb": 25, "llm_provider": "deepseek"}
DOCUMENTS = [{"document_id": DOC, "filename": "公开学习资料.pdf", "chunk_count": 86}]


def chat_app(runtime, documents):
    from frontend.streamlit_app import render_chat
    render_chat(runtime, documents)


def visible_copy(at):
    return "\n".join(str(e.value) for kind in ("markdown", "caption", "text", "info", "warning", "error")
                     for e in at.get(kind))


def source(label, page=3, text="公开原文", **kwargs):
    return {"citation_id": label, "document_id": DOC, "filename": "公开学习资料.pdf",
            "page_number": page, "text": text, "cited": True, **kwargs}


def test_page_references_deduplicate_without_losing_evidence_or_paragraphs():
    original = [source("S42"), source("S86", text="同页另一段原文"), source("S87", page=8)]
    before = deepcopy(original)
    answer, groups = ui.build_reading_view("结论。[S42][S86]\n\n补充。[S87]", original)
    assert answer.count("[第 3 页]") == 1
    assert "\n\n" in answer
    assert "[第 8 页](#reading-source-2)" in answer
    assert groups[0]["texts"] == ["公开原文", "同页另一段原文"]
    assert original == before


def test_citations_never_invent_a_page_or_expose_unknown_reference():
    answer, groups = ui.build_reading_view("结论 [S1][S99]", [source("S1", page=None)])
    assert "参考原文" in answer
    assert "出处暂不可用" in answer
    assert "S99" not in answer
    assert groups[0]["title"] == "参考原文"


def test_same_page_in_different_files_remains_separate():
    _, groups = ui.build_reading_view("[S1][S2]", [source("S1"), source("S2", document_id="b" * 32)])
    assert len(groups) == 2
    assert groups[0]["anchor"] != groups[1]["anchor"]


@pytest.mark.parametrize("code", list(ui.ERROR_MESSAGES) + ["unknown_error", ["bad-shape"]])
def test_api_errors_never_expose_raw_diagnostics(code):
    response = SimpleNamespace(ok=False, status_code=500, text="Traceback /private/server secret",
                               json=lambda: {"error": {"code": code, "message": "debug secret"}})
    payload, error = ui.parse_response(response)
    assert payload is None
    assert error
    assert all(value not in error for value in ("Traceback", "private", "debug", "secret", "HTTP"))


def test_non_json_and_invalid_success_are_user_friendly():
    def not_json():
        raise ValueError("private details")
    for body in (not_json, lambda: []):
        response = SimpleNamespace(ok=True, status_code=200, json=body)
        assert ui.parse_response(response) == (None, "这次操作没有完成，请稍后重试。")


def test_consumer_chat_has_no_debug_controls_and_preserves_top_six(monkeypatch):
    calls = []
    monkeypatch.setattr(ui, "api_post", lambda path, **kw: (calls.append(kw) or
                        {"answer": "学习结论 [S42]", "sources": [source("S42")], "status": "answered"}, None))
    at = AppTest.from_function(chat_app, args=(RUNTIME, DOCUMENTS)).run()
    assert not at.exception
    assert not at.slider
    assert at.button(key="submit-reading").disabled
    at.text_area[0].set_value("这个方法适用于哪些情况？").run()
    at.button(key="submit-reading").click().run()
    assert not at.exception
    assert calls[0]["json"] == {"question": "这个方法适用于哪些情况？", "document_id": DOC,
                                 "top_k": 6, "mode": "auto"}
    text = visible_copy(at)
    for diagnostic in (DOC, "[S42]", "Distance", "Chunks", "向量", "top_k", "后端", "86 个片段"):
        assert diagnostic not in text
    assert "[第 3 页](#reading-source-1)" in text
    assert "所需原文会发送给 DeepSeek" in text
    assert at.expander[0].label == "第 3 页 · 1 处参考"
    assert not at.expander[0].proto.expanded


def test_provider_label_follows_runtime_config(monkeypatch):
    monkeypatch.setattr(ui, "api_post", lambda *a, **kw: ({"answer": "公开结论 [S1]", "sources": [], "status": "answered"}, None))
    at = AppTest.from_function(chat_app, args=({**RUNTIME, "llm_provider": "gemini"}, DOCUMENTS)).run()
    assert not at.exception
    text = visible_copy(at)
    assert "由 Gemini 提供回答" in text and "所需原文会发送给 Gemini" in text
    assert "DeepSeek" not in text and "gemini-" not in text


def test_reading_starter_prefills_but_does_not_send_document(monkeypatch):
    calls = []
    monkeypatch.setattr(ui, "api_post", lambda *a, **kw: calls.append(kw))
    at = AppTest.from_function(chat_app, args=(RUNTIME, DOCUMENTS)).run()
    next(b for b in at.button if b.label == "梳理核心概念").click().run()
    assert at.radio[0].value == "概括全文"
    assert "核心概念" in at.text_area[0].value
    assert not calls


def test_local_mode_only_shows_original_text_and_cannot_summarize(monkeypatch):
    calls = []
    monkeypatch.setattr(ui, "api_post", lambda path, **kw: (calls.append(kw) or
                        {"answer": "技术原文提示", "sources": [source("S1", cited=False)],
                         "status": "retrieval_only"}, None))
    at = AppTest.from_function(chat_app, args=({**RUNTIME, "chat_mode": "retrieval_only"}, DOCUMENTS)).run()
    assert at.radio[0].disabled
    at.text_area[0].set_value("核心概念是什么？").run()
    at.button(key="submit-reading").click().run()
    assert not at.exception
    assert calls[0]["json"]["mode"] == "question"
    assert "技术原文提示" not in visible_copy(at)
    assert "公开原文" in visible_copy(at)


def test_empty_library_and_offline_state_are_readable(monkeypatch):
    at = AppTest.from_function(chat_app, args=(RUNTIME, [])).run()
    assert "从第一份资料开始" in visible_copy(at)
    monkeypatch.setattr(ui, "api_get", lambda path: (None, ui.connection_error_message()))
    def app():
        from frontend.streamlit_app import main
        main()
    at = AppTest.from_function(app).run()
    assert not at.exception
    assert "资料不会因此被删除" in visible_copy(at)
    assert any(b.label == "重新连接" for b in at.button)


def test_failed_answer_clears_old_result_and_refusal_is_plain_language(monkeypatch):
    monkeypatch.setattr(ui, "api_post", lambda *a, **kw: (None, "这次回答没有完成，请稍后再试。"))
    at = AppTest.from_function(chat_app, args=(RUNTIME, DOCUMENTS)).run()
    at.session_state[ui.LAST_CHAT_RESULT_KEY] = {"document_id": DOC, "answer": "旧答案"}
    at.text_area[0].set_value("具体问题").run()
    at.button(key="submit-reading").click().run()
    assert "旧答案" not in visible_copy(at)
    assert "这次回答没有完成" in visible_copy(at)
    at.session_state[ui.LAST_CHAT_RESULT_KEY] = {"document_id": DOC, "status": "insufficient_evidence",
                                               "answer": "内部拒答文字", "sources": [source("S1")]}
    at.run()
    assert "没有找到足够信息" in visible_copy(at)
    assert "内部拒答文字" not in visible_copy(at)


def test_deletion_requires_confirmation_and_preserves_state_on_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(ui, "api_delete", lambda path: (calls.append(path), "删除暂未完成"))
    def app(document):
        from frontend.streamlit_app import render_document_actions
        render_document_actions(document)
    at = AppTest.from_function(app, args=(DOCUMENTS[0],)).run()
    at.button(key=f"delete-{DOC}").click().run()
    assert not calls
    assert "无法恢复" in visible_copy(at)
    at.button(key=f"cancel-delete-{DOC}").click().run()
    assert not calls
    at.button(key=f"delete-{DOC}").click().run()
    at.button(key=f"confirm-delete-{DOC}").click().run()
    assert calls == [f"/api/documents/{DOC}"]
    assert at.session_state[ui.PENDING_DELETE_KEY] == DOC


def test_uploaded_document_is_selected_without_showing_internal_counts(monkeypatch):
    from io import BytesIO
    upload = BytesIO(b"public fixture")
    upload.name = "新资料.pdf"
    monkeypatch.setattr(ui.st, "file_uploader", lambda *a, **kw: upload)
    monkeypatch.setattr(ui, "api_post", lambda *a, **kw: ({"document_id": DOC, "filename": upload.name,
                                                         "chunk_count": 86}, None))
    def app(runtime):
        from frontend.streamlit_app import render_upload_form
        render_upload_form(runtime)
    at = AppTest.from_function(app, args=(RUNTIME,)).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state[ui.SELECTED_DOCUMENT_KEY] == DOC
    assert at.session_state["upload_revision"] == 1
    assert "86" not in visible_copy(at)
