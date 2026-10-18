# StudyMate RAG v0.5.0

This release adds a second answer model provider and the operational hardening found while running the course library against it.

## Highlights

- **Gemini as a switchable provider.** `STUDYMATE_LLM_PROVIDER=gemini` with `GEMINI_API_KEY` calls Gemini through its OpenAI-compatible endpoint (default `gemini-3.8-flash`); DeepSeek stays the default and only the selected provider receives document text. `/api/config` reports the provider and the page names it. `scripts/verify_llm_provider.py` checks a provider with two fictional prompts.
- **Concurrent summary sections.** Whole-document summaries send section requests with bounded concurrency (`STUDYMATE_SUMMARY_CONCURRENCY`, default 4), keep page order, fail fast, and the page budget is derived from concurrency rounds (150 s by default instead of 330 s).
- **Citation normalisation.** Grouped citation brackets such as `[S6, S16, S17]`, which Gemini often writes, are rewritten to `[S6][S16][S17]` before any check, so supported answers are no longer refused and every cited page renders as a link.
- **Clear provider failures.** HTTP 429 maps to `llm_rate_limited` and HTTP 402 to `llm_quota_exhausted`, each with its own reader-facing message; nothing is retried automatically.
- **Page fixes.** The sidebar expand button is reachable again (a regression from the Streamlit 1.65 upgrade), the chosen document is remembered across reloads through the `doc` address-bar parameter, and the page process no longer inherits provider keys.
- **Configuration guard.** `STUDYMATE_LLM_MODEL` overrides the provider default and is rejected when it names the other provider's model.

## Evaluation

- All answer evidence was refreshed on 2026-10-18 with DeepSeek on this release's code: public benchmark 30/30 keyword checks with 100.00% cited-page accuracy, hard set 24/24 with 97.92% citation support, answerability 12/12 refusals and 6/6 held-out answers, isolated Docker E2E with `llm_provider=deepseek` and the 150 s summary budget, and summary concurrency medians of 27.93 s sequential versus 12.99 s with four workers (2.15x).
- Gemini was verified live (question and summary paths, course library) but not benchmarked: the free tier allows 5 requests per minute and 20 per day, and the project's prepaid credit was depleted (HTTP 402).
- Hybrid retrieval was measured offline with reciprocal-rank fusion of the BGE and n-gram rankings: public hard R@1 62.5%, real-course hard R@6 53.3% (unchanged from BGE alone), so the serving path still uses dense retrieval only. See `docs/hard-evaluation.md`.

## Verification

- `scripts/test.sh`: Ruff, 168 tests, backend coverage above 88 %, dependency check
- Live with Gemini: `scripts/verify_llm_provider.py`, and the course library driven through the browser (question with page-7 citation, 76-page summary with 2 concurrent sections)
- Live with DeepSeek (2026-10-18): `scripts/verify_llm_provider.py`, `scripts/evaluate_rag.py --with-llm`, `scripts/evaluate_answerability.py --with-llm`, `scripts/evaluate_hard.py --with-llm`, `scripts/verify_summary_concurrency.py`, `scripts/run_docker_e2e.py`

## Upgrade notes

- `STUDYMATE_APP_VERSION` now defaults to `0.5.0`.
- New environment variables: `STUDYMATE_LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `STUDYMATE_SUMMARY_CONCURRENCY`; `STUDYMATE_LLM_MODEL` may now be left empty.
