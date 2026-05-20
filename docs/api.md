# StudyMate RAG API

基础地址：`http://127.0.0.1:8000`

错误响应统一为：

```json
{
  "error": {
    "code": "unsupported_file_type",
    "message": "目前只支持上传 PDF 文件。",
    "details": {}
  }
}
```

## GET /health

用于确认 FastAPI 服务是否启动。

```bash
curl http://127.0.0.1:8000/health
```

响应：

```json
{
  "status": "ok",
  "service": "studymate-rag-api"
}
```

## POST /api/upload

上传一个 PDF 文件，系统会保存文件、解析页面文本、切分 chunk、生成 embedding，并写入 ChromaDB。

请求类型：`multipart/form-data`

字段：

- `file`: PDF 文件。

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@/path/to/course-note.pdf"
```

响应：

```json
{
  "document_id": "abc123",
  "filename": "course-note.pdf",
  "status": "indexed",
  "chunk_count": 12,
  "metadata": {
    "stored_filename": "abc123_course-note.pdf",
    "page_count": 5
  }
}
```

常见错误：

- `400 unsupported_file_type`: 上传文件不是 PDF。
- `400 bad_request`: PDF 无可解析文本、文件过大或 chunk 配置不合法。
- `502 embedding_failed`: BGE embedding 生成失败。

## POST /api/chat

基于已上传并索引的课程资料回答问题。

请求：

```json
{
  "question": "这份资料的核心概念是什么？",
  "top_k": 4
}
```

字段：

- `question`: 必填，不能是空白字符串。
- `top_k`: 可选，检索返回的 chunk 数量，范围 1 到 10，默认 4。

响应：

```json
{
  "answer": "回答内容",
  "sources": [
    {
      "document_id": "abc123",
      "filename": "course-note.pdf",
      "page": 2,
      "chunk_id": "0",
      "score": 0.18,
      "text": "引用片段",
      "metadata": {}
    }
  ]
}
```

常见错误：

- `422 validation_error`: 请求参数不合法，例如问题为空白字符串。
- `503 llm_not_configured`: 没有设置 `DEEPSEEK_API_KEY`，且没有兼容读取到 `OPENAI_API_KEY`。
- `502 llm_request_failed`: DeepSeek 调用失败。

## GET /api/documents

列出当前 ChromaDB 中已索引的文档。

```bash
curl http://127.0.0.1:8000/api/documents
```

响应：

```json
{
  "documents": [
    {
      "document_id": "abc123",
      "filename": "course-note.pdf",
      "chunk_count": 12,
      "created_at": null,
      "metadata": {
        "pages": [1, 2, 3],
        "page_count": 3,
        "indexed_at": "2026-05-20T00:00:00+00:00"
      }
    }
  ]
}
```

## DELETE /api/documents/{document_id}

删除指定文档的向量索引，并清理对应上传文件。

```bash
curl -X DELETE http://127.0.0.1:8000/api/documents/abc123
```

响应：

```json
{
  "document_id": "abc123",
  "status": "deleted",
  "message": "文档已删除。"
}
```
