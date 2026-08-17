# StudyMate RAG 简历材料

## 项目名称

StudyMate RAG：课程资料智能问答系统

## 简历描述

- 基于 FastAPI、Streamlit、BGE、ChromaDB 和 DeepSeek 构建课程 PDF 问答系统，打通文件解析、向量索引、语义检索、生成回答和页码引用的完整流程。
- 设计分块上传和类型化错误体系，覆盖路径穿越、危险文档 ID、超限残留、损坏/加密/无文本 PDF、模型和向量库异常，客户端统一返回脱敏 JSON。
- 将 PDF 解析、embedding、Chroma 和 LLM 等同步重任务移出事件循环，并为空知识库设置短路逻辑，避免无效模型加载和外部调用。
- 为检索来源定义 `citation_id`、`distance` 和 `cited` 语义，通过系统级 prompt 约束抵御资料内指令，并在前端区分实际引用和检索候选。
- 使用 Python 3.12、uv 锁文件和非 root Docker 镜像统一开发与运行环境；CI 执行 Ruff、编译检查、pytest coverage、Compose 和 Dockerfile 检查。
- 构建 3 份公开虚构 PDF 和 30 题中文基准，按标准文档与页码计算 Recall@K、MRR、引用准确率和端到端延迟，并对比 BGE 与字符 n-gram 基线、不同 chunk size 和 top-k。

## 可核验数据

- 51 项自动化测试通过，后端语句覆盖率 84.99%
- 30 题公开合成集上，BGE Recall@1 与 MRR@1 均为 100%
- 30 次真实 DeepSeek 调用的关键词回答正确率、引用准确率和 grounded-answer rate 均为 100%
- 默认配置的平均检索延迟 26.18 毫秒，P95 为 59.51 毫秒
- 平均 DeepSeek 生成延迟 1.31 秒，P95 为 1.94 秒
- Docker Compose 前后端健康检查通过
- 隔离 Docker E2E 完成真实 BGE、PDF 上传、Chroma 重启持久化、真实 DeepSeek 问答和删除清理
- 公开虚构样例完成真实 DeepSeek 问答，答案包含有效来源标记

## 技术关键词

Python, FastAPI, Streamlit, Pydantic, RAG, BGE, sentence-transformers, ChromaDB, DeepSeek API, Docker Compose, uv, pytest, Ruff

## 面试讲解提纲

### 为什么需要 RAG

普通聊天模型无法保证答案来自指定课程资料。该项目先检索上传 PDF 的相关片段，再把带来源编号的上下文交给模型，使回答可以回查到文件、页码和原文。

### 核心流程

```text
PDF 分块上传
-> 解析与按页切分
-> 本地 BGE embedding
-> ChromaDB 持久化
-> 问题 embedding 与 top-k 检索
-> DeepSeek 生成带 [S1] 标记的回答
-> 前端展示实际引用和检索候选
```

### 工程取舍

- 展示版采用本地文件和 ChromaDB，部署简单且数据边界清晰。
- embedding 留在本地，外部模型只接收检索到的公开或用户授权片段。
- 使用 distance 原始语义，不包装成容易误解的相似度分数。
- 用服务层异常隔离底层库细节，避免路径、密钥或供应商错误泄露给客户端。
- 当前不加入 OCR、混合检索和多轮记忆，优先保证单知识库 PDF 闭环稳定可复现。
