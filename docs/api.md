# StudyMate RAG API 0.4.0

- 默认地址：`http://127.0.0.1:8000`
- 交互式文档：`http://127.0.0.1:8000/docs`

## 统一错误格式

```json
{
  "error": {
    "code": "invalid_pdf",
    "message": "PDF 文件已损坏或格式无效。",
    "details": {}
  }
}
```

未知异常只在服务端记录完整日志，客户端统一收到脱敏的 `internal_error`。

## GET /health

```json
{
  "status": "ok",
  "service": "studymate-rag-api"
}
```

## POST /api/upload

以 `multipart/form-data` 上传字段 `file`。成功状态码为 `201`。

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@output/pdf/studymate-demo-course.pdf"
```

```json
{
  "document_id": "624ccf423d3844c4b8a3636e4b06365b",
  "filename": "星际导航课程讲义.pdf",
  "status": "indexed",
  "chunk_count": 3,
  "metadata": {
    "stored_filename": "624ccf423d3844c4b8a3636e4b06365b_星际导航课程讲义.pdf",
    "page_count": 3
  }
}
```

文件会分块写入，并在写入过程中检查大小。任何解析或索引失败都会清理本次上传残留。

启动脚本会将 `STUDYMATE_MAX_UPLOAD_SIZE_MB` 同时传给 Streamlit 服务；页面从 `/api/config` 获取后端上限，发现两端不一致时阻止上传并提示上传暂不可用。维护者需用相同配置重启前后端。

常见错误：

- `400 unsupported_file_type`：不是 PDF
- `400 invalid_pdf`：PDF 损坏或格式无效
- `413 upload_too_large`：超过 `STUDYMATE_MAX_UPLOAD_SIZE_MB`
- `422 encrypted_pdf`：PDF 已加密
- `422 pdf_no_extractable_text`：空白、无文本或纯扫描 PDF
- `502 embedding_failed`：BGE 初始化或向量生成失败
- `503 vector_store_unavailable`：ChromaDB 不可用

## POST /api/chat

```json
{
  "question": "蓝色令牌的有效期是多少？",
  "top_k": 6
}
```

- `question`：必填，最多 2000 字符，去除首尾空白后不能为空；超过 embedding 的实际 token 上限返回 `422 embedding_input_too_long`，不会静默截断
- `top_k`：可选，范围 1 到 10；省略时使用 `STUDYMATE_TOP_K`，默认 6
- `document_id`：可选，32 位十六进制 ID。新版页面始终传所选 PDF 的 ID；具体问题无命中时不会回退到全库。
- `mode`：`auto`（默认）、`question` 或 `summary`。自动模式只把针对整份资料的概览请求（如“这份资料的核心概念是什么？”“总结主要内容”）转为整篇概括；带有具体对象的问题（如“总结第三章的公式”）仍走相似度检索。`question` 强制具体检索，`summary` 强制概览。

整篇概括必须提供 `document_id`，否则返回 `400 document_selection_required`。它按页读取该 PDF 的全部已索引文字，不经过相似度过滤或 top-k 抽样。每批最多 12000 字符、最多 8 批，多批归纳后综合，超限在外发前返回 `422 summary_too_large`。

```json
{"question":"这份资料的核心概念是什么？","document_id":"624ccf423d3844c4b8a3636e4b06365b","mode":"summary"}
```

概括响应额外返回 `metadata`：`mode=summary`、`coverage=all_indexed_text`、`indexed_pages_covered`、`chunks_covered`、`batches`。引用指向原文页码与片段，`distance=null`；覆盖仅指已解析文本，不包括扫描图片。具体问题不提供 ID 时保留旧全库 API 行为，新版页面不使用该行为。

```json
{
  "answer": "蓝色令牌的有效期为三个星港周期。[S1]",
  "status": "answered",
  "sources": [
    {
      "citation_id": "S1",
      "document_id": "624ccf423d3844c4b8a3636e4b06365b",
      "filename": "星际导航课程讲义.pdf",
      "page": 2,
      "chunk_id": "624ccf423d3844c4b8a3636e4b06365b:p2:c0",
      "distance": 0.733,
      "cited": true,
      "text": "引用片段",
      "metadata": {}
    }
  ]
}
```

`distance` 是 Chroma 返回的向量距离，通常越小越相关，不是相似度百分比。`cited=true` 表示答案文本实际包含对应的 `[S1]` 标记；其余来源只是检索候选。

空知识库会直接返回友好提示和空来源列表，不加载 BGE，也不调用 DeepSeek。

`status` 的含义：

- `answered`：返回带合法来源标记的生成回答；标记本身不证明每句话都被原文支持。
- `insufficient_evidence`：没有足够检索证据、模型拒答、无有效引用或存在越界引用。
- `empty`：知识库为空。
- `retrieval_only`：仅展示本地片段，不调用外部 LLM，所有 `cited` 均为 false。

归一化向量使用 Chroma 默认平方 L2 距离。默认生成模式相似度门槛为 0.35，等价于距离不大于 1.30；显式课程本地模式使用 0.50。低分片段被过滤，高分仍不保证答案存在，因此生成提示和无答案测试继续约束拒答。整篇概括不使用相似度门槛。

DeepSeek 读取超时默认为 30 秒，连接超时最多 5 秒，SDK 自动重试为 0。前端从运行配置获取等待预算（至少 60 秒，或读取超时加 30 秒）。这些是 HTTP 阶段超时，不是对任意网络行为的绝对总时长保证。

常见错误：

- `422 validation_error`：问题或 `top_k` 不合法
- `400 document_selection_required`：概括前未选择 PDF
- `404 document_not_found`：所选 PDF 不存在或已删除
- `422 summary_too_large`：超过整篇概括预算，外部调用尚未开始
- `502 embedding_failed`：问题向量生成失败
- `502 llm_request_failed`：DeepSeek 请求失败
- `502 llm_output_incomplete`：模型达到输出上限，答案未完整生成，不返回截断内容作为成功答案
- `502 summary_citations_invalid`：概括已生成但缺少引用或引用越界，结果被丢弃；这是输出质量问题而非服务故障，可直接重试
- `503 llm_not_configured`：未设置 `DEEPSEEK_API_KEY`
- `503 vector_store_unavailable`：ChromaDB 不可用
- `504 llm_timeout`：生成请求超时，本次未自动重试

## GET /api/config

返回 `knowledge_base_name`、`chat_mode`、`max_upload_size_mb`、`default_top_k`、`chat_request_timeout_seconds`、`summary_request_timeout_seconds`。不返回 API Key、本机路径或私人原文件名。概括等待预算默认为 `9 × LLM阶段超时 + 60`，即 330 秒；前端智能模式也使用该预算，因为它可能路由到概括。后端每次模型调用仍为零重试和有限阶段超时。

整篇概括显式关闭 DeepSeek 思考模式，具体问答保留思考；两者 `max_tokens=4096`，并检查 `finish_reason`，避免旧预算耗尽后正文为空。HTTP 200 仍需检查完整性、正文及有效引用，不等于应用层成功。

### 消费端展示边界（2026-09-06）

API 字段和引用协议未变。页面不显示 `document_id`、`chunk_id`、`distance`、`chunks_covered` 或 top-k 控件；具体问答仍发送配置的 `default_top_k`，概括不受该值限制。`[S数字]` 仅在展示时转换为页码链接，同页多个原文保留在一个折叠卡片中。纯本地页面发送 `mode=question`，不把“查找原文”操作转成无法生成的概括请求。错误根据稳定 `error.code` 映射到中文提示，未知错误使用统一提示，不展示 HTTP 正文。

## GET /api/documents

```json
{
  "documents": [
    {
      "document_id": "624ccf423d3844c4b8a3636e4b06365b",
      "filename": "星际导航课程讲义.pdf",
      "chunk_count": 3,
      "created_at": null,
      "metadata": {
        "pages": [1, 2, 3],
        "page_count": 3,
        "indexed_at": "2026-07-20T07:34:00+00:00"
      }
    }
  ]
}
```

## DELETE /api/documents/{document_id}

`document_id` 必须是 32 位十六进制字符串。合法但不存在的 ID 返回 `200` 和 `not_found`，便于幂等调用；通配符、路径字符和其他格式返回 `400 invalid_document_id`，且不会触碰文件或向量。

```json
{
  "document_id": "624ccf423d3844c4b8a3636e4b06365b",
  "status": "deleted",
  "message": "文档已删除。"
}
```

删除成功时会同时移除对应上传文件和 Chroma 向量。
