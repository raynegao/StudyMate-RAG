from __future__ import annotations

from io import BytesIO


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "studymate-rag-api"}


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


def test_chat_contract_with_mocked_service(client, monkeypatch):
    def fake_answer_question(question, top_k):
        return {
            "answer": f"answer: {question}",
            "sources": [
                {
                    "document_id": "doc-1",
                    "filename": "course.pdf",
                    "page_number": 3,
                    "chunk_index": 0,
                    "distance": 0.12,
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

    response = client.delete("/api/documents/missing")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == "missing"
    assert payload["status"] == "not_found"
