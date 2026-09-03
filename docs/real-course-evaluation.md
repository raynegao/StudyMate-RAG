# Anonymous real-course evaluation

This evaluation uses 15 paraphrased Chinese questions over 3 real university course PDFs. The PDFs, original filenames, local paths, institution names, instructor names and student data are not committed. Only anonymous aliases, integrity hashes, page-level labels and minimal answer keywords are public.

## Privacy boundary

- Source PDFs remain local and Git-ignored.
- The evaluator verifies source SHA-256 values, page counts and gold keywords before running.
- Only local BGE embeddings are used; no source text or question is sent to an external LLM.
- Results contain anonymous aliases and page numbers, never local paths or source text.

## Default result

- BGE Recall@1: 66.67%
- BGE MRR@1: 66.67%
- Mean retrieval latency: 34.356 ms
- P95 retrieval latency: 56.879 ms

## Retrieval results

| Retriever | Chunk size | Overlap | Top K | Chunks | Recall@K | MRR@K | Mean ms/query | P95 ms/query |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BGE dense | 300 | 60 | 1 | 275 | 66.67% | 66.67% | 34.478 | 56.882 |
| character n-gram | 300 | 60 | 1 | 275 | 33.33% | 33.33% | 6.106 | 69.682 |
| BGE dense | 300 | 60 | 3 | 275 | 86.67% | 75.56% | 34.478 | 56.882 |
| character n-gram | 300 | 60 | 3 | 275 | 66.67% | 50.00% | 6.106 | 69.682 |
| BGE dense | 300 | 60 | 5 | 275 | 93.33% | 76.89% | 34.478 | 56.882 |
| character n-gram | 300 | 60 | 5 | 275 | 93.33% | 55.67% | 6.106 | 69.682 |
| BGE dense | 600 | 100 | 1 | 236 | 66.67% | 66.67% | 34.040 | 56.528 |
| character n-gram | 600 | 100 | 1 | 236 | 26.67% | 26.67% | 1.379 | 2.070 |
| BGE dense | 600 | 100 | 3 | 236 | 86.67% | 76.67% | 34.040 | 56.528 |
| character n-gram | 600 | 100 | 3 | 236 | 60.00% | 41.11% | 1.379 | 2.070 |
| BGE dense | 600 | 100 | 5 | 236 | 86.67% | 76.67% | 34.040 | 56.528 |
| character n-gram | 600 | 100 | 5 | 236 | 80.00% | 45.78% | 1.379 | 2.070 |
| BGE dense | 1000 | 150 | 1 | 233 | 66.67% | 66.67% | 34.356 | 56.879 |
| character n-gram | 1000 | 150 | 1 | 233 | 26.67% | 26.67% | 1.336 | 2.087 |
| BGE dense | 1000 | 150 | 3 | 233 | 86.67% | 76.67% | 34.356 | 56.879 |
| character n-gram | 1000 | 150 | 3 | 233 | 60.00% | 41.11% | 1.336 | 2.087 |
| BGE dense | 1000 | 150 | 5 | 233 | 86.67% | 76.67% | 34.356 | 56.879 |
| character n-gram | 1000 | 150 | 5 | 233 | 80.00% | 45.78% | 1.336 | 2.087 |

## Reproduce locally

1. Copy `evaluation/real_course_sources.example.json` to the Git-ignored path `evaluation/private/real-course-sources.json`.
2. Map each anonymous alias to the corresponding local PDF.
3. Run `.venv/bin/python scripts/evaluate_real_course.py`.

Machine-readable results are stored in `output/evaluation/real-course-results.json`.

## Limitations

- The benchmark contains one real course domain and 15 questions, so it measures a more realistic retrieval slice rather than broad academic generalization.
- Source PDFs cannot be redistributed, so third parties need their own authorized local documents to reproduce the workflow.
- Keyword and page labels were manually checked; they are not expert-scored free-form answer labels.
