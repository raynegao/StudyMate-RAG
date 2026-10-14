"""Isolated, fictional UI fixture. No storage, model, or network calls.

Run: PYTHONPATH=. .venv/bin/python -m streamlit run tests/ui_preview.py --server.port 8513
Use ?scenario=empty, local, or error to review additional states.
"""
import streamlit as st

from frontend import streamlit_app as ui

DOC = "a" * 32
scenario = st.query_params.get("scenario", "ready")
runtime = {"chat_mode": "retrieval_only" if scenario == "local" else "generation",
           "default_top_k": 6, "summary_request_timeout_seconds": 330, "max_upload_size_mb": 25}
documents = [{"document_id": DOC, "filename": "高效学习：从理解到应用.pdf", "chunk_count": 86},
             {"document_id": "b" * 32, "filename": "知识管理与阅读笔记.pdf", "chunk_count": 42}]
if scenario == "empty":
    documents = []


def get(path):
    if scenario == "error":
        return None, ui.connection_error_message()
    return {"/health": {"status": "ok"}, "/api/config": runtime,
            "/api/documents": {"documents": documents}}[path], None


def post(path, **kwargs):
    if path != "/api/chat":
        return None, "此预览不保存文件，请在正式页面添加资料。"
    return {"status": "retrieval_only" if scenario == "local" else "answered",
            "answer": "### 学习，不只是记住答案\n\n这份资料围绕三个相互关联的学习方法展开："
                      "**主动回忆、间隔复习与实际应用**。[S42]\n\n"
                      "1. **主动回忆**：先合上资料，用自己的话说出核心观点，再回到原文查漏补缺。[S42]\n"
                      "2. **间隔复习**：把复习分散到不同的时间，而不是一次重复阅读很多遍。[S86]\n"
                      "3. **实际应用**：用一个具体例子检验理解，把知识转化为可以使用的方法。[S86]\n\n"
                      "一句话理解：**先试着回忆，再安排复习，最后用起来。**",
            "sources": [{"citation_id": "S42", "document_id": kwargs["json"]["document_id"],
                         "filename": documents[0]["filename"], "page_number": 3, "cited": True,
                         "text": "主动回忆要求学习者在不查看资料的情况下尝试复述知识，并在随后核对原文、补充遗漏。"},
                        {"citation_id": "S86", "document_id": kwargs["json"]["document_id"],
                         "filename": documents[0]["filename"], "page_number": 8, "cited": True,
                         "text": "将复习安排在不同时间，并通过具体案例应用所学内容，有助于检验和巩固理解。"}],
            "metadata": {"coverage": "all_indexed_text", "indexed_pages_covered": 8, "chunks_covered": 86}
                        if kwargs["json"]["mode"] == "summary" else {}}, None


ui.api_get = get
ui.api_post = post
ui.api_delete = lambda path: (None, "此预览不删除文件，请在正式页面管理资料。")
ui.main()
