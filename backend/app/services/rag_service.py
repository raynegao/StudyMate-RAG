from __future__ import annotations

import logging

from app.core.config import settings
from app.services.embedding_service import embed_texts
from app.services.llm_service import complete_answer
from app.services.vector_store import RetrievedChunk, query_chunks

logger = logging.getLogger(__name__)


def answer_question(question: str, top_k: int | None = None) -> dict:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question 不能为空。")

    effective_top_k = top_k or settings.default_top_k
    query_embedding = embed_texts([cleaned_question])[0]
    chunks = query_chunks(query_embedding, effective_top_k)
    logger.info(
        "retrieval_finished",
        extra={"top_k": effective_top_k, "retrieved_count": len(chunks)},
    )
    if not chunks:
        return {
            "question": cleaned_question,
            "answer": "当前知识库中没有可用于回答的问题相关资料。",
            "sources": [],
        }

    prompt = build_prompt(cleaned_question, chunks)
    answer = complete_answer(prompt)
    logger.info("llm_answer_finished", extra={"source_count": len(chunks)})

    return {
        "question": cleaned_question,
        "answer": answer,
        "sources": [
            {
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "source": chunk.source,
                "distance": chunk.distance,
                "text": chunk.text,
            }
            for chunk in chunks
        ],
    }


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context_blocks = []
    for index, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{index}] 来源: {chunk.source}\n"
            f"document_id: {chunk.document_id}\n"
            f"内容: {chunk.text}"
        )

    context = "\n\n".join(context_blocks)
    return (
        "请只基于下列课程资料回答问题。"
        "如果资料不足以回答，请明确说明资料中没有足够信息。"
        "回答后用“引用来源”列出用到的来源编号、文件名和页码。\n\n"
        f"课程资料:\n{context}\n\n"
        f"问题: {question}"
    )
