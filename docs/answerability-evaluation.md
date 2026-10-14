# Answerability evaluation

18 additional questions over the public fictional PDFs: 6 held-out answerable paraphrases and 12 unanswerable questions (6 calibration, 6 held-out). Missing-fact negatives share the document's topic but ask for facts that are absent.

Generated: 2026-09-05T09:37:06.038366+00:00; real LLM evaluation: True.

The serving relevance gate and answer/citation guard are used unchanged. A low similarity can reject irrelevant context locally; high similarity does not establish answerability. Related missing-fact questions are tested through real generation. The threshold is selected using the original 30 answerable questions and calibration negatives. The held-out split is a development regression set, not a blind generalization claim.

```json
{
  "positive_source": "original 30-question public benchmark",
  "positive_min_top_similarity": 0.43859571023720073,
  "positive_gate_acceptance": 1.0,
  "out_of_domain_max_top_similarity": 0.2955160820262556,
  "selection_rule": "Conservative threshold within the calibration gap; held-out cases are regression checks, not a blind generalization claim."
}
```

```json
{
  "calibration": {
    "unanswerable_count": 6,
    "answerable_count": 0,
    "refusal_accuracy": 1.0,
    "answer_accuracy": null,
    "retrieval_evidence_recall": null
  },
  "held_out": {
    "unanswerable_count": 6,
    "answerable_count": 6,
    "refusal_accuracy": 1.0,
    "answer_accuracy": 0.8333333333333334,
    "retrieval_evidence_recall": 1.0
  }
}
```

| Case | Split | Kind | Top cosine | Gate rejected | Answer/refusal correct |
| --- | --- | --- | ---: | --- | --- |
| ANS-01 | held_out | answerable | 0.760 | False | True |
| ANS-02 | held_out | answerable | 0.445 | False | True |
| ANS-03 | held_out | answerable | 0.652 | False | True |
| ANS-04 | held_out | answerable | 0.464 | False | True |
| ANS-05 | held_out | answerable | 0.598 | False | False |
| ANS-06 | held_out | answerable | 0.610 | False | True |
| NO-01 | calibration | out_of_domain | 0.289 | True | True |
| NO-02 | calibration | out_of_domain | 0.218 | True | True |
| NO-03 | calibration | out_of_domain | 0.296 | True | True |
| NO-04 | calibration | missing_fact | 0.639 | False | True |
| NO-05 | calibration | missing_fact | 0.617 | False | True |
| NO-06 | calibration | missing_fact | 0.449 | False | True |
| NO-07 | held_out | out_of_domain | 0.305 | True | True |
| NO-08 | held_out | out_of_domain | 0.429 | False | True |
| NO-09 | held_out | out_of_domain | 0.390 | False | True |
| NO-10 | held_out | missing_fact | 0.522 | False | True |
| NO-11 | held_out | missing_fact | 0.650 | False | True |
| NO-12 | held_out | missing_fact | 0.619 | False | True |

## Reproduce

Load `.env.local`, then run `.venv/bin/python scripts/evaluate_answerability.py --with-llm`. Omit the flag for local retrieval checks only.

## Limits

Gold-page support and keyword correctness are auditable proxies, not a semantic entailment judge. The small synthetic set cannot prove universal refusal reliability. True/False outcomes require `with_llm=true`; a retrieval-only run leaves them null.
