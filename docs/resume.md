# StudyMate RAG Resume Notes

## 项目名称

StudyMate RAG：基于 RAG 的课程资料智能问答系统

## 简历描述

- 构建基于 FastAPI、Streamlit、ChromaDB、BGE embedding 和 DeepSeek Chat 的课程资料智能问答系统，支持 PDF 上传、文本解析、向量化索引、语义检索和基于上下文的问答。
- 设计并实现完整 RAG pipeline，包括 PDF 页面解析、文本 chunking、metadata 保留、本地 embedding 生成、top-k 向量检索、prompt 构造和引用来源展示。
- 使用 Pydantic 定义 API 请求/响应模型，加入统一错误响应、日志、API contract 测试和最小 smoke check，提升项目可维护性。
- 通过 Streamlit 构建可演示前端，并使用 Docker Compose 编排 FastAPI 与 Streamlit 服务，实现本地一键展示。

## 技术关键词

FastAPI, Streamlit, Pydantic, ChromaDB, RAG, BGE, sentence-transformers, DeepSeek API, Docker, Docker Compose, pytest

## 面试讲解重点

### 为什么做这个项目

课程资料通常分散在 PDF、讲义和笔记中，普通聊天模型无法保证答案来自指定资料。StudyMate RAG 的目标是让用户上传自己的课程资料，然后系统只基于资料回答问题，并展示引用来源。

### RAG 流程

```text
PDF 上传
-> 文本解析
-> chunking
-> 本地 BGE embedding
-> ChromaDB 入库
-> 用户问题 embedding
-> top-k 检索
-> 构造 prompt
-> DeepSeek 生成回答
-> 返回答案和引用来源
```

### 工程设计

- API 层只处理 HTTP 和 schema，业务逻辑放在 service 层。
- ChromaDB 操作集中在 `vector_store`，后续可以替换成 FAISS、Milvus 或 pgvector。
- Embedding 和 LLM 调用分别封装，后续可以切换模型供应商。
- 上传文件和向量索引放在 `data/`，不提交到 Git。
- 测试覆盖健康检查、上传参数校验、聊天参数校验和 API contract。

### 当前边界

展示版暂不包含用户登录、多知识库、Rerank、Hybrid Search、多轮对话和云部署。后续可以按这些方向继续增强。

## 项目亮点短句

- “我没有只做一个调用 LLM 的 demo，而是实现了从资料解析、向量索引到引用来源展示的完整 RAG 应用闭环。”
- “项目采用 FastAPI service 分层，embedding、向量库和 LLM 调用都有独立模块，方便后续替换模型或扩展检索策略。”
- “前端用 Streamlit 做快速交互展示，后端保留标准 API 和测试，既能演示也能继续工程化扩展。”
