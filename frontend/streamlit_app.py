from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("STUDYMATE_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = float(os.getenv("STUDYMATE_FRONTEND_TIMEOUT", "60"))
UPLOAD_REQUEST_TIMEOUT = float(
    os.getenv("STUDYMATE_FRONTEND_UPLOAD_TIMEOUT", "300")
)
MAX_UPLOAD_SIZE_MB = int(os.getenv("STUDYMATE_MAX_UPLOAD_SIZE_MB", "25"))
LAST_CHAT_RESULT_KEY = "last_chat_result"
PENDING_DELETE_KEY = "pending_delete_document_id"
SELECTED_DOCUMENT_KEY = "selected_document_id"
QUESTION_KEY = "reading_question"
TASK_KEY = "reading_task"
# The address bar remembers the chosen document across reloads. It carries only the
# internal document ID, never a filename, and the page copy still shows no IDs.
DOCUMENT_QUERY_PARAM = "doc"

PROVIDER_LABELS = {"deepseek": "DeepSeek", "gemini": "Gemini"}

ERROR_MESSAGES = {
    "unsupported_file_type": "目前支持 PDF 格式，请换一份文件试试。",
    "upload_too_large": "文件太大了，请按上传区提示的大小限制缩小文件后重试。",
    "invalid_pdf": "这份 PDF 暂时无法打开，请确认文件完整后重新上传。",
    "encrypted_pdf": "这份 PDF 有密码保护，请解除保护后重新上传。",
    "pdf_no_extractable_text": "没有读到可用的文字，请上传可以选中文字的 PDF；暂不支持纯图片扫描件。",
    "embedding_failed": "资料阅读暂时不可用，请稍后重试。",
    "embedding_input_too_long": "这次内容有些长，请缩短问题，或将资料拆分后重试。",
    "vector_store_unavailable": "暂时无法读取你的资料，请稍后重试。",
    "invalid_document_id": "暂时无法打开这份资料，请重新选择。",
    "document_not_found": "这份资料已不在资料库中，请刷新后重新选择。",
    "document_selection_required": "请先选择一份资料，再开始阅读。",
    "summary_too_large": "这份资料太长，暂时无法一次概括。请拆分为较短的 PDF 后重试。",
    "llm_not_configured": "智能回答暂不可用，请稍后再试。",
    "llm_request_failed": "这次回答没有完成，请稍后再试。",
    "llm_timeout": "这次阅读花的时间有些长，请稍后重试。",
    "llm_rate_limited": "请求有些频繁，请稍等片刻再试。",
    "llm_quota_exhausted": "智能回答的额度暂时用完了，请稍后再试。",
    "llm_output_incomplete": "回答未能完整生成，请减少本次要求后重试。",
    "summary_citations_invalid": "这次概括没有对应到原文页码，结果未采用。请再试一次，或减少概括要求。",
    "validation_error": "请检查所选资料和问题后，再试一次。",
}


def provider_label(runtime: dict[str, Any]) -> str:
    """Reader-facing name of the answer model provider; never an internal model name."""
    return PROVIDER_LABELS.get(str(runtime.get("llm_provider", "")), "智能模型")


def connection_error_message() -> str:
    """Return a user-facing error without exposing an internal backend address."""
    return "暂时无法连接阅读服务，请稍后重试。"


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
        return None, "删除还未确认完成，请刷新资料列表查看结果。"
    except requests.RequestException:
        return None, connection_error_message()


def parse_response(response: requests.Response) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = response.json()
    except ValueError:
        return None, "这次操作没有完成，请稍后重试。"

    if response.ok and isinstance(payload, dict):
        return payload, None

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        code = error.get("code")
        return None, ERROR_MESSAGES.get(code if isinstance(code, str) else "", "这次操作没有完成，请稍后重试。")
    return None, "这次操作没有完成，请稍后重试。"


def build_reading_view(
    answer: str, sources: list[dict[str, Any]], *, include_uncited: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """Translate internal references to page links without changing API evidence."""
    cited = {f"S{int(n)}" for n in re.findall(r"\[S(\d+)\]", answer, re.I)}
    groups: dict[tuple, dict[str, Any]] = {}
    references = {}
    for index, source in enumerate(sources, 1):
        citation_id = str(source.get("citation_id") or f"S{index}").upper()
        if not include_uncited and citation_id not in cited:
            continue
        filename = source.get("filename") or "当前资料"
        page = source.get("page") or source.get("page_number")
        page = page if isinstance(page, int) and not isinstance(page, bool) and page > 0 else None
        key = (source.get("document_id"), filename, page)
        if key not in groups:
            groups[key] = {"title": f"第 {page} 页" if page else "参考原文",
                           "anchor": f"reading-source-{len(groups) + 1}",
                           "filename": filename, "texts": []}
        group = groups[key]
        text = source.get("text") or "这段原文暂时无法展示。"
        if text not in group["texts"]:
            group["texts"].append(text)
        references[citation_id] = f"[{group['title']}](#{group['anchor']})"

    def replace_references(match: re.Match) -> str:
        links = dict.fromkeys(
            references.get(f"S{int(n)}", "（出处暂不可用）")
            for n in re.findall(r"\[S(\d+)\]", match.group(), re.I)
        )
        return " " + " ".join(links) + " "

    displayed = re.sub(r"(?:\[S\d+\][ \t]*)+", replace_references, answer, flags=re.I)
    return displayed, list(groups.values())


def apply_styles() -> None:
    css = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown('''<div class="sm-hero">
        <div class="sm-eyebrow">让每一次阅读，都有所收获</div>
        <h1>资料里的答案，<br>问一问就清楚。</h1>
        <p>读懂重点，解答疑问。让 StudyMate 陪你把复杂的内容，一点点理清。</p>
        </div>''', unsafe_allow_html=True)


def render_backend_status() -> dict[str, Any] | None:
    payload, error = api_get("/health")
    if error:
        st.sidebar.error(error)
        return
    runtime, error = api_get("/api/config")
    if error:
        st.sidebar.error(error)
        return None
    return runtime


def render_documents() -> list[dict[str, Any]]:
    payload, error = api_get("/api/documents")
    if error:
        st.sidebar.warning(error)
        return []

    documents = payload.get("documents", []) if payload else []
    return documents


def render_document_management(documents: list[dict[str, Any]]) -> None:
    with st.sidebar.expander("管理资料"):
        if st.button("刷新资料", key="refresh-documents", use_container_width=True):
            st.rerun()
        if not documents:
            st.caption("添加的资料会出现在这里。")
        for document in documents:
            render_document_actions(document)


def render_document_actions(document: dict[str, Any]) -> None:
    document_id = document["document_id"]
    with st.container(border=True):
        st.text(document.get("filename") or "未命名资料")
        is_pending = st.session_state.get(PENDING_DELETE_KEY) == document_id
        if not is_pending and st.button("删除资料", key=f"delete-{document_id}"):
            st.session_state[PENDING_DELETE_KEY] = document_id
            st.rerun()

        if is_pending:
            st.warning("删除后，这份资料将从 StudyMate 移除，无法恢复。你电脑中的原文件不受影响。")
            confirm_column, cancel_column = st.columns(2)
            if confirm_column.button("确认删除", key=f"confirm-delete-{document_id}", type="primary"):
                _, delete_error = api_delete(f"/api/documents/{document_id}")
                if delete_error:
                    st.error(delete_error)
                else:
                    st.session_state.pop(PENDING_DELETE_KEY, None)
                    if st.session_state.get(LAST_CHAT_RESULT_KEY, {}).get("document_id") == document_id:
                        st.session_state.pop(LAST_CHAT_RESULT_KEY, None)
                    st.session_state["reading_notice"] = "资料已删除。"
                    st.rerun()
            if cancel_column.button("取消", key=f"cancel-delete-{document_id}"):
                st.session_state.pop(PENDING_DELETE_KEY, None)
                st.rerun()


def render_upload(runtime: dict[str, Any], *, expanded: bool = False) -> None:
    with st.sidebar.expander("添加资料", expanded=expanded):
        render_upload_form(runtime)


def render_upload_form(runtime: dict[str, Any]) -> None:
    limit = runtime["max_upload_size_mb"]
    if st.get_option("server.maxUploadSize") != limit:
        st.error("上传功能暂不可用，请稍后重试。已添加的资料仍可阅读。")
        return
    st.caption(f"支持 PDF，每份不超过 {limit} MB。")
    uploaded_file = st.file_uploader(
        "选择 PDF 资料", label_visibility="collapsed",
        type=["pdf"],
        key=f"reading_upload_{st.session_state.get('upload_revision', 0)}",
    )
    if not uploaded_file:
        return

    if st.button("添加到我的资料", type="primary", use_container_width=True):
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf",
            )
        }
        with st.spinner("正在阅读资料，准备好后就可以提问了…"):
            payload, error = api_post(
                "/api/upload",
                files=files,
                timeout=UPLOAD_REQUEST_TIMEOUT,
                timeout_message=(
                    "资料仍可能在处理中，请先刷新资料列表查看结果，避免重复添加。"
                ),
            )
        if error:
            st.error(error)
            return
        st.session_state["reading_notice"] = "资料已准备好，可以开始阅读了。"
        st.session_state["upload_revision"] = st.session_state.get("upload_revision", 0) + 1
        st.session_state[SELECTED_DOCUMENT_KEY] = payload["document_id"]
        st.session_state.pop(LAST_CHAT_RESULT_KEY, None)
        st.rerun()


def render_sources(groups: list[dict[str, Any]]) -> None:
    if not groups:
        return
    st.subheader("查看原文")
    st.caption("展开页码，核对回答的依据。")
    for group in groups:
        st.markdown(f'<div id="{group["anchor"]}" class="sm-source-anchor"></div>', unsafe_allow_html=True)
        with st.expander(f"{group['title']} · {len(group['texts'])} 处参考"):
            st.caption(group["filename"])
            for index, text in enumerate(group["texts"]):
                if index:
                    st.divider()
                st.text(text)


def set_reading_prompt(question: str) -> None:
    st.session_state[QUESTION_KEY] = question
    st.session_state[TASK_KEY] = "概括全文"


def render_chat(runtime: dict[str, Any], documents: list[dict[str, Any]]) -> None:
    render_hero()
    if not documents:
        st.markdown('''<div class="sm-empty"><div class="sm-step">从第一份资料开始</div>
            <h2>把想读懂的 PDF，交给 StudyMate。</h2>
            <p>在左侧「添加资料」上传文件，再选择概括全文，或问一个你关心的问题。<br>
            回答附有原文页码，方便随时核对。手机上可先点左上角打开资料栏。</p></div>''', unsafe_allow_html=True)
        return
    by_id = {d["document_id"]: d for d in documents}
    if st.session_state.get(SELECTED_DOCUMENT_KEY) not in by_id:
        remembered = st.query_params.get(DOCUMENT_QUERY_PARAM)
        st.session_state[SELECTED_DOCUMENT_KEY] = remembered if remembered in by_id else documents[0]["document_id"]
    st.sidebar.subheader("我的资料")
    selected = st.sidebar.selectbox(
        "正在阅读", options=list(by_id), key=SELECTED_DOCUMENT_KEY,
        format_func=lambda value: by_id[value].get("filename") or "未命名资料",
    )
    if st.query_params.get(DOCUMENT_QUERY_PARAM) != selected:
        st.query_params[DOCUMENT_QUERY_PARAM] = selected
    st.sidebar.caption(f"共 {len(documents)} 份资料 · 每次阅读一份")
    generation = runtime["chat_mode"] == "generation"
    if not generation:
        st.session_state[TASK_KEY] = "问资料"
        st.info("当前可查找资料中的原文，暂不生成智能回答。资料内容不会发送给外部 AI。")
    if generation:
        st.caption("不知道从哪里开始？试试这些阅读方向")
        for column, (label, prompt) in zip(st.columns(3), [
            ("概括主要内容", "请概括这份资料的主要内容。"),
            ("梳理核心概念", "请解释这份资料的核心概念及它们之间的关系。"),
            ("提炼重要结论", "请总结这份资料的重要结论与适用条件。"),
        ], strict=True):
            column.button(label, on_click=set_reading_prompt, args=(prompt,), use_container_width=True)
    with st.container(border=True):
        st.caption("本次阅读的资料")
        st.text(by_id[selected].get("filename") or "未命名资料")
        task = st.radio("阅读方式", ["问资料", "概括全文"], horizontal=True, key=TASK_KEY,
                        disabled=not generation)
        summary = task == "概括全文"
        question = st.text_area("有没有特别关注的内容？（选填）" if summary else "想了解什么？",
                                height=115, max_chars=2000, key=QUESTION_KEY,
                                placeholder="例如：重点解释核心概念，用容易理解的语言总结。" if summary
                                else "例如：这份资料提到的方法，适用于哪些情况？")
        if summary:
            st.caption("将通读资料中可读取的文字，为你整理整体脉络与重点。")
        else:
            st.caption("回答基于当前资料。只问“主要内容是什么”这类整体问题时会概括全文；指定章节或具体问题按原文检索。" if generation
                       else "输入一个具体问题，为你找出资料中的相关内容。")
        submitted = st.button(("生成概括" if summary else "开始提问") if generation else "查找原文",
                              key="submit-reading", type="primary", use_container_width=True,
                              disabled=(not summary and not question.strip()) or (summary and not generation))
    st.caption(f"由 {provider_label(runtime)} 提供回答 · 点击生成时，所需原文会发送给 {provider_label(runtime)}；概括会读取整份资料的文字。" if generation
               else "仅在本机查找资料内容。")
    if submitted:
        prompt = question.strip() or "请概括这份资料的主要内容、核心概念及重要条件。"
        st.session_state.pop(LAST_CHAT_RESULT_KEY, None)
        with st.spinner("正在为你阅读和整理，请稍候…" if generation else "正在查找相关内容…"):
            payload, error = api_post(
                "/api/chat",
                json={"question": prompt, "top_k": runtime["default_top_k"], "document_id": selected,
                      "mode": ("summary" if summary else "auto") if generation else "question"},
                timeout=max(REQUEST_TIMEOUT, runtime["summary_request_timeout_seconds"]),
            )
        if error:
            st.error(error)
        elif payload is not None:
            st.session_state[LAST_CHAT_RESULT_KEY] = {
                "question": prompt, "document_id": selected,
                "answer": payload.get("answer", ""),
                "sources": payload.get("sources", []),
                "status": payload.get("status"), "metadata": payload.get("metadata", {}),
            }

    result = st.session_state.get(LAST_CHAT_RESULT_KEY)
    if not result or result.get("document_id") != selected:
        st.markdown('<div class="sm-reading-note">每一个答案，都能回到原文。<br>提问后，你可以在回答下方查看对应页码和内容。</div>', unsafe_allow_html=True)
        return

    st.divider()
    st.subheader("为你整理的回答")
    if result.get("question"):
        st.caption(f"问题：{result['question']}")
    if result.get("status") == "insufficient_evidence":
        st.info("这份资料里暂时没有找到足够信息。试试换一个更具体的问题，或先概括全文。")
        return
    metadata = result.get("metadata", {})
    if metadata.get("coverage") == "all_indexed_text":
        st.caption(f"已阅读资料中可提取文字的 {metadata['indexed_pages_covered']} 页；不包含扫描图片中的内容。")
    local = result.get("status") == "retrieval_only"
    answer, groups = build_reading_view(result.get("answer", ""), result.get("sources", []), include_uncited=local)
    st.markdown("为你找到了以下相关内容，展开页码即可阅读。" if local else answer)
    st.caption("AI 回答可能有误，重要信息请结合原文核对。" if not local else "以下内容摘自你选择的资料。")
    render_sources(groups)


def main() -> None:
    st.set_page_config(page_title="StudyMate · 读懂你的资料", page_icon="📖", layout="wide")
    apply_styles()
    st.sidebar.markdown('''<div class="sm-brand"><div class="sm-mark" aria-hidden="true">S</div>
        <div><strong>StudyMate</strong><small>你的随身阅读助手</small></div></div>''', unsafe_allow_html=True)
    runtime = render_backend_status()
    if runtime is None:
        render_hero()
        st.info("阅读服务暂时无法连接。你的资料不会因此被删除，请稍后再试。")
        if st.button("重新连接"):
            st.rerun()
        return
    documents = render_documents()
    render_upload(runtime, expanded=not documents)
    notice = st.session_state.pop("reading_notice", None)
    if notice:
        st.toast(notice)
    render_chat(runtime, documents)
    render_document_management(documents)
    with st.sidebar.expander("使用与隐私"):
        st.write("每次只使用你选中的资料，不会混入其他文件的内容。")
        st.write(f"智能回答会把所需原文发送给 {provider_label(runtime)}，全文概括会处理资料中全部可读取的文字。" if runtime["chat_mode"] == "generation"
                 else "当前只在本机查找原文，不会把资料内容发送给外部 AI。")
        st.caption("暂不支持纯图片扫描件。重要信息请结合原文核对。")


if __name__ == "__main__":
    main()
