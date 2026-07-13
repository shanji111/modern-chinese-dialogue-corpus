# bert_assisted_prototype_v0 report

- MacBERT loaded successfully: yes
- model path: D:\hf_models\hfl_chinese_macbert_base
- model training in this step: no
- model fine-tuning in this step: no
- candidate rows scored: 70
- scoring input rows: 70
- offline evaluation label rows: 70
- best filter strategy: rule_pool_no_filter
- better than no_filter: no

## Shadow score definition

- `pair_context_similarity`: cosine similarity between frozen MacBERT embeddings of `turn_a` and `turn_b`.
- `span_pair_similarity`: cosine similarity between frozen MacBERT embeddings of `pred_span_a` and `pred_span_b`.
- `candidate_context_fit_score`: normalized heuristic score built from frozen MacBERT span similarity and context-vs-span+relation similarity.
- These are shadow scores only, not trained probabilities.

## Score vs relaxed-match label

- mean candidate_context_fit_score on relaxed-kept candidates: 0.930190
- mean candidate_context_fit_score on relaxed-rejected candidates: 0.907118

## Tier signals

- high_precision_rule: 30 / 39 relaxed-kept
- recall_rule_only: 19 / 28 relaxed-kept
- precision_ablation_only: 2 / 3 relaxed-kept

## Relation-type difficulty

- contrast: keep-label rate 0.800 (4/5)
- coreference_or_demonstrative: keep-label rate 0.667 (12/18)
- lexical_reproduction: keep-label rate 0.821 (23/28)
- repair: keep-label rate 1.000 (1/1)
- short_answer: keep-label rate 0.571 (4/7)
- slot_filling: keep-label rate 0.636 (7/11)

## Strategy comparison

- no_filter relaxed F1: 0.497561
- best strategy relaxed F1: 0.497561
- no_filter overgeneration: 0.271429
- best strategy overgeneration: 0.271429

## Recommendation

- move to supervised reranker next: yes, cautiously
- Keep the next stage focused on binary keep/filter plus relation-type sanity check.
- Do not let BERT directly generate spans or new columns at this stage.
- 70 candidates / 50 pairs are still too small and too evaluation-oriented for training a large end-to-end generator.

## Boundary notes

- This round used BERT only for offline shadow scoring.
- This round did not train or fine-tune any model.
- This round did not modify gold.
- This round did not touch the website.

## Score distribution snapshot

- pair_context_similarity mean: 0.823066
- span_pair_similarity mean: 0.876236
- candidate_context_fit_score mean: 0.923927
