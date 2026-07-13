# similarity baseline on gold_v1_binary

- Uses training: no.
- Runs BERT: no.
- Features: char_unigram_jaccard, char_bigram_jaccard, char_overlap_ratio, length_ratio, rule_any_positive_score, rule_flag_count, combined_similarity_score.
- Threshold selection: threshold swept on dev split for best F1; no model training.
- selected threshold: 0.000

## Metrics

|set|precision|recall|f1|tp|fp|fn|tn|total|
|---|---|---|---|---|---|---|---|---|
|dev|0.791|1.000|0.883|34|9|0|0|43|
|test|0.791|1.000|0.883|34|9|0|0|43|
|full|0.797|1.000|0.887|228|58|0|0|286|

## Comparison with rule baseline

- rule baseline full precision / recall / F1: 0.873 / 0.575 / 0.693
- similarity full precision / recall / F1: 0.797 / 1.000 / 0.887
- similarity test precision / recall / F1: 0.791 / 1.000 / 0.883

## Failure case analysis

Similarity false negatives still include hidden semantic selection, slot filling, demonstrative/reference uptake, short answers, and analogy-like mappings. Similarity false positives usually come from surface overlap without stable resonance.

## Notes

This is a non-training baseline. It uses a fixed weighted score and a dev-set threshold sweep, not model fitting.
