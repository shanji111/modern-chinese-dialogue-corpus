# Hybrid Shadow Integration Design

This document describes a future offline/shadow integration design for dialogue-syntax resonance search. It does not implement production routes, does not change the database, and does not modify gold labels.

## Recommended Strategy

Use `rule_priority_with_bert_recall` as the recommended hybrid strategy name.

Current shadow result:

- Rule test split: macro-F1 = 0.642, balanced accuracy = 0.753
- MacBERT v3 mean: macro-F1 = 0.745, balanced accuracy = 0.803
- Best hybrid: macro-F1 = 0.779, balanced accuracy = 0.815
- Best hybrid TP/FP/FN/TN = 29/2/5/7
- Rule false negatives recovered = 8

The strategy should be interpreted as:

1. Trust rule-positive pairs as interpretable candidates.
2. Use BERT only to supplement recall for rule-negative pairs with high semantic confidence.
3. Keep rule evidence as the primary explanation layer.

## Why BERT Should Not Replace Rules

BERT is useful for pair-level semantic confidence, especially when the resonance is implicit. But it does not produce an inspectable syntax graph, it can over-score topic-related non-resonance, and its confidence is not a linguistic explanation.

The rule system remains essential because it provides:

- Observable surface evidence.
- Stable graph construction inputs.
- Debuggable rule flags.
- A clear audit trail for why a pair was retrieved.

Replacing the rule system with BERT would weaken interpretability and make the search experience harder to explain.

## Rule System Responsibilities

The rule system should remain responsible for:

- Candidate recall.
- Surface pattern evidence.
- Cross-turn graph explanation.
- Interpretable rule flags such as lexical echo, pattern reuse, question-response, negation, and repair repetition.
- Human-readable evidence summaries.

Rules should continue to produce the graph-level explanation, even when BERT contributes a high confidence score.

## BERT Responsibilities

BERT should be responsible for:

- Pair-level semantic confidence.
- Reranking among existing or sampled candidates.
- Recall supplement for rule-negative but semantically resonant pairs.
- Confidence scoring for possible hidden resonance.

BERT is especially relevant for:

- Demonstrative/reference carry-over.
- Short-answer resonance.
- Slot filling with little lexical reuse.
- Semantic selection that is not captured by current rule flags.

## Hybrid Responsibilities

The hybrid layer should:

- Combine `rule_any_positive` and BERT probability.
- Apply the named strategy `rule_priority_with_bert_recall`.
- Recommend a confidence level.
- Mark potential hidden resonance.
- Preserve all rule evidence in the output.
- Surface warning flags when the pair resembles known error modes.

The hybrid layer should not collapse rule and BERT into a single opaque judgment. It should report both channels.

## What BERT Must Not Do

BERT must not:

- Generate graph edges.
- Generate cross-sentence syntax graphs.
- Automatically write to any database.
- Modify gold labels.
- Replace human judgment.
- Serve as the only explanation source.
- Decide production search ranking without shadow evaluation.

## Known Risk

The stable false positive `F300V1-0221` shows that MacBERT can still mistake topic-related continuity for dialogue-syntax resonance. Any integration must keep this distinction visible:

Topic relatedness is not the same as dialogue-syntax resonance.

