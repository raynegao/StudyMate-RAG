# StudyMate RAG API

基础地址：`http://127.0.0.1:8000`

## GET /health

用于确认 FastAPI 服务是否启动。

### 示例

```bash
curl http://127.0.0.1:8000/health
```

### 响应

```json
{
  "status": "ok",
  "service": "studymate-rag-api"
}
```

## POST /api/upload

上传一个 PDF 文件，系统会保存文件、解析页面文本、切分 chunk、生成 embedding，并写入 ChromaDB。

### 请求

Content-Type: `multipart/form-data`

字段：

- `file`: PDF 文件。

### 示例

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@/path/to/course-note.pdf"
```

### 响应

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

## POST /api/chat

基于已上传并索引的课程资料回答问题。

### 请求

```json
{
  "question": "这份资料的核心概念是什么？",
  "top_k": 4
}
```

字段：

- `question`: 必填，用户问题。
- `top_k`: 可选，检索返回的 chunk 数量，范围 1 到 10，默认 4。

### 示例

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"这份资料的核心概念是什么？","top_k":4}'
```

### 响应

```json
{
  "answer": "回答内容",
  "sources": [
    {
      "document_id": "abc123",
      "filename": "course-note.pdf",
      "page": 2,
      "chunk_id": "abc123-2-0",
      "score": 0.18,
      "text": "引用片段",
      "metadata": {}
    }
  ]
}
```

## GET /api/documents

列出当前 ChromaDB 中已索引的文档。

### 示例

```bash
curl http://127.0.0.1:8000/api/documents
```

## DELETE /api/documents/{document_id}

删除指定文档的向量索引，并清理对应上传文件。

### 示例

```bash
curl -X DELETE http://127.0.0.1:8000/api/documents/abc123
```

## 常见错误

- `400 Only PDF uploads are supported.`：上传的文件不是 PDF。
- `500 缺少 DEEPSEEK_API_KEY 环境变量`：没有设置 DeepSeek API Key，且没有兼容读取到 `OPENAI_API_KEY`。
- `500 question 不能为空。`：`/api/chat` 的问题为空字符串。
