from __future__ import annotations

import requests

from frontend import streamlit_app


class SuccessfulResponse:
    ok = True
    text = ""
    status_code = 200

    @staticmethod
    def json():
        return {"status": "ok"}


def test_api_post_uses_upload_timeout_override(monkeypatch):
    captured = {}

    def fake_post(url, *, json, files, timeout):
        captured.update(url=url, json=json, files=files, timeout=timeout)
        return SuccessfulResponse()

    monkeypatch.setattr(streamlit_app.requests, "post", fake_post)

    payload, error = streamlit_app.api_post(
        "/api/upload",
        files={"file": ("课程资料.pdf", b"pdf", "application/pdf")},
        timeout=321,
    )

    assert error is None
    assert payload == {"status": "ok"}
    assert captured["timeout"] == 321
    assert captured["url"].endswith("/api/upload")


def test_api_post_timeout_uses_safe_upload_hint(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.Timeout("http://backend:8000/api/upload timed out")

    monkeypatch.setattr(streamlit_app.requests, "post", fake_post)
    hint = "请先刷新文档列表确认结果，避免重复上传。"

    payload, error = streamlit_app.api_post(
        "/api/upload",
        files={"file": ("课程资料.pdf", b"pdf", "application/pdf")},
        timeout=321,
        timeout_message=hint,
    )

    assert payload is None
    assert error == hint
    assert "backend:8000" not in error


def test_connection_error_does_not_expose_internal_address(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.ConnectionError("http://backend:8000 refused")

    monkeypatch.setattr(streamlit_app.requests, "get", fake_get)

    payload, error = streamlit_app.api_get("/health")

    assert payload is None
    assert error == "无法连接后端，请确认服务已启动后重试。"
    assert "backend:8000" not in error


def test_build_source_view_marks_cited_source_and_formats_distance():
    view = streamlit_app.build_source_view(
        {
            "citation_id": "S2",
            "filename": "课程资料.pdf",
            "page": 3,
            "chunk_id": "chunk-2",
            "distance": 0.123456,
            "cited": True,
            "text": "课程内容",
        },
        2,
    )

    assert view["title"] == "[S2] 课程资料.pdf p.3"
    assert view["status"] == "回答已引用"
    assert view["cited"] is True
    assert view["distance_label"] == "0.1235"


def test_build_source_view_marks_uncited_result_as_retrieval_candidate():
    view = streamlit_app.build_source_view(
        {
            "filename": "notes.pdf",
            "distance": "not-a-number",
            "cited": False,
        },
        1,
    )

    assert view["citation_id"] == "S1"
    assert view["status"] == "仅检索候选"
    assert view["cited"] is False
    assert view["distance_label"] is None
