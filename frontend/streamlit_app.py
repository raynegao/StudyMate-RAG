from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("STUDYMATE_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = float(os.getenv("STUDYMATE_FRONTEND_TIMEOUT", "60"))


def api_get(path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT)
        return parse_response(response)
    except requests.RequestException as exc:
        return None, f"无法连接后端：{exc}"


def api_post(
    path: str,
    *,
    json: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            f"{API_BASE_URL}{path}",
            json=json,
            files=files,
            timeout=REQUEST_TIMEOUT,
        )
        return parse_response(response)
    except requests.RequestException as exc:
        return None, f"无法连接后端：{exc}"


def api_delete(path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.delete(f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT)
        return parse_response(response)
    except requests.RequestException as exc:
        return None, f"无法连接后端：{exc}"


def parse_response(response: requests.Response) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.ok:
        return payload, None

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return None, error.get("message") or response.text
    return None, response.text or f"HTTP {response.status_code}"


def render_backend_status() -> None:
    payload, error = api_get("/health")
    if error:
        st.sidebar.error(error)
        return
    st.sidebar.success(f"后端在线：{payload.get('service', 'StudyMate')}")


def render_documents() -> None:
    payload, error = api_get("/api/documents")
    st.sidebar.subheader("文档")
    if error:
        st.sidebar.warning(error)
        return

    documents = payload.get("documents", []) if payload else []
    if not documents:
        st.sidebar.caption("暂无已索引文档")
        return

    for document in documents:
        label = document.get("filename") or document["document_id"]
        chunks = document.get("chunk_count")
        pages = document.get("metadata", {}).get("pages") or document.get("pages")
        with st.sidebar.container(border=True):
            st.markdown(f"**{label}**")
            st.caption(f"ID: {document['document_id']}")
            if chunks is not None:
                st.caption(f"Chunks: {chunks}")
            if pages:
                st.caption(f"Pages: {len(pages)}")
            if st.button("删除", key=f"delete-{document['document_id']}"):
                _, delete_error = api_delete(f"/api/documents/{document['document_id']}")
                if delete_error:
                    st.error(delete_error)
                else:
                    st.success("已删除")
                    st.rerun()


def render_upload() -> None:
    st.sidebar.subheader("上传 PDF")
    uploaded_file = st.sidebar.file_uploader("选择课程资料", type=["pdf"])
    if not uploaded_file:
        return

    if st.sidebar.button("上传并索引", type="primary"):
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf",
            )
        }
        with st.spinner("正在解析、切分并写入向量库..."):
            payload, error = api_post("/api/upload", files=files)
        if error:
            st.sidebar.error(error)
            return
        st.sidebar.success(
            f"已索引 {payload.get('filename')}，chunks: {payload.get('chunk_count')}"
        )
        st.rerun()


def render_sources(sources: list[dict[str, Any]]) -> None:
    if not sources:
        st.info("本次回答没有返回引用来源。")
        return

    st.subheader("引用来源")
    for index, source in enumerate(sources, start=1):
        filename = source.get("filename") or "未知文件"
        page = source.get("page") or source.get("page_number")
        title = f"{index}. {filename}"
        if page:
            title = f"{title} p.{page}"
        with st.expander(title, expanded=index == 1):
            chunk_id = source.get("chunk_id")
            score = source.get("score")
            if chunk_id is not None:
                st.caption(f"Chunk: {chunk_id}")
            if score is not None:
                st.caption(f"Distance: {score:.4f}")
            st.write(source.get("text") or "无片段内容")


def render_chat() -> None:
    st.header("StudyMate RAG")
    top_k = st.slider("检索片段数", min_value=1, max_value=10, value=4)
    question = st.text_area("问题", height=120, placeholder="例如：这份资料的核心概念是什么？")

    if not st.button("提问", type="primary", disabled=not question.strip()):
        return

    with st.spinner("正在检索资料并生成回答..."):
        payload, error = api_post(
            "/api/chat",
            json={"question": question.strip(), "top_k": top_k},
        )
    if error:
        st.error(error)
        return

    st.subheader("回答")
    st.write(payload.get("answer", ""))
    render_sources(payload.get("sources", []))


def main() -> None:
    st.set_page_config(page_title="StudyMate RAG", layout="wide")
    st.sidebar.title("StudyMate")
    st.sidebar.caption(API_BASE_URL)
    render_backend_status()
    render_upload()
    render_documents()
    render_chat()


if __name__ == "__main__":
    main()
