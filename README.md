# StudyMate RAG

StudyMate RAG 是一个课程资料智能问答系统。当前阶段提供 FastAPI 后端 MVP：上传 PDF、解析并切分文本、写入本地 ChromaDB 向量库，然后基于已上传资料回答问题并返回引用来源。

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

复制示例配置：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```bash
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

如果你已经把 DeepSeek key 写在 `OPENAI_API_KEY` 这个变量名下，当前代码也会兼容读取；只是后续更推荐改成 `DEEPSEEK_API_KEY`，语义更清楚。

本项目当前使用本地 BGE 模型生成 embedding，并使用 DeepSeek 生成答案。首次上传 PDF 时会自动下载 `BAAI/bge-small-zh-v1.5` 到本地模型缓存。本地运行时需要把 `.env` 加载到当前 shell：

```bash
set -a
source .env
set +a
```

### 4. 启动 FastAPI

```bash
PYTHONPATH=backend uvicorn app.main:app --reload
```

服务默认运行在 `http://127.0.0.1:8000`，交互式 API 文档在 `http://127.0.0.1:8000/docs`。

## API 调用示例

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

预期响应：

```json
{
  "status": "ok",
  "service": "studymate-rag-api"
}
```

### 上传 PDF

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@/path/to/course-note.pdf"
```

上传成功后会返回 `document_id`、文件名和 chunk 数量。PDF 原文件会保存到 `data/uploads/`，向量索引会写入 `data/chroma_db/`。

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
backend/app/core/config.py   环境变量配置
backend/app/services/        PDF 解析、chunk、embedding、ChromaDB、RAG 流程
backend/app/models/          Pydantic 请求和响应模型
data/uploads/                本地上传文件目录，不提交真实文件
data/chroma_db/              ChromaDB 持久化目录，不提交索引数据
docs/                        架构和 API 文档
```

## 注意事项

- 不要把 `.env`、API Key、上传文件或 ChromaDB 索引提交到版本控制。
- 当前第一阶段只补本地运行依赖和说明，不包含 Docker 或 docker-compose。
- `/api/upload` 会使用本地 BGE embedding 模型；`/api/chat` 会调用 DeepSeek chat 接口，需要有效的 `DEEPSEEK_API_KEY`。
