# StudyMate RAG v0.3.0

This release packages StudyMate RAG as a reproducible graduate-application portfolio project.

## Highlights

- Local BGE embeddings, ChromaDB persistence and DeepSeek grounded answers with page-level citations
- FastAPI backend, Streamlit workspace and non-root Docker Compose runtime
- 30-question public Chinese benchmark over three fully fictional PDFs
- Recall@K, MRR@K, deterministic answer accuracy, citation accuracy and latency reporting
- BGE dense retrieval comparison against a character n-gram lexical baseline across chunk sizes and top-k values
- Isolated automated Docker E2E covering real BGE, real DeepSeek, backend restart persistence and cleanup
- 75-second public demonstration video and refreshed screenshots with a consistent 25 MB upload limit

## Reproducibility

Run `scripts/test.sh` for the regular quality gate, `scripts/evaluate_rag.py` for retrieval metrics, and `scripts/run_docker_e2e.py` for the external-model real-stack check.

The attached JSON files are machine-readable evidence from the release verification run. The benchmark is synthetic and intentionally small; see `docs/evaluation.md` for methodology and limitations.
