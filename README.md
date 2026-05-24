# StudyMate RAG

StudyMate RAG 是一个课程资料智能问答系统。用户上传课程 PDF 后，系统会解析文本、切分 chunk、使用本地 BGE 模型生成 embedding、写入 ChromaDB，并通过 DeepSeek Chat 基于检索到的资料片段回答问题，同时返回引用来源。

当前展示版目标：本地可运行、Docker 可启动、接口可测试、前端可演示、项目材料可写进简历。

## 功能

- PDF 上传、文本解析和 chunking
- 本地 `BAAI/bge-small-zh-v1.5` embedding
- ChromaDB 本地持久化向量库
- DeepSeek Chat 生成基于资料的回答
- FastAPI 后端接口和交互式 `/docs`
- Streamlit 文件上传、问答和引用展示
- API contract 测试、Docker Compose 和演示文档

## 技术栈

- Backend: FastAPI, Pydantic, Uvicorn
- RAG: sentence-transformers, ChromaDB, DeepSeek Chat API
- Frontend: Streamlit
- Tests: pytest, FastAPI TestClient
- Deployment: Docker, Docker Compose

## 本地运行

### 1. 创建环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```bash
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

如果本地仍把 DeepSeek key 写在 `OPENAI_API_KEY` 里，当前代码也兼容读取；推荐使用 `DEEPSEEK_API_KEY`，语义更清楚。

加载配置：

```bash
set -a
source .env
set +a
```

### 3. 启动后端

```bash
scripts/run_backend.sh
```

开发时需要自动重载：

```bash
STUDYMATE_BACKEND_RELOAD=true scripts/run_backend.sh
```

后端默认地址：`http://127.0.0.1:8000`

API 文档：`http://127.0.0.1:8000/docs`

### 4. 启动前端

另开一个终端，激活同一个虚拟环境并加载 `.env` 后运行：

```bash
scripts/run_frontend.sh
```

前端默认地址：`http://127.0.0.1:8501`

## Docker Compose 运行

使用 `.env`：

```bash
docker compose up --build
```

如果你使用的是本地私密文件 `.env.local`：

```bash
docker compose --env-file .env.local up --build
```

服务地址：

- FastAPI: `http://127.0.0.1:8000`
- Streamlit: `http://127.0.0.1:8501`

首次上传 PDF 时，容器会下载 BGE embedding 模型。Compose 使用 `studymate_hf_cache` volume 缓存模型，后续启动会更快。

停止服务：

```bash
docker compose down
```

## 测试与验证

运行静态编译检查和 API contract 测试：

```bash
scripts/test.sh
```

后端启动后做 smoke check：

```bash
scripts/smoke_api.sh
```

等价手动命令：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/documents
```

## API 示例

上传 PDF：

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@/path/to/course-note.pdf"
```

基于资料提问：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"这份资料的核心概念是什么？","top_k":4}'
```

列出文档：

```bash
curl http://127.0.0.1:8000/api/documents
```

删除文档：

```bash
curl -X DELETE http://127.0.0.1:8000/api/documents/{document_id}
```

## 展示流程

1. 启动后端和 Streamlit，打开 `http://127.0.0.1:8501`。
2. 在侧边栏上传一份课程 PDF。
3. 等待系统完成解析、切分、embedding 和 ChromaDB 入库。
4. 在主界面输入课程问题。
5. 查看回答以及引用来源中的文件名、页码、chunk 和原文片段。
6. 演示结束后可在侧边栏删除文档。

更详细的演示脚本见 [docs/demo.md](docs/demo.md)。

## 项目结构

```text
backend/app/main.py          FastAPI 应用入口
backend/app/api/             health、upload、chat、documents 接口
backend/app/core/            配置、日志、统一错误处理
backend/app/services/        PDF 解析、chunk、embedding、ChromaDB、RAG 流程
backend/app/models/          Pydantic 请求和响应模型
frontend/streamlit_app.py    Streamlit 前端工作台
scripts/                     本地启动、测试和 smoke check 脚本
data/uploads/                本地上传文件目录，不提交真实文件
data/chroma_db/              ChromaDB 持久化目录，不提交索引数据
docs/                        架构、API、演示和简历材料
```

## 常见问题

- `llm_not_configured`: 没有加载 `DEEPSEEK_API_KEY`。确认 `.env` 或 `.env.local` 已填写，并在启动前加载。
- 首次上传很慢：本地或容器第一次会下载 BGE 模型，这是预期行为。
- 没有引用来源：当前知识库没有可检索内容，先上传并索引 PDF。
- Docker 中前端连不上后端：Compose 内部使用 `STUDYMATE_API_BASE_URL=http://backend:8000`，不要在容器内写 `127.0.0.1:8000`。

## 当前边界

展示版不包含用户登录、多知识库、Hybrid Search、Rerank、Query Rewrite、多轮对话、Conversation Memory 或云部署。这些属于后续增强阶段。
