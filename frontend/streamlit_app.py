from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("STUDYMATE_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = float(os.getenv("STUDYMATE_FRONTEND_TIMEOUT", "60"))
UPLOAD_REQUEST_TIMEOUT = float(
    os.getenv("STUDYMATE_FRONTEND_UPLOAD_TIMEOUT", "300")
)
LAST_CHAT_RESULT_KEY = "last_chat_result"
PENDING_DELETE_KEY = "pending_delete_document_id"


def connection_error_message() -> str:
    """Return a user-facing error without exposing an internal backend address."""
    return "无法连接后端，请确认服务已启动后重试。"


def api_get(path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT)
        return parse_response(response)
    except requests.Timeout:
        return None, "请求超时，请稍后重试。"
    except requests.RequestException:
        return None, connection_error_message()


def api_post(
    path: str,
    *,
    json: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    timeout: float | None = None,
    timeout_message: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            f"{API_BASE_URL}{path}",
            json=json,
            files=files,
            timeout=REQUEST_TIMEOUT if timeout is None else timeout,
        )
        return parse_response(response)
    except requests.Timeout:
        return None, timeout_message or "请求超时，请稍后重试。"
    except requests.RequestException:
        return None, connection_error_message()


def api_delete(path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.delete(f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT)
        return parse_response(response)
    except requests.Timeout:
        return None, "删除请求超时，请刷新文档列表确认结果。"
    except requests.RequestException:
        return None, connection_error_message()


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


def build_source_view(source: dict[str, Any], index: int) -> dict[str, Any]:
    """Normalize a source for display while preserving the API's distance semantics."""
    citation_id = str(source.get("citation_id") or f"S{index}")
    filename = source.get("filename") or "未知文件"
    page = source.get("page") or source.get("page_number")
    cited = source.get("cited") is True

    distance = source.get("distance")
    try:
        distance_label = f"{float(distance):.4f}" if distance is not None else None
    except (TypeError, ValueError):
        distance_label = None

    title = f"[{citation_id}] {filename}"
    if page is not None:
        title = f"{title} p.{page}"

    return {
        "citation_id": citation_id,
        "title": title,
        "status": "回答已引用" if cited else "仅检索候选",
        "cited": cited,
        "distance_label": distance_label,
        "chunk_id": source.get("chunk_id"),
        "text": source.get("text") or "无片段内容",
    }


def render_backend_status() -> None:
    payload, error = api_get("/health")
    if error:
        st.sidebar.error(error)
        return
    st.sidebar.success(f"后端在线：{payload.get('service', 'StudyMate')}")


def render_documents() -> None:
    payload, error = api_get("/api/documents")
    st.sidebar.subheader("文档")
    if st.sidebar.button("刷新文档列表", key="refresh-documents"):
        st.rerun()
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
        document_id = document["document_id"]
        with st.sidebar.container(border=True):
            st.markdown(f"**{label}**")
            st.caption(f"ID: {document_id}")
            if chunks is not None:
                st.caption(f"Chunks: {chunks}")
            if pages:
                st.caption(f"Pages: {len(pages)}")

            is_pending = st.session_state.get(PENDING_DELETE_KEY) == document_id
            if not is_pending and st.button("删除", key=f"delete-{document_id}"):
                st.session_state[PENDING_DELETE_KEY] = document_id
                st.rerun()

            if is_pending:
                st.warning("确认删除？原始上传文件和对应向量索引都会被移除。")
                confirm_column, cancel_column = st.columns(2)
                if confirm_column.button(
                    "确认删除",
                    key=f"confirm-delete-{document_id}",
                    type="primary",
                ):
                    _, delete_error = api_delete(f"/api/documents/{document_id}")
                    st.session_state.pop(PENDING_DELETE_KEY, None)
                    if delete_error:
                        st.error(delete_error)
                    else:
                        st.success("原始文件和向量索引已删除")
                        st.rerun()
                if cancel_column.button("取消", key=f"cancel-delete-{document_id}"):
                    st.session_state.pop(PENDING_DELETE_KEY, None)
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
            payload, error = api_post(
                "/api/upload",
                files=files,
                timeout=UPLOAD_REQUEST_TIMEOUT,
                timeout_message=(
                    "上传请求超时，后端可能仍在处理。请先刷新文档列表确认结果，"
                    "避免重复上传。"
                ),
            )
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

    st.subheader("引用与检索来源")
    st.caption(
        "Distance 表示向量距离，数值越小通常越相关；"
        "“回答已引用”表示答案中实际出现了该来源标记。"
    )
    for index, source in enumerate(sources, start=1):
        view = build_source_view(source, index)
        status_icon = "✅" if view["cited"] else "🔎"
        with st.expander(
            f"{status_icon} {view['status']} · {view['title']}",
            expanded=view["cited"],
        ):
            if view["chunk_id"] is not None:
                st.caption(f"Chunk: {view['chunk_id']}")
            if view["distance_label"] is not None:
                st.caption(f"Distance: {view['distance_label']}")
            st.write(view["text"])


def render_chat() -> None:
    st.header("StudyMate RAG")
    top_k = st.slider("检索片段数", min_value=1, max_value=10, value=4)
    question = st.text_area("问题", height=120, placeholder="例如：这份资料的核心概念是什么？")

    submitted = st.button("提问", type="primary", disabled=not question.strip())
    if submitted:
        with st.spinner("正在检索资料并生成回答..."):
            payload, error = api_post(
                "/api/chat",
                json={"question": question.strip(), "top_k": top_k},
            )
        if error:
            st.error(error)
        elif payload is not None:
            st.session_state[LAST_CHAT_RESULT_KEY] = {
                "question": question.strip(),
                "answer": payload.get("answer", ""),
                "sources": payload.get("sources", []),
            }

    result = st.session_state.get(LAST_CHAT_RESULT_KEY)
    if not result:
        st.info("上传并索引课程资料后，即可基于资料提问。")
        return

    st.subheader("回答")
    if result.get("question"):
        st.caption(f"问题：{result['question']}")
    st.write(result.get("answer", ""))
    render_sources(result.get("sources", []))


def main() -> None:
    st.set_page_config(page_title="StudyMate RAG", layout="wide")
    st.sidebar.title("StudyMate")
    st.sidebar.caption("课程资料智能问答")
    render_backend_status()
    render_upload()
    render_documents()
    render_chat()


if __name__ == "__main__":
    main()
