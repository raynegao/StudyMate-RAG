# StudyMate RAG Demo Guide

这份文档用于录制 Demo 视频、现场展示或面试讲解。

## 准备

1. 准备一份可公开展示的课程 PDF，最好包含清晰页码和概念说明。
2. 确认 `.env` 或 `.env.local` 中有有效的 `DEEPSEEK_API_KEY`。
3. 确认本地没有需要保密的上传资料留在 `data/uploads/`。

## 本地演示流程

### 1. 启动后端

```bash
source .venv/bin/activate
set -a && source .env && set +a
scripts/run_backend.sh
```

打开：

```text
http://127.0.0.1:8000/docs
```

可以先展示 `/health` 和 `/api/documents`。

### 2. 启动前端

另开终端：

```bash
source .venv/bin/activate
set -a && source .env && set +a
scripts/run_frontend.sh
```

打开：

```text
http://127.0.0.1:8501
```

### 3. 上传 PDF

在 Streamlit 侧边栏选择 PDF，点击“上传并索引”。

讲解重点：

- 系统先保存文件到 `data/uploads/`。
- 然后逐页解析文本。
- 接着切成带 metadata 的 chunks。
- 使用本地 BGE 模型生成 embedding。
- 最后写入 ChromaDB。

### 4. 提问

建议问题：

```text
这份资料主要讲了哪些核心概念？
```

或针对 PDF 内容问一个更具体的问题。

讲解重点：

- 用户问题也会生成 embedding。
- 系统从 ChromaDB 检索 top-k 相关 chunks。
- LLM 只基于检索到的课程资料回答。
- 回答下方展示引用来源，包括文件名、页码、chunk 和原文片段。

### 5. 展示文档管理

侧边栏会展示已索引文档。可以演示删除文档，说明系统会删除对应向量索引和上传文件。

## Docker 演示流程

```bash
docker compose --env-file .env up --build
```

如果使用 `.env.local`：

```bash
docker compose --env-file .env.local up --build
```

访问：

- FastAPI: `http://127.0.0.1:8000`
- Streamlit: `http://127.0.0.1:8501`

停止：

```bash
docker compose down
```

## Demo 讲解词

可以按这个顺序讲：

1. StudyMate RAG 是一个面向课程资料的智能问答系统。
2. 它不是让模型凭空回答，而是先从用户上传的 PDF 中检索相关片段。
3. 后端使用 FastAPI 暴露上传、问答和文档管理接口。
4. RAG pipeline 包含 PDF 解析、chunking、本地 BGE embedding、ChromaDB 检索和 DeepSeek Chat 生成回答。
5. 前端使用 Streamlit，方便快速展示上传、提问和引用来源。
6. 项目支持本地运行和 Docker Compose 一键启动，适合作为 AI 应用工程项目展示。

## 录制建议

- 先清空无关文档，避免展示私人资料。
- 录屏时打开浏览器左侧前端、右侧终端日志。
- 展示一次上传、一次提问、一次引用来源展开即可。
- 不要展示 `.env` 文件或 API Key。
