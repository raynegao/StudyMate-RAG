from __future__ import annotations

from dataclasses import replace
from io import BytesIO

from app.core.config import settings
from app.core.errors import EmbeddingServiceError, VectorStoreError


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "studymate-rag-api"}


def test_openapi_reports_release_version(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["version"] == "0.3.0"


def test_upload_rejects_non_pdf(client):
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_blank_question_returns_validation_error(client):
    response = client.post("/api/chat", json={"question": "   ", "top_k": 4})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_upload_contract_with_mocked_service(client, monkeypatch):
    async def fake_index_uploaded_pdf(upload_file):
        return {
            "document_id": "doc-1",
            "filename": upload_file.filename,
            "status": "indexed",
            "chunk_count": 2,
            "page_count": 1,
        }

    monkeypatch.setattr(
        "app.services.document_service.index_uploaded_pdf",
        fake_index_uploaded_pdf,
    )

    response = client.post(
        "/api/upload",
        files={"file": ("course.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document_id"] == "doc-1"
    assert payload["filename"] == "course.pdf"
    assert payload["chunk_count"] == 2
    assert payload["metadata"]["page_count"] == 1


def test_upload_preserves_unicode_filename(client, monkeypatch):
    async def fake_index_uploaded_pdf(upload_file):
        return {
            "document_id": "a" * 32,
            "filename": upload_file.filename,
            "chunk_count": 1,
        }

    monkeypatch.setattr(
        "app.services.document_service.index_uploaded_pdf",
        fake_index_uploaded_pdf,
    )

    response = client.post(
        "/api/upload",
        files={"file": ("机器学习课程.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "机器学习课程.pdf"


def test_chat_contract_with_mocked_service(client, monkeypatch):
    def fake_answer_question(question, top_k):
        return {
            "answer": f"answer: {question}",
            "sources": [
                {
                    "citation_id": "S1",
                    "document_id": "doc-1",
                    "filename": "course.pdf",
                    "page_number": 3,
                    "chunk_index": 0,
                    "distance": 0.12,
                    "cited": True,
                    "text": "source text",
                }
            ],
        }

    monkeypatch.setattr("app.services.rag_service.answer_question", fake_answer_question)

    response = client.post("/api/chat", json={"question": "讲讲重点", "top_k": 3})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "answer: 讲讲重点"
    assert payload["sources"][0]["page"] == 3
    assert payload["sources"][0]["chunk_id"] == "0"
    assert payload["sources"][0]["citation_id"] == "S1"
    assert payload["sources"][0]["distance"] == 0.12
    assert payload["sources"][0]["cited"] is True
    assert "score" not in payload["sources"][0]


def test_chat_without_top_k_delegates_environment_default(client, monkeypatch):
    received = {}

    def fake_answer_question(question, top_k):
        received["top_k"] = top_k
        return {"answer": question, "sources": []}

    monkeypatch.setattr("app.services.rag_service.answer_question", fake_answer_question)

    response = client.post("/api/chat", json={"question": "讲讲重点"})

    assert response.status_code == 200
    assert received["top_k"] is None


def test_list_documents_contract_with_mocked_service(client, monkeypatch):
    def fake_list_indexed_documents():
        return [
            {
                "document_id": "doc-1",
                "filename": "course.pdf",
                "chunk_count": 2,
                "indexed_at": "2026-05-20T00:00:00+00:00",
                "pages": [1, 2],
            }
        ]

    monkeypatch.setattr(
        "app.services.document_service.list_indexed_documents",
        fake_list_indexed_documents,
    )

    response = client.get("/api/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["documents"][0]["document_id"] == "doc-1"
    assert payload["documents"][0]["metadata"]["pages"] == [1, 2]


def test_delete_missing_document_returns_not_found_status(client, monkeypatch):
    def fake_delete_indexed_document(document_id):
        return {
            "document_id": document_id,
            "deleted": False,
            "deleted_from_index": False,
            "deleted_files": [],
            "message": "未找到该文档。",
        }

    monkeypatch.setattr(
        "app.services.document_service.delete_indexed_document",
        fake_delete_indexed_document,
    )

    document_id = "f" * 32
    response = client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document_id
    assert payload["status"] == "not_found"


def test_delete_rejects_dangerous_document_id_before_service(client, monkeypatch):
    called = False

    def fake_delete_indexed_document(document_id):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.services.document_service.delete_indexed_document",
        fake_delete_indexed_document,
    )

    response = client.delete("/api/documents/%2A")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_document_id"
    assert called is False


def test_upload_too_large_returns_413_and_cleans_partial_file(
    client,
    monkeypatch,
    tmp_path,
):
    from app.services import document_service

    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(
        document_service,
        "settings",
        replace(settings, upload_dir=upload_dir, max_upload_size_mb=0),
    )

    response = client.post(
        "/api/upload",
        files={"file": ("large.pdf", b"too large", "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"
    assert list(upload_dir.iterdir()) == []


def test_corrupt_pdf_returns_typed_json_error_and_cleans_file(
    client,
    monkeypatch,
    tmp_path,
):
    from app.services import document_service

    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(
        document_service,
        "settings",
        replace(settings, upload_dir=upload_dir),
    )

    response = client.post(
        "/api/upload",
        files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "invalid_pdf"
    assert list(upload_dir.iterdir()) == []


def test_embedding_failure_is_stable_and_does_not_leak_details(client, monkeypatch):
    def fake_answer_question(question, top_k):
        raise EmbeddingServiceError("private model path")

    monkeypatch.setattr("app.services.rag_service.answer_question", fake_answer_question)

    response = client.post("/api/chat", json={"question": "重点是什么？"})

    assert response.status_code == 502
    payload = response.json()
    assert payload["error"]["code"] == "embedding_failed"
    assert "private model path" not in response.text


def test_unknown_service_error_is_generic_and_does_not_leak_details(
    client,
    monkeypatch,
):
    def fake_answer_question(question, top_k):
        raise RuntimeError("secret-token-value")

    monkeypatch.setattr("app.services.rag_service.answer_question", fake_answer_question)

    response = client.post("/api/chat", json={"question": "重点是什么？"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert "secret-token-value" not in response.text


def test_vector_store_error_has_stable_api_mapping(client, monkeypatch):
    def fake_list_indexed_documents():
        raise VectorStoreError("private database path")

    monkeypatch.setattr(
        "app.services.document_service.list_indexed_documents",
        fake_list_indexed_documents,
    )

    response = client.get("/api/documents")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "vector_store_unavailable"
    assert "private database path" not in response.text
