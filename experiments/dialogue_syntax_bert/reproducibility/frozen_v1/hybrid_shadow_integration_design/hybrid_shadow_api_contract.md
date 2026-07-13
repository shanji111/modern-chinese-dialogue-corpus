# Hybrid Shadow API Contract

This is an offline interface design. It is not a production route and should not be connected to the website without a separate implementation review.

## Scope

The API consumes one adjacent-turn pair plus existing rule evidence. It returns BERT confidence and hybrid metadata. It does not write to the database and does not generate graph edges.

## Input Fields

Required:

- `pair_id`
- `turn_a`
- `turn_b`
- `rule_any_positive`
- `rule_flags`
- `shared_terms`

Recommended when available:

- `graph_evidence`
- `source`
- `dataset_name`
- `conversation_group_key`
- `sample_stratum`

Rule flags should include:

- `has_lexical_echo`
- `has_pattern_reuse`
- `has_question_response`
- `has_negation_turn`
- `has_repair_repetition`

`graph_evidence` can include rule-derived nodes, edges, matched spans, or reusable syntax resources. BERT must not invent this evidence.

## Output Fields

Required:

- `bert_prob`
- `bert_pred`
- `hybrid_pred`
- `hybrid_strategy`
- `confidence_bucket`
- `recall_supplement_flag`
- `warning_flags`
- `explanation_summary`

Recommended:

- `rule_pred`
- `rule_summary`
- `bert_model_id`
- `bert_threshold`
- `hybrid_threshold`
- `shadow_version`

## Strategy

Use:

`rule_priority_with_bert_recall`

Logic:

1. If `rule_any_positive=1`, keep `hybrid_pred=yes`.
2. If `rule_any_positive=0`, allow `hybrid_pred=yes` only when `bert_prob >= high_threshold`.
3. If warning flags indicate a known false-positive risk, keep the pair in review/low-confidence mode rather than treating BERT as decisive.

## Confidence Bucket

Suggested buckets:

- `high`: strong rule evidence or high BERT probability with supporting surface evidence.
- `medium`: BERT high but rule-negative, or rule-positive with weak BERT support.
- `low`: conflicting signals, no surface overlap, or known false-positive risk.

The exact thresholds should be calibrated only on dev data or a future validation set, never on test data.

## Warning Flags

Warning flags should include:

- `topic_related_but_not_resonance_risk`
- `short_answer_risk`
- `demonstrative_reference_risk`
- `no_surface_overlap_risk`

Optional future flags:

- `ordinary_question_answer_risk`
- `context_truncation_risk`
- `genre_noise_risk`

## Explanation Summary

`explanation_summary` must prioritize rule evidence.

Suggested format:

1. Rule evidence: matched spans, flags, and graph evidence.
2. BERT score: pair-level semantic confidence only.
3. Hybrid note: whether BERT supplemented recall or only confirmed rule evidence.
4. Warning note: known false-positive or uncertainty risks.

Bad summary:

`AI says this is resonance.`

Acceptable summary:

`Rule evidence did not fire. MacBERT probability is high, so this pair is marked as possible hidden resonance. No graph evidence is generated; manual review is recommended.`

