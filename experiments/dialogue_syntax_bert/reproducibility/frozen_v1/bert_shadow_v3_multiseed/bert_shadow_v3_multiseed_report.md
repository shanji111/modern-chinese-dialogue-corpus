# BERT Shadow v3 Multi-Seed Report

This is an offline shadow experiment. It does not connect to the website, does not deploy, does not read or write the formal database, and does not modify gold or split files.

## Per-Seed Test Results

| Seed | Thr | Macro-F1 | Bal Acc | No Recall | Pos F1 | TP/FP/FN/TN | Rule FN recovered | All yes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20260621 | 0.555198 | 0.703 | 0.797 | 0.889 | 0.814 | 24/1/10/8 | 5 | False |
| 42 | 0.677419 | 0.746 | 0.827 | 0.889 | 0.852 | 26/1/8/8 | 6 | False |
| 1234 | 0.548311 | 0.693 | 0.678 | 0.444 | 0.886 | 31/5/3/4 | 11 | False |
| 2025 | 0.745037 | 0.792 | 0.856 | 0.889 | 0.889 | 28/1/6/8 | 8 | False |
| 3407 | 0.882965 | 0.792 | 0.856 | 0.889 | 0.889 | 28/1/6/8 | 8 | False |

## Mean +/- Std

- test macro-F1: 0.745 ± 0.047
- test balanced accuracy: 0.803 ± 0.074
- test no-class recall: 0.800 ± 0.199
- test positive F1: 0.866 ± 0.033
- test FP count: 1.800 ± 1.789
- test FN count: 6.600 ± 2.608
- rule FN recovery count: 7.600 ± 2.302

## Baseline Comparison

- majority/similarity: macro-F1≈0.442, balanced accuracy=0.500, no recall=0
- rule full-set: macro-F1=0.548, balanced accuracy=0.623
- rule test split: macro-F1=0.642, balanced accuracy=0.753
- seeds exceeding majority/similarity: 5 / 5
- seeds exceeding rule full-set: 5 / 5
- seeds exceeding rule test split: 4 / 5
- seeds with no-class recall > 0: 5 / 5
- all-yes seeds: none
