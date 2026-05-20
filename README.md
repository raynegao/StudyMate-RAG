# StudyMate RAG

StudyMate RAG 是一个课程资料智能问答系统。当前 Phase 2 版本提供 FastAPI 后端和 Streamlit 前端：上传 PDF、解析并切分文本、写入本地 ChromaDB 向量库，然后基于已上传资料回答问题并返回引用来源。

当前模型路线：

- Embedding: 本地 `sentence-transformers` + `BAAI/bge-small-zh-v1.5`
- LLM: DeepSeek Chat API
- Vector store: ChromaDB 本地持久化目录

## 本地运行

### 1. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 3. 设置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```bash
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

如果你已经把 DeepSeek key 写在 `OPENAI_API_KEY` 这个变量名下，当前代码也会兼容读取；后续更推荐改成 `DEEPSEEK_API_KEY`，语义更清楚。

本地运行前加载 `.env`：

```bash
set -a
source .env
set +a
```

### 4. 启动 FastAPI 后端

```bash
PYTHONPATH=backend uvicorn app.main:app --reload
```

服务默认运行在 `http://127.0.0.1:8000`，交互式 API 文档在 `http://127.0.0.1:8000/docs`。

### 5. 启动 Streamlit 前端

另开一个终端，激活同一个虚拟环境后运行：

```bash
streamlit run frontend/streamlit_app.py
```

前端默认连接 `http://127.0.0.1:8000`。如需改后端地址：

```bash
STUDYMATE_API_BASE_URL=http://127.0.0.1:8000 streamlit run frontend/streamlit_app.py
```

## 测试与验证

```bash
.venv/bin/python -m compileall backend tests frontend
.venv/bin/python -m pytest -q
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/documents
```

首次上传 PDF 时会自动下载 BGE 模型到本地模型缓存。真实问答需要有效的 `DEEPSEEK_API_KEY`。

## API 调用示例

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 上传 PDF

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@/path/to/course-note.pdf"
```

### 基于资料提问

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"这份资料的核心概念是什么？","top_k":4}'
```

响应包含 `answer` 和 `sources`。`sources` 用于展示回答引用的文件、页码、chunk 和原文片段。

## 当前目录

```text
backend/app/main.py          FastAPI 应用入口
backend/app/api/             health、upload、chat、documents 接口
backend/app/core/            配置、日志、统一错误处理
backend/app/services/        PDF 解析、chunk、embedding、ChromaDB、RAG 流程
backend/app/models/          Pydantic 请求和响应模型
frontend/streamlit_app.py    Streamlit 前端工作台
tests/                       API contract 和错误处理测试
data/uploads/                本地上传文件目录，不提交真实文件
data/chroma_db/              ChromaDB 持久化目录，不提交索引数据
docs/                        架构和 API 文档
```

## Phase 2 边界

- 本阶段做本地可运行、可展示、可测试的工程化版本。
- 不引入 SQLite/PostgreSQL；文档列表继续从 Chroma metadata 聚合。
- 不做 Phase 3 的 Hybrid Search、Rerank、Query Rewrite、多轮对话或 Conversation Memory。
- 不要把 `.env`、API Key、上传文件、ChromaDB 索引或虚拟环境提交到版本控制。
