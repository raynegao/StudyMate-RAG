# StudyMate RAG Architecture

## 当前阶段

Phase 2 目标是把 Phase 1 的 RAG 后端做成可运行、可展示、可测试的本地工程化版本。本阶段包含 FastAPI 后端、Streamlit 前端、统一错误响应、日志、配置和 API contract 测试。

本阶段不加入 SQLite/PostgreSQL，也不做 Docker、Hybrid Search、Rerank、Query Rewrite、多轮对话或 Conversation Memory。

## 模块边界

```text
Streamlit frontend
  |
  | HTTP
  v
FastAPI app (backend/app/main.py)
  |
  +-- API routers (backend/app/api/)
  |     +-- /health
  |     +-- /api/upload
  |     +-- /api/chat
  |     +-- /api/documents
  |
  +-- Core (backend/app/core/)
  |     +-- runtime settings
  |     +-- logging
  |     +-- unified error responses
  |
  +-- Models (backend/app/models/)
  |     +-- Pydantic request and response schemas
  |
  +-- Services (backend/app/services/)
        +-- PDF parsing
        +-- Text chunking
        +-- BGE local embeddings
        +-- DeepSeek chat completion
        +-- ChromaDB persistent vector store
        +-- RAG prompt assembly
```

## 本地数据流

### 上传 PDF

1. Streamlit 或其他客户端调用 `POST /api/upload` 上传 PDF。
2. FastAPI 校验文件类型和大小。
3. `document_service` 保存原始 PDF 到 `data/uploads/`。
4. `pdf_parser` 提取每页文本。
5. `chunking` 将页面文本切分为 chunk。
6. `embedding_service` 使用本地 BGE 模型生成向量。
7. `vector_store` 将 chunk、metadata 和 embedding 写入 `data/chroma_db/`。
8. API 返回 `document_id`、文件名和 chunk 数。

### 问答

1. 客户端调用 `POST /api/chat`，传入 `question` 和可选 `top_k`。
2. 系统为问题生成 embedding。
3. `vector_store` 从 ChromaDB 检索相关 chunk。
4. `rag_service` 构造只基于课程资料回答的 prompt。
5. `llm_service` 调用 DeepSeek 生成答案。
6. API 返回 `answer` 和 `sources`，前端展示引用来源。

### 文档管理

1. `GET /api/documents` 从 Chroma metadata 聚合文档列表。
2. `DELETE /api/documents/{document_id}` 删除对应 Chroma entries，并清理 `data/uploads/` 中同一 document_id 前缀的 PDF 文件。
3. 当前不维护独立数据库，避免引入迁移和一致性问题。

## 运行时配置

配置来源是环境变量，示例见 `.env.example`。

关键配置：

- `DEEPSEEK_API_KEY`: 推荐，DeepSeek chat completion 调用需要。
- `OPENAI_API_KEY`: 兼容旧变量名；如果这里放的是 DeepSeek key，系统也会读取。
- `DEEPSEEK_BASE_URL`: 可选，默认 `https://api.deepseek.com`。
- `STUDYMATE_API_BASE_URL`: Streamlit 前端调用 FastAPI 的地址。
- `STUDYMATE_UPLOAD_DIR`: 上传 PDF 保存目录，默认 `data/uploads`。
- `STUDYMATE_CHROMA_DIR`: ChromaDB 持久化目录，默认 `data/chroma_db`。
- `STUDYMATE_LOCAL_EMBEDDING_MODEL`: 本地 embedding 模型，默认 `BAAI/bge-small-zh-v1.5`。
- `STUDYMATE_LLM_MODEL`: DeepSeek 模型，默认 `deepseek-v4-flash`。
- `STUDYMATE_MAX_UPLOAD_SIZE_MB`: 单个上传文件大小限制，默认 25。

## 持久化和版本控制

`data/uploads/` 和 `data/chroma_db/` 是本地运行数据目录。仓库只保留 `.gitkeep` 占位文件，不提交真实上传文件、向量索引、缓存或 API Key。
