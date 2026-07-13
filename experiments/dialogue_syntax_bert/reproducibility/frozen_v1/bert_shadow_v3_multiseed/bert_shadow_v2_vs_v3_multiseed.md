# BERT Shadow v2 vs v3 Multi-Seed

| System | Macro-F1 | Bal Acc | No Recall | Pos F1 | TP/FP/FN/TN |
| --- | --- | --- | --- | --- | --- |
| BERT shadow v1 | 0.496 | 0.505 | 0.333 | 0.730 | 23/6/11/3 |
| BERT shadow v2 | 0.703 | 0.797 | 0.889 | 0.814 | 24/1/10/8 |
| BERT shadow v3 mean | 0.745 ± 0.047 | 0.803 ± 0.074 | 0.800 ± 0.199 | 0.866 ± 0.033 | FP 1.800 ± 1.789; FN 6.600 ± 2.608 |

## Conclusion Template

MacBERT shadow experiment shows robust improvement under the current split, because the multi-seed mean exceeds the rule test split on macro-F1 and balanced accuracy.
