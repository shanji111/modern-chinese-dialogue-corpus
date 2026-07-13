# Hybrid Shadow Recommendation

Best post-hoc hybrid strategy in this run: `rule_or_bert`.

- test macro-F1: 0.779
- test balanced accuracy: 0.815
- test no-class recall: 0.778
- test positive F1: 0.892
- TP/FP/FN/TN: 29/2/5/7
- rule FN recovered: 8
- rule test split reference: macro-F1=0.642, balanced accuracy=0.753

## Tradeoff

- Pure ensemble_mean FP/FN: 1/8
- Best hybrid FP/FN: 2/5
- The best hybrid improves recall and macro-F1 over pure ensemble_mean, but it does not reduce false positives; it accepts one extra false positive to recover more rule false negatives.
- The stable topic-related false positive remains a risk and should be highlighted in any future shadow UI.

## Integration Recommendation

Recommend moving toward website shadow integration only as an offline-visible auxiliary signal first, not as an automatic production decision.

BERT should be integrated as:

- reranker
- confidence scorer
- recall supplement
- not graph generator

Rule graph explanations should remain visible. The BERT score can help prioritize or flag hidden carry-over, but it should not replace rule evidence or generate graph edges by itself.

## Guardrails

- Do not automatically rewrite gold labels.
- Do not use BERT outputs to mutate corpus.db.
- Keep test-set threshold selection prohibited.
- More gold data is still needed before production routing.
- Add a shadow-only UI flag or offline export before any user-facing automatic behavior.
- The best hybrid beats rule test macro-F1 in this split, but should still remain shadow-only until validated on more data.
