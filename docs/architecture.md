# StudyMate RAG Architecture

## 当前阶段

第一阶段目标是让后端可以在本地直接运行，并把运行依赖、环境变量和 API 调用方式记录清楚。本阶段不加入 Docker 或 docker-compose。

## 模块边界

```text
Client
  |
  v
FastAPI app (backend/app/main.py)
  |
  +-- API routers (backend/app/api/)
  |     +-- /health
  |     +-- /api/upload
  |     +-- /api/chat
  |     +-- /api/documents
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

1. 客户端调用 `POST /api/upload` 上传 PDF。
2. FastAPI 校验文件类型。
3. `document_service` 保存原始 PDF 到 `data/uploads/`。
4. `pdf_parser` 提取每页文本。
5. `chunking` 将页面文本切分为 chunk。
6. `embedding_service` 使用本地 BGE 模型生成向量。
7. `vector_store` 将 chunk、metadata 和 embedding 写入 `data/chroma_db/`。

### 问答

1. 客户端调用 `POST /api/chat`，传入 `question` 和可选 `top_k`。
2. 系统为问题生成 embedding。
3. `vector_store` 从 ChromaDB 检索相关 chunk。
4. `rag_service` 构造只基于课程资料回答的 prompt。
5. `llm_service` 调用 DeepSeek 生成答案。
6. API 返回 `answer` 和 `sources`，用于前端展示引用来源。

## 运行时配置

配置来源是环境变量，示例见 `.env.example`。

关键配置：

- `DEEPSEEK_API_KEY`: 推荐，DeepSeek chat completion 调用需要。
- `OPENAI_API_KEY`: 兼容旧变量名；如果这里放的是 DeepSeek key，系统也会读取。
- `DEEPSEEK_BASE_URL`: 可选，默认 `https://api.deepseek.com`。
- `STUDYMATE_UPLOAD_DIR`: 上传 PDF 保存目录，默认 `data/uploads`。
- `STUDYMATE_CHROMA_DIR`: ChromaDB 持久化目录，默认 `data/chroma_db`。
- `STUDYMATE_LOCAL_EMBEDDING_MODEL`: 本地 embedding 模型，默认 `BAAI/bge-small-zh-v1.5`。
- `STUDYMATE_LLM_MODEL`: DeepSeek 模型，默认 `deepseek-v4-flash`。

## 持久化和版本控制

`data/uploads/` 和 `data/chroma_db/` 是本地运行数据目录。仓库只保留 `.gitkeep` 占位文件，不提交真实上传文件、向量索引、缓存或 API Key。

## 后续 DevOps 工作

当前阶段只覆盖本地运行。后续阶段可以继续补：

- 测试命令和 CI 基础配置。
- Dockerfile 和 docker-compose。
- 生产部署环境变量说明。
- Demo 截图、架构图和展示材料。
