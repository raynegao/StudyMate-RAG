# StudyMate RAG v0.4.0

This release turns StudyMate RAG from a whole-library demo into a reader for one selected PDF, and adds an evaluation set that can still tell a better retriever from a worse one.

## Highlights

- **Document-scoped answers.** Every question is answered from the selected PDF only; there is no fallback to other documents.
- **Whole-document summaries.** Summaries read every indexed chunk of the selected PDF in page order, in up to 8 batches of 12,000 characters, and refuse before any external call when a document is too large. Each summary point keeps its page citation.
- **Narrower automatic routing.** Only whole-document requests such as 这份资料的核心概念是什么 become summaries; targeted requests such as 总结第三章的公式 keep similarity retrieval.
- **Reader-facing interface.** Citations render as page links, sources fold by page, errors map to plain Chinese messages, and internal IDs, distances and tuning controls are hidden.
- **Safer generation.** Chunking respects the real tokenizer limit, DeepSeek calls have a 30-second read timeout and no automatic retries, truncated output is rejected, and summaries without valid page references return `summary_citations_invalid` instead of a generic failure.
- **Local deployment hardening.** Ports publish to `127.0.0.1` by default, a separate real-course profile keeps a local-only mode, and `/api/config` serves upload and timeout budgets to the page.
- **Dependency refresh.** FastAPI 0.143, Streamlit 1.65, Pydantic 2.14, pypdf 6.20, pytest 9 and Ruff 0.17. Torch, transformers, sentence-transformers, ChromaDB and the OpenAI SDK are held back on purpose because they change embeddings, the index format or request parameters.

## Evaluation

The original 30 public and 15 real-course questions are nearly saturated, so a new hard set measures paraphrased questions, confusable entities, boundary conditions, numeric details and multi-page evidence with the app's document-scoped retrieval.

| Set | BGE top-1 | BGE top-6 |
| --- | ---: | ---: |
| Public hard, 24 fictional questions | 50.0% | 100.0% |
| Real-course hard, 15 local-only questions | 26.7% | 53.3% |

On the public hard set, 95.8% of DeepSeek answers pass the keyword and distractor-value checks. The real-course gap is mainly cross-language paraphrase and confusable concepts; it is the baseline for any future retrieval change. See `docs/hard-evaluation.md`.

## Verification

- `scripts/test.sh`: Ruff, 141 tests, backend coverage above 88 %, dependency check
- `docker build --check .` and `docker compose config --quiet`
- Isolated Docker E2E with real BGE, ChromaDB persistence across restart, DeepSeek answers and overview, refusal and cleanup

The attached JSON files are the machine-readable evidence from this release's verification runs.

## Upgrade notes

- `STUDYMATE_APP_VERSION` now defaults to `0.4.0`. An existing `.env.local` that sets it explicitly keeps its old value until edited.
- New chunking only applies to new uploads; existing indexes are not rebuilt automatically.
