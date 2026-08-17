# StudyMate RAG 开发约定

## 项目目标

StudyMate RAG 为课程 PDF 提供本地向量检索和带引用的问答能力。当前版本只维护稳定展示闭环，不提前加入 OCR、Hybrid Search、Rerank、Query Rewrite、多轮记忆或多知识库。

## 技术栈

- Python 3.12、FastAPI、Pydantic、Uvicorn
- sentence-transformers、`BAAI/bge-small-zh-v1.5`、ChromaDB
- DeepSeek Chat API
- Streamlit
- uv、pytest、Ruff、coverage、Docker Compose

## 模块边界

- `backend/app/api/`：HTTP 路由、请求校验和响应转换
- `backend/app/core/`：配置、日志和统一错误处理
- `backend/app/services/`：PDF 解析、chunking、embedding、向量库和 RAG 流程
- `backend/app/models/`：Pydantic schema
- `frontend/streamlit_app.py`：页面状态、上传、问答和文档管理
- `tests/`：API contract、服务层和前端辅助逻辑测试
- `scripts/`：启动、测试、smoke 和公开样例生成脚本
- `evaluation/`：公开虚构基准、标准文档/页码和答案关键词标注
- `output/evaluation/`、`output/e2e/`：可公开、可机读的量化与真实栈验收证据

## 常用命令

```bash
uv venv --python 3.12
uv pip sync --python .venv/bin/python --torch-backend cpu backend/requirements-dev.txt
scripts/test.sh
scripts/run_backend.sh
scripts/run_frontend.sh
scripts/smoke_api.sh
.venv/bin/python scripts/generate_evaluation_assets.py
.venv/bin/python scripts/evaluate_rag.py
.venv/bin/python scripts/run_docker_e2e.py
docker compose --env-file .env.local up --build
```

## 修改要求

- 修改前先阅读相关模块、README、依赖输入文件和现有测试。
- 保持 API 层与服务层分离，不在路由中实现模型或数据库细节。
- 同步重任务必须离开 FastAPI 事件循环。
- 客户端只接收稳定、脱敏的 JSON 错误，完整异常只写服务日志。
- API 行为变化时同步更新测试、`docs/api.md` 和 README。
- 依赖变更先修改 `requirements.in` 或 `requirements-dev.in`，再重新生成锁文件。
- 提交前运行 `scripts/test.sh`、Compose 配置检查和 Dockerfile 检查。
- 评测集或检索逻辑变化时重新生成公开 PDF、量化结果和 `docs/evaluation.md`；真实栈变化时重跑隔离 Docker E2E。

## 数据与安全

- 不提交 API Key、`.env`、`.env.local`、上传资料、Chroma 数据、模型缓存或虚拟环境。
- 不读取、迁移、重建或对外发送现有私人索引内容。
- 删除操作只能接受 32 位十六进制 `document_id`，并同时处理对应上传文件和向量。
- 演示和外部模型验收只使用 `output/pdf/` 中的公开虚构资料。
