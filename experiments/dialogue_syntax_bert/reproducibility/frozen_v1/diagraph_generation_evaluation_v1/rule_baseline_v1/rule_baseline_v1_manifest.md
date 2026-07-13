# rule_baseline_v1 manifest

| file | purpose |
| --- | --- |
| `rule_baseline_prediction_v1.csv` | rule-based baseline prediction in schema-compliant CSV form |
| `rule_baseline_prediction_v1.xlsx` | spreadsheet view of the baseline prediction file |
| `rule_baseline_v1_generation_report.md` | generation-side summary of coverage, rule triggers, and conservative design choices |
| `rule_baseline_v1_evaluation_summary.md` | compact summary of evaluator metrics for the baseline run |
| `rule_baseline_v1_error_analysis.md` | error analysis focused on missed relation types, zero-match pairs, and overgeneration |
| `rule_baseline_v1_manifest.md` | artifact manifest for the whole baseline package |
| `evaluation_run/evaluation_summary.json` | machine-readable evaluator summary |
| `evaluation_run/evaluation_summary.md` | default evaluator summary report |
| `evaluation_run/per_pair_metrics.csv` | per-pair metric table from evaluator |
| `evaluation_run/per_pair_metrics.xlsx` | spreadsheet version of per-pair metrics |
| `evaluation_run/matched_columns_exact.csv` | exact-match alignment table |
| `evaluation_run/matched_columns_relaxed.csv` | relaxed-match alignment table |
| `evaluation_run/unmatched_gold_columns.csv` | gold columns not recovered after relaxed matching |
| `evaluation_run/overgenerated_prediction_columns.csv` | prediction columns with no relaxed gold match |
| `evaluation_run/invalid_predictions.csv` | invalid prediction rows excluded from scoring |
| `evaluation_run/relation_type_confusion_matrix.csv` | relation-type confusion matrix on relaxed matches |
| `evaluation_run/core_column_error_report.csv` | core-column specific mismatch audit |
