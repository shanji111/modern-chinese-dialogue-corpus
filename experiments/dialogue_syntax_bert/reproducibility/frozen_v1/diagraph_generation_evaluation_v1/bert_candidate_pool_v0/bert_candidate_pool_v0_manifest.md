# bert_candidate_pool_v0 manifest

| file | purpose |
| --- | --- |
| `bert_candidate_pool_v0.csv` | merged candidate pool from v1 recall base plus v1.1 precision hints |
| `bert_candidate_pool_v0.xlsx` | spreadsheet view of the merged candidate pool |
| `bert_candidate_pool_v0_evaluation_summary.md` | compact metric summary for pool evaluation |
| `bert_candidate_pool_v0_comparison_with_v1_and_v1_1.md` | comparison of pool vs v1 and v1.1 |
| `bert_candidate_pool_v0_tier_distribution.csv` | candidate tier counts and coverage |
| `bert_candidate_pool_v0_relation_type_distribution.csv` | relation-type distribution for the pool |
| `bert_candidate_pool_v0_pair_coverage.csv` | per-pair candidate coverage table |
| `bert_candidate_pool_v0_diagnostic_report.md` | diagnostic notes on remaining gaps and noise |
| `bert_assisted_prototype_v0_plan.md` | next-step plan for BERT rerank/filter prototype |
| `bert_candidate_pool_v0_manifest.md` | artifact manifest |
| `evaluation_run/*` | evaluator outputs for the candidate pool |

## Scope note

- No BERT training or inference was run in this step.
- No baseline artifacts were overwritten.
- `diagraph_gold_50_column_gold_v1` was used only for offline evaluation.
