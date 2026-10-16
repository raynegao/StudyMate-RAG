# StudyMate RAG 开发约定

## 项目目标

StudyMate RAG 为课程 PDF 提供本地向量检索和带引用的问答能力。当前版本只维护稳定展示闭环，不提前加入 OCR、Hybrid Search、Rerank、Query Rewrite、多轮记忆或多知识库。

## 技术栈

- Python 3.12、FastAPI、Pydantic、Uvicorn
- sentence-transformers、`BAAI/bge-small-zh-v1.5`、ChromaDB
- DeepSeek Chat API 或 Gemini API（OpenAI 兼容接口），由 `STUDYMATE_LLM_PROVIDER` 切换
- Streamlit
- uv、pytest、Ruff、coverage、Docker Compose

## 模块边界

- `backend/app/api/`：HTTP 路由、请求校验和响应转换
- `backend/app/core/`：配置、日志和统一错误处理
- `backend/app/services/`：PDF 解析、chunking、embedding、向量库和 RAG 流程
- `backend/app/models/`：Pydantic schema
- `frontend/streamlit_app.py`：页面状态、上传、问答和文档管理
- `frontend/styles.css`、`.streamlit/config.toml`：消费端阅读界面的本地样式与主题；`scripts/ui_preview.py` 是不调用模型或资料库的虚构 UI 预览
- `tests/`：API contract、服务层和前端辅助逻辑测试
- `scripts/`：启动、测试、smoke、公开样例生成和不依赖后端的 UI 预览脚本
- `config/profiles/`：可公开的单实例运行配置；课程入口按用户授权默认启用智能回答（DeepSeek，或 `STUDYMATE_LLM_PROVIDER=gemini` 切换为 Gemini），`local` 保留仅检索模式
- `evaluation/`：公开虚构基准、加难基准、匿名真实课程清单（含加难题），以及 Git 忽略的本机来源映射
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
.venv/bin/python scripts/evaluate_real_course.py
.venv/bin/python scripts/evaluate_answerability.py --with-llm
.venv/bin/python scripts/evaluate_hard.py --with-llm
scripts/run_real_course.sh
scripts/run_real_course.sh local
scripts/run_real_course.sh verify
.venv/bin/python scripts/verify_token_budget.py
.venv/bin/python scripts/verify_summary_concurrency.py
.venv/bin/python scripts/run_docker_e2e.py
docker compose --env-file .env.local up --build
```

## 修改要求

- 修改前先阅读相关模块、README、依赖输入文件和现有测试。
- 保持 API 层与服务层分离，不在路由中实现模型或数据库细节。
- 同步重任务必须离开 FastAPI 事件循环。
- 分块同时满足实际 tokenizer 上限，embedding 不得静默截断；当前默认 300 字符、60 重叠、384 tokens、Top K 6。
- 前后端上传上限保持一致；页面使用 `/api/config` 获取资料库名称、模式、上限和等待预算。
- 回答模型（DeepSeek 或 Gemini）默认读取超时 30 秒、连接最多 5 秒、不自动重试；`local`、`prepare`、`verify` 必须保持 `retrieval_only`，常规启动按用户 2026-09-05 明确要求启用 DeepSeek。
- 页面问答必须携带所选 `document_id`，上传后选中新文档；整篇概括读取该文档全部已索引文本，不用 top-k 抽样冒充全文。
- 页面文案面向普通读者，不展示内部 ID、向量距离、片段计数、服务地址、异常正文或调试控件。问答沿用配置中的 Top K；页面不提供数字调参。API 原始引用不变，展示层转为页码链接并按页折叠原文；本地模式仍可查看未生成回答的相关原文。
- 概括最多 8 批、每批 12000 字符，超限必须在外发前明确拒绝；分段请求按 `STUDYMATE_SUMMARY_CONCURRENCY`（默认 4）并发，摘要须保持页序，任一分段失败即取消未开始的分段，不得为凑结果自动重试；生成保留原始片段引用和页码，覆盖范围不包括扫描图片。
- DeepSeek V4 整篇概括显式非思考，具体问答保留思考；两者 4096 token 输出上限，检查 `finish_reason=length`，不得将空正文或截断回答作为成功返回。Gemini 3 无法关闭思考，概括用 `reasoning_effort=minimal`、问答用 `low`，思考 token 计入同一上限。
- 客户端只接收稳定、脱敏的 JSON 错误，完整异常只写服务日志。
- API 行为变化时同步更新测试、`docs/api.md` 和 README。
- 依赖变更先修改 `requirements.in` 或 `requirements-dev.in`，再用锁文件头部记录的 `uv pip compile --universal --torch-backend cpu` 命令重新生成锁文件。
- torch、transformers、sentence-transformers、chromadb 和 openai 的大版本升级不能顺手做：它们分别影响向量数值、Chroma 磁盘索引格式（0.5 → 1.x）和请求参数，每一项都要单独迁移、重跑公开评测并确认 `real-course-v2` 索引无需重建。
- Ruff 规则集固定在根目录 `ruff.toml`（pyflakes 与 pycodestyle 错误子集），升级 Ruff 时不要靠它的内置默认值。
- 提交前运行 `scripts/test.sh`、Compose 配置检查和 Dockerfile 检查。
- 评测集或检索逻辑变化时重新生成公开 PDF、量化结果和 `docs/evaluation.md`；真实栈变化时重跑隔离 Docker E2E。
- 真实课程评测只提交匿名别名、完整性哈希、页码和最小答案关键词；原 PDF、本机路径、学校/教师信息和学生数据必须留在 `evaluation/private/` 或其他 Git 忽略位置。
- 标准页或答案关键词修订后保留原口径指标；不要把标注变化算成检索提升。拒答评测区分资料外问题和同主题缺失事实。
- 原 30 题与原 15 题已接近满分，判断检索改动时以 `docs/hard-evaluation.md` 的加难集为准。加难题在首次运行前固定，不按结果改题或改判分；新增题目需另起版本并保留旧版本指标。

## 数据与安全

- 不提交 API Key、`.env`、`.env.local`、上传资料、Chroma 数据、模型缓存或虚拟环境。
- 不读取、迁移、重建或对外发送旧私人索引内容。当前 `real-course-v2` 的所选文档可按用户明确授权用于 DeepSeek 问答，2026-10-16 起同样授权发送给 Gemini，但同一时间只有所选提供方收到原文；不得混入其他 PDF，也不得把私人回答写入公开验收文件。
- 删除操作只能接受 32 位十六进制 `document_id`，并同时处理对应上传文件和向量。
- 自动化演示和外部模型验收只使用 `output/pdf/` 中的公开虚构资料；用户已授权的实际 PDF 问答只在本机应用内处理，不作为公开样例。
