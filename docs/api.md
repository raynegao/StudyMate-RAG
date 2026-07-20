# StudyMate RAG API 0.3.0

- 默认地址：`http://127.0.0.1:8000`
- 交互式文档：`http://127.0.0.1:8000/docs`

## 统一错误格式

```json
{
  "error": {
    "code": "invalid_pdf",
    "message": "PDF 文件已损坏或格式无效。",
    "details": {}
  }
}
```

未知异常只在服务端记录完整日志，客户端统一收到脱敏的 `internal_error`。

## GET /health

```json
{
  "status": "ok",
  "service": "studymate-rag-api"
}
```

## POST /api/upload

以 `multipart/form-data` 上传字段 `file`。成功状态码为 `201`。

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@output/pdf/studymate-demo-course.pdf"
```

```json
{
  "document_id": "624ccf423d3844c4b8a3636e4b06365b",
  "filename": "星际导航课程讲义.pdf",
  "status": "indexed",
  "chunk_count": 3,
  "metadata": {
    "stored_filename": "624ccf423d3844c4b8a3636e4b06365b_星际导航课程讲义.pdf",
    "page_count": 3
  }
}
```

文件会分块写入，并在写入过程中检查大小。任何解析或索引失败都会清理本次上传残留。

常见错误：

- `400 unsupported_file_type`：不是 PDF
- `400 invalid_pdf`：PDF 损坏或格式无效
- `413 upload_too_large`：超过 `STUDYMATE_MAX_UPLOAD_SIZE_MB`
- `422 encrypted_pdf`：PDF 已加密
- `422 pdf_no_extractable_text`：空白、无文本或纯扫描 PDF
- `502 embedding_failed`：BGE 初始化或向量生成失败
- `503 vector_store_unavailable`：ChromaDB 不可用

## POST /api/chat

```json
{
  "question": "蓝色令牌的有效期是多少？",
  "top_k": 4
}
```

- `question`：必填，去除首尾空白后不能为空
- `top_k`：可选，范围 1 到 10；省略时使用 `STUDYMATE_TOP_K`

```json
{
  "answer": "蓝色令牌的有效期为三个星港周期。[S1]",
  "sources": [
    {
      "citation_id": "S1",
      "document_id": "624ccf423d3844c4b8a3636e4b06365b",
      "filename": "星际导航课程讲义.pdf",
      "page": 2,
      "chunk_id": "624ccf423d3844c4b8a3636e4b06365b:p2:c0",
      "distance": 0.733,
      "cited": true,
      "text": "引用片段",
      "metadata": {}
    }
  ]
}
```

`distance` 是 Chroma 返回的向量距离，通常越小越相关，不是相似度百分比。`cited=true` 表示答案文本实际包含对应的 `[S1]` 标记；其余来源只是检索候选。

空知识库会直接返回友好提示和空来源列表，不加载 BGE，也不调用 DeepSeek。

常见错误：

- `422 validation_error`：问题或 `top_k` 不合法
- `502 embedding_failed`：问题向量生成失败
- `502 llm_request_failed`：DeepSeek 请求失败
- `503 llm_not_configured`：未设置 `DEEPSEEK_API_KEY`
- `503 vector_store_unavailable`：ChromaDB 不可用

## GET /api/documents

```json
{
  "documents": [
    {
      "document_id": "624ccf423d3844c4b8a3636e4b06365b",
      "filename": "星际导航课程讲义.pdf",
      "chunk_count": 3,
      "created_at": null,
      "metadata": {
        "pages": [1, 2, 3],
        "page_count": 3,
        "indexed_at": "2026-07-20T07:34:00+00:00"
      }
    }
  ]
}
```

## DELETE /api/documents/{document_id}

`document_id` 必须是 32 位十六进制字符串。合法但不存在的 ID 返回 `200` 和 `not_found`，便于幂等调用；通配符、路径字符和其他格式返回 `400 invalid_document_id`，且不会触碰文件或向量。

```json
{
  "document_id": "624ccf423d3844c4b8a3636e4b06365b",
  "status": "deleted",
  "message": "文档已删除。"
}
```

删除成功时会同时移除对应上传文件和 Chroma 向量。
