# Hybrid Shadow v1 Report

This is an offline rule+BERT hybrid shadow analysis. It uses existing MacBERT v3 multi-seed predictions and rule fields only; no new model is trained, no database is touched, and nothing is connected to the website.

## Strategy Results On Test

| Strategy | Thr | Macro-F1 | Bal Acc | No Recall | Pos F1 | TP/FP/FN/TN | Rule FN recovered | All yes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ensemble_mean | 0.683685 | 0.746 | 0.827 | 0.889 | 0.852 | 26/1/8/8 | 7 | False |
| rule_or_bert | 0.640379 | 0.779 | 0.815 | 0.778 | 0.892 | 29/2/5/7 | 8 | False |
| rule_and_bert | 0.683685 | 0.631 | 0.779 | 1.000 | 0.717 | 19/0/15/9 | 0 | False |
| rule_priority_with_bert_recall | 0.640379 | 0.779 | 0.815 | 0.778 | 0.892 | 29/2/5/7 | 8 | False |
| bert_with_rule_veto | 0.683685 | 0.703 | 0.797 | 0.889 | 0.814 | 24/1/10/8 | 7 | False |
| bert_with_rule_veto_plus_topic_guard | 0.200564 | 0.669 | 0.742 | 0.778 | 0.800 | 24/2/10/7 | 5 | False |

## Baseline References

- majority/similarity: macro-F1≈0.442, balanced accuracy=0.500, no recall=0
- rule full-set: macro-F1=0.548, balanced accuracy=0.623
- rule test split: macro-F1=0.642, balanced accuracy=0.753
- MacBERT v3 mean: macro-F1=0.745 ± 0.047, balanced accuracy=0.803 ± 0.074

## Interpretation

- `rule_or_bert` targets recall and should be checked for false-positive growth.
- `rule_and_bert` targets precision but can suppress recall.
- `rule_priority_with_bert_recall` preserves direct rule positives while allowing high-confidence BERT recovery for rule-negative rows.
- `bert_with_rule_veto` currently only implements an available question-response veto; stronger negative patterns remain future work.
- `bert_with_rule_veto_plus_topic_guard` is exploratory and uses a conservative no-rule/no-cue topic guard; it should not be deployed without more data.
