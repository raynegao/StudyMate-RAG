# Anonymous real-course evaluation

This evaluation uses 15 paraphrased Chinese questions over 3 real university course PDFs. The PDFs, original filenames, local paths, institution names, instructor names and student data are not committed. Only anonymous aliases, integrity hashes, page-level labels and minimal answer keywords are public.

## Privacy boundary

- Source PDFs remain local and Git-ignored.
- The evaluator verifies source SHA-256 values, page counts and gold keywords before running.
- Only local BGE embeddings are used; no source text or question is sent to an external LLM.
- Results contain anonymous aliases and page numbers, never local paths or source text.
- The reviewed entropy question accepts pages 14 and 15. Original-page-only recall is retained separately in JSON; changing annotations is not counted as a retrieval improvement.
- Splits respect sentence boundaries and a 384-token budget. Default character limit/overlap/top-k: 300/60/6.

## Default result

- BGE Recall@1: 73.33%
- BGE MRR@1: 73.33%
- Mean retrieval latency: 30.241 ms
- P95 retrieval latency: 60.326 ms

## Retrieval results

| Retriever | Chunk size | Overlap | Top K | Chunks | Recall@K | MRR@K | Mean ms/query | P95 ms/query |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BGE dense | 300 | 60 | 1 | 275 | 73.33% | 73.33% | 30.241 | 60.326 |
| character n-gram | 300 | 60 | 1 | 275 | 33.33% | 33.33% | 1.525 | 2.841 |
| BGE dense | 300 | 60 | 3 | 275 | 86.67% | 78.89% | 30.241 | 60.326 |
| character n-gram | 300 | 60 | 3 | 275 | 66.67% | 50.00% | 1.525 | 2.841 |
| BGE dense | 300 | 60 | 4 | 275 | 86.67% | 78.89% | 30.241 | 60.326 |
| character n-gram | 300 | 60 | 4 | 275 | 86.67% | 55.00% | 1.525 | 2.841 |
| BGE dense | 300 | 60 | 5 | 275 | 93.33% | 80.22% | 30.241 | 60.326 |
| character n-gram | 300 | 60 | 5 | 275 | 93.33% | 56.33% | 1.525 | 2.841 |
| BGE dense | 300 | 60 | 6 | 275 | 100.00% | 81.33% | 30.241 | 60.326 |
| character n-gram | 300 | 60 | 6 | 275 | 93.33% | 56.33% | 1.525 | 2.841 |
| BGE dense | 600 | 100 | 1 | 236 | 73.33% | 73.33% | 29.831 | 59.985 |
| character n-gram | 600 | 100 | 1 | 236 | 26.67% | 26.67% | 1.438 | 2.712 |
| BGE dense | 600 | 100 | 3 | 236 | 86.67% | 80.00% | 29.831 | 59.985 |
| character n-gram | 600 | 100 | 3 | 236 | 66.67% | 44.44% | 1.438 | 2.712 |
| BGE dense | 600 | 100 | 4 | 236 | 86.67% | 80.00% | 29.831 | 59.985 |
| character n-gram | 600 | 100 | 4 | 236 | 73.33% | 46.11% | 1.438 | 2.712 |
| BGE dense | 600 | 100 | 5 | 236 | 86.67% | 80.00% | 29.831 | 59.985 |
| character n-gram | 600 | 100 | 5 | 236 | 80.00% | 47.44% | 1.438 | 2.712 |
| BGE dense | 600 | 100 | 6 | 236 | 93.33% | 81.11% | 29.831 | 59.985 |
| character n-gram | 600 | 100 | 6 | 236 | 86.67% | 48.56% | 1.438 | 2.712 |
| BGE dense | 1000 | 150 | 1 | 233 | 73.33% | 73.33% | 29.816 | 60.011 |
| character n-gram | 1000 | 150 | 1 | 233 | 26.67% | 26.67% | 1.328 | 2.013 |
| BGE dense | 1000 | 150 | 3 | 233 | 86.67% | 80.00% | 29.816 | 60.011 |
| character n-gram | 1000 | 150 | 3 | 233 | 66.67% | 44.44% | 1.328 | 2.013 |
| BGE dense | 1000 | 150 | 4 | 233 | 86.67% | 80.00% | 29.816 | 60.011 |
| character n-gram | 1000 | 150 | 4 | 233 | 73.33% | 46.11% | 1.328 | 2.013 |
| BGE dense | 1000 | 150 | 5 | 233 | 86.67% | 80.00% | 29.816 | 60.011 |
| character n-gram | 1000 | 150 | 5 | 233 | 80.00% | 47.44% | 1.328 | 2.013 |
| BGE dense | 1000 | 150 | 6 | 233 | 93.33% | 81.11% | 29.816 | 60.011 |
| character n-gram | 1000 | 150 | 6 | 233 | 86.67% | 48.56% | 1.328 | 2.013 |

## Reproduce locally

1. Copy `evaluation/real_course_sources.example.json` to the Git-ignored path `evaluation/private/real-course-sources.json`.
2. Map each anonymous alias to the corresponding local PDF.
3. Run `.venv/bin/python scripts/evaluate_real_course.py`.

Machine-readable results are stored in `output/evaluation/real-course-results.json`.

## Limitations

- The benchmark contains one real course domain and 15 questions, so it measures a more realistic retrieval slice rather than broad academic generalization.
- Source PDFs cannot be redistributed, so third parties need their own authorized local documents to reproduce the workflow.
- Keyword and page labels were manually checked; they are not expert-scored free-form answer labels.
