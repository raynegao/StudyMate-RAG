#!/usr/bin/env python3
"""Prepare a new local-only course index from authorized source PDFs, never old indexes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import create_app  # noqa: E402
from scripts.evaluate_real_course import (  # noqa: E402
    SOURCE_MAP_PATH, load_manifest, load_source_map, validate_sources,
)

RECEIPT = ROOT_DIR / "evaluation/private/real-course-v2-receipt.json"


def profile_signature() -> dict:
    return {
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "chunk_max_tokens": settings.chunk_max_tokens,
        "embedding_model": settings.embedding_model,
        "collection": settings.chroma_collection,
    }


def prepare() -> dict:
    expected_uploads = ROOT_DIR / "data/uploads/real-course-v2"
    expected_chroma = ROOT_DIR / "data/chroma_db/real-course-v2"
    if (settings.upload_dir.resolve() != expected_uploads
            or settings.chroma_dir.resolve() != expected_chroma
            or settings.chat_mode != "retrieval_only"):
        raise RuntimeError("请通过 scripts/run_real_course.sh prepare 加载课程库配置")
    if RECEIPT.exists():
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if receipt["profile"] != profile_signature():
            raise RuntimeError("课程库分块配置已变化；请使用新目录重建，不能混用旧向量")
        if not (expected_chroma / "chroma.sqlite3").is_file() or any(
            not (expected_uploads / item["stored_filename"]).is_file()
            for item in receipt["documents"]
        ):
            raise RuntimeError("课程库文件不完整，请检查本地资料；不会覆盖或迁移已有索引")
        return receipt
    if any(path.exists() and any(path.iterdir()) for path in (expected_uploads, expected_chroma)):
        raise RuntimeError("目标目录已有资料但没有完整准备记录；拒绝覆盖或重复导入")

    manifest = load_manifest()
    sources = load_source_map(SOURCE_MAP_PATH, {d["filename"] for d in manifest["documents"]})
    validate_sources(manifest, sources)
    documents = []
    with TestClient(create_app()) as client:
        for alias in sorted(sources):
            with sources[alias].open("rb") as file:
                response = client.post("/api/upload", files={"file": (alias, file, "application/pdf")})
            response.raise_for_status()
            data = response.json()
            documents.append({"document_id": data["document_id"], "filename": data["filename"], "chunk_count": data["chunk_count"], **data["metadata"]})
            print(f"已导入 {alias}：{documents[-1]['chunk_count']} 个片段", flush=True)
    receipt = {"profile": profile_signature(), "documents": documents, "external_llm_calls": False}
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    receipt = prepare()
    print(f"初始资料回执已确认：{len(receipt['documents'])} 份初始文档；保留之后上传的文件和现有索引。")
