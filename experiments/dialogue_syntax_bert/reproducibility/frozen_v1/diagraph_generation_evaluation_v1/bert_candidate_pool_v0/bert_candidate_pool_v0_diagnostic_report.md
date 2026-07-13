# bert_candidate_pool_v0 diagnostic report

- candidate pool total columns: 70
- covered pairs: 33 / 50
- exact P/R/F1: 0.3 / 0.155556 / 0.204878
- relaxed P/R/F1: 0.728571 / 0.377778 / 0.497561
- core recall: 0.313131
- overgeneration_rate: 0.271429

## candidate_tier counts

- high_precision_rule: 39 candidates across 25 pairs
- precision_ablation_only: 3 candidates across 3 pairs
- recall_rule_only: 28 candidates across 21 pairs

## relation_type counts

- contrast: 5
- coreference_or_demonstrative: 18
- lexical_reproduction: 28
- repair: 1
- short_answer: 7
- slot_filling: 11

## Remaining blind spots

- pairs with zero candidates: F300V1-0017, F300V1-0033, F300V1-0052, F300V1-0092, F300V1-0097, F300V1-0106, F300V1-0117, F300V1-0150, F300V1-0154, F300V1-0159, F300V1-0185, F300V1-0205, F300V1-0219, F300V1-0220, F300V1-0224, F300V1-0244, F300V1-0265
- unmatched gold core columns after relaxed matching: 56
- top pairs with uncovered core columns: F300V1-0244 (3), F300V1-0127 (2), F300V1-0196 (2), F300V1-0211 (2), F300V1-0254 (2), F300V1-0185 (2), F300V1-0265 (2), F300V1-0298 (2)

## Overgenerated candidates that most need BERT filter

- overgenerated preview: F300V1-0002/CP02 short_answer [recall_rule_only], F300V1-0008/CP02 coreference_or_demonstrative [recall_rule_only], F300V1-0023/CP04 short_answer [recall_rule_only], F300V1-0024/CP01 contrast [high_precision_rule], F300V1-0055/CP03 slot_filling [high_precision_rule], F300V1-0081/CP01 lexical_reproduction [high_precision_rule], F300V1-0081/CP02 coreference_or_demonstrative [recall_rule_only], F300V1-0127/CP01 coreference_or_demonstrative [high_precision_rule], F300V1-0128/CP01 slot_filling [precision_ablation_only], F300V1-0128/CP02 short_answer [recall_rule_only]

## Interpretation

- v1.1 is not suitable as a standalone pool because it improves cleanliness by shrinking coverage too aggressively.
- v1 is still the better recall base because it keeps more candidates and more matched columns alive for downstream filtering.
- the first BERT stage should be reranker/filter, not end-to-end generator, because the current 50-pair / 135-column gold_v1 is strong enough for evaluation and diagnostic slicing but too small for direct span-generation training.
- gold_v1 is used here only for offline evaluation and diagnosis, not for candidate creation logic.

## Gold reference note

- gold active columns for offline diagnosis: 135
