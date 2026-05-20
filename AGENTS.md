# StudyMate RAG 项目协作说明

## 项目目标

StudyMate RAG 是一个课程资料智能问答系统，目标是做成可运行、可部署、可展示的 AI 应用项目，用于港新 AI 硕士申请、AI 应用开发/RAG/Agent 实习简历和项目作品集。

核心能力：用户上传课程资料后，系统解析文档、切分文本、生成向量索引，并支持基于资料内容问答，同时返回引用来源。

## 技术栈

- Backend: Python, FastAPI, Pydantic, Uvicorn
- RAG: LangChain, ChromaDB, OpenAI API/DeepSeek API, Embedding Model
- Frontend: Streamlit
- Storage: 本地文件系统, SQLite/PostgreSQL, ChromaDB 持久化目录
- Deployment: Docker, Docker Compose

## 推荐目录

- `backend/app/main.py`: FastAPI 入口
- `backend/app/api/`: 上传、问答、文档管理接口
- `backend/app/core/`: 配置、安全等基础模块
- `backend/app/services/`: 文档解析、切分、embedding、向量库、RAG 流程
- `backend/app/models/`: Pydantic 数据模型
- `frontend/streamlit_app.py`: Streamlit 前端
- `data/uploads/`: 上传文件目录
- `data/chroma_db/`: ChromaDB 持久化目录
- `docs/`: 架构和 API 文档

## 开发阶段

1. MVP：PDF 上传、文本解析、chunk、embedding、写入 ChromaDB、问答并返回来源。
2. 工程化：FastAPI 后端、Streamlit 前端、多文档管理、引用展示、错误处理、日志、配置管理。
3. 增强 RAG：Hybrid Search、Rerank、Query Rewrite、多轮对话、Conversation Memory、多知识库切换。
4. 部署展示：Docker、Docker Compose、README、架构图、Demo 截图/视频、简历描述。

## 常用命令

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
set -a && source .env && set +a
PYTHONPATH=backend uvicorn app.main:app --reload
streamlit run frontend/streamlit_app.py
.venv/bin/python -m compileall backend tests frontend
.venv/bin/python -m pytest -q
```

当前 Phase 2 不包含 Docker 或 docker-compose。

## 协作偏好

- 默认用中文沟通。
- 优先小步推进 MVP，不一次性堆太多复杂代码。
- 每个模块先讲清原理，再写代码，再解释关键实现。
- 代码要适合初学者理解，但目录和边界保持工程化。
- 做代码任务前先阅读项目结构、README、依赖清单和测试配置。
- 能运行测试、lint、启动检查或最小验证时要主动验证。
- 最后简短说明改了什么、验证结果和剩余风险。

## 多 Agent 工作流

本项目采用 Codex 多 Agent / Subagents 工作流，但必须按阶段推进，不能所有 Agent 同时写代码。

### Agent 分工

- Project Architect Agent：设计整体架构、规划目录结构、确定模块边界、维护 `AGENTS.md`，避免项目越做越乱。
- Backend API Agent：负责 FastAPI 后端、上传/问答/文档接口、请求参数校验、错误处理和 Pydantic schemas。
- RAG Pipeline Agent：负责 PDF 解析、chunking、embedding、ChromaDB、检索、prompt 构造、LLM 回答和引用来源返回。
- Frontend Agent：负责 Streamlit 前端、文件上传、问答界面、答案展示、引用来源展示和文档列表展示。
- Testing & Debugging Agent：负责单元测试、接口测试、最小可运行测试和 bug 检查。
- DevOps Agent：负责 Dockerfile、docker-compose.yml、`.env.example`、requirements、启动脚本和 README 运行说明。

### 执行顺序

1. 先由 Project Architect Agent 输出架构、目录、模块边界和接口契约。
2. 用户确认后，Backend API Agent 和 RAG Pipeline Agent 才能开始 MVP 开发。
3. 后端接口稳定后，Frontend Agent 才能开发 Streamlit 前端。
4. 每完成一个模块后，由 Testing & Debugging Agent 做最小验证。
5. DevOps Agent 最后负责容器化、环境示例和运行说明。

### 确认规则

- 初始化阶段只允许修改项目说明、规划文档、`AGENTS.md`、README 草案或目录规划，不直接写业务代码。
- 进入代码开发前，必须先给出本阶段要改的文件清单，并等待用户明确确认。
- 每个 Agent 输出都要说明：做了什么、修改了哪些文件、如何运行、是否需要用户确认。
- 如果用户只要求“初始化”“规划”“讲解”或“先设计”，不得直接开始开发代码。

## 禁止事项

- 不做无关重构。
- 不覆盖用户已有改动。
- 不把课程/项目学习过程变成黑箱代做；需要讲清楚关键思路。
- 不硬编码 API Key、访问令牌或本地绝对路径到源码中。
- 不把上传文件、向量库、缓存、`.env`、虚拟环境提交到版本控制。

## 参考资料

- 初始项目大纲：`/Users/rayne/Desktop/studymate 大纲.md`
