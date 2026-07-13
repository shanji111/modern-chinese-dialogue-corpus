# bert_assisted_filtering_simulation_report

- evaluated strategies: rule_pool_no_filter, bert_span_similarity_top, tier_aware_filter, relation_type_sanity_filter
- best strategy by relaxed F1: rule_pool_no_filter

| strategy | candidate_count | relaxed P | relaxed R | relaxed F1 | core recall | overgeneration |
| --- | --- | --- | --- | --- | --- | --- |
| rule_pool_no_filter | 70 | 0.728571 | 0.377778 | 0.497561 | 0.313131 | 0.271429 |
| bert_span_similarity_top | 43 | 0.790698 | 0.251852 | 0.382022 | 0.222222 | 0.209302 |
| tier_aware_filter | 50 | 0.78 | 0.288889 | 0.421622 | 0.252525 | 0.22 |
| relation_type_sanity_filter | 52 | 0.769231 | 0.296296 | 0.427807 | 0.252525 | 0.230769 |

## Interpretation

- All filtered predictions here are simulations built on top of the candidate pool.
- They are not final deployed systems and do not modify gold or baseline artifacts.
