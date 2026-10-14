from __future__ import annotations

import requests
import tomllib

from frontend import streamlit_app


class SuccessfulResponse:
    ok = True
    text = ""
    status_code = 200

    @staticmethod
    def json():
        return {"status": "ok"}


def test_streamlit_and_backend_upload_limits_match():
    with open(".streamlit/config.toml", "rb") as file:
        config = tomllib.load(file)

    assert config["server"]["maxUploadSize"] == 25
    assert streamlit_app.MAX_UPLOAD_SIZE_MB == 25


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
    assert error == "暂时无法连接阅读服务，请稍后重试。"
    assert "backend:8000" not in error


def test_reading_view_replaces_internal_reference_with_page_link():
    answer, groups = streamlit_app.build_reading_view(
        "课程内容 [S2]", [{
            "citation_id": "S2",
            "filename": "课程资料.pdf",
            "page": 3,
            "chunk_id": "chunk-2",
            "distance": 0.123456,
            "cited": True,
            "text": "课程内容",
        }],
    )
    assert "[第 3 页](#reading-source-1)" in answer
    assert "[S2]" not in answer
    assert groups == [{"title": "第 3 页", "anchor": "reading-source-1",
                       "filename": "课程资料.pdf", "texts": ["课程内容"]}]


def test_reading_view_hides_unused_candidates_but_keeps_local_excerpts():
    sources = [{
            "filename": "notes.pdf",
            "distance": "not-a-number",
            "cited": False,
            "text": "公开原文",
        }]
    assert streamlit_app.build_reading_view("没有引用", sources)[1] == []
    _, groups = streamlit_app.build_reading_view("", sources, include_uncited=True)
    assert groups[0]["texts"] == ["公开原文"]
