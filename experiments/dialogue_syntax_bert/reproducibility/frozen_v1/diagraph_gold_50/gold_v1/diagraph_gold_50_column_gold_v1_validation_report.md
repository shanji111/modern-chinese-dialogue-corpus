# diagraph_gold_50 column gold v1 validation report

## Counts

- active pair coverage: 50
- active column count: 135
- all_rows count: 151
- active rows with spot_review_applied=1: 20
- active rows with spot_review_decision=keep: 16
- active rows with spot_review_decision=revise: 4
- all_rows delete count retained for audit: 16

## Checks

- active covers 50 pairs: PASS
- active column count is 135: PASS
- all_rows count is 151: PASS
- active has no excluded_from_gold_candidate rows: PASS
- active has no reviewer_decision=delete rows: PASS
- annotation_id + column_id unique: PASS
- each pair has at least 1 active column: PASS
- each pair has at least 1 active core column: PASS
- span_a all from turn_a: PASS
- span_b all from turn_b: PASS
- relation_type legal: PASS
- relation_strength legal: PASS
- alignment_direction legal: PASS
- is_core_column / supports_resonance legal: PASS
- spot review 4 core demotions applied: PASS
- source spot_reviewed inputs unchanged during freeze: PASS

## Spot Review Core Demotions

- F300V1-0127/C04
- F300V1-0254/C01
- F300V1-0254/C04
- F300V1-0254/C05

## Constraint Audit

- BERT training or inference: none
- pair-level gold_v1 / gold_v1_binary modification: none
- train/dev/test split modification: none
- formal corpus.db read/write: none
- website routing / deployment: none
