# diagraph_gold_50 column gold v1 freeze report

## Freeze Input Sources

- `full_gold_candidate/final_sanity_check/targeted_spot_review/applied/full_diagraph_gold_50_column_gold_candidate_active_spot_reviewed.csv`
- `full_gold_candidate/final_sanity_check/targeted_spot_review/applied/full_diagraph_gold_50_column_reviewed_all_rows_spot_reviewed.csv`
- `full_gold_candidate/final_sanity_check/targeted_spot_review/applied/targeted_spot_review_apply_validation_report.md`
- `full_gold_candidate/final_sanity_check/targeted_spot_review/applied/targeted_spot_review_apply_summary.md`
- `full_gold_candidate/full_diagraph_gold_50_merge_validation_report.md`
- `diagraph_gold_50_annotation_guide_v2.md`
- `diagraph_gold_50_pair_list.csv`

## Freeze Output Files

- `diagraph_gold_50_column_gold_v1_active.csv`
- `diagraph_gold_50_column_gold_v1_active.xlsx`
- `diagraph_gold_50_column_gold_v1_all_rows.csv`
- `diagraph_gold_50_column_gold_v1_all_rows.xlsx`
- `diagraph_gold_50_column_gold_v1_metadata.json`
- `diagraph_gold_50_column_gold_v1_freeze_report.md`
- `diagraph_gold_50_column_gold_v1_validation_report.md`
- `diagraph_gold_50_column_gold_v1_readme.md`

## Freeze Checks

- active rows: 135
- audit rows: 151
- pair coverage: 50 / 50
- each pair retains at least 1 active column
- each pair retains at least 1 active core column
- span validation passed before freeze and is rechecked in the validation report
- relation_type / relation_strength / alignment_direction / is_core_column / supports_resonance are revalidated

## Relation to Pair-Level Gold

- 本文件是 column-level `diagraph_gold_50_column_gold_v1`。
- 它依附于 formal_300_v1 的 pair-level `gold_v1` / `gold_v1_binary` 取样背景，但不替代 pair-level gold。
- pair-level gold 负责判断共鸣是否存在；column-level gold 负责记录 turn_a / turn_b 之间的纵栏映射结构。

## Why BERT Is Not Involved

- BERT / hybrid 只属于前一阶段的 pair-level shadow experiment。
- 本 column gold 由 guide_v2 约束下的人机协同标注、review、spot review 和 freeze 流程产出。
- 因此 BERT 没有直接参与 column gold 生成。

## Freeze Policy

- `gold_v1` 冻结后不应随意改动。
- 如果未来发现问题，应另开 `gold_v1_patch` 或 `gold_v2_candidate`。
- 不要直接覆盖或回写 `gold_v1` 本体。
