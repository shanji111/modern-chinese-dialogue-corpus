# Hybrid Error Analysis

This file compares false positives, false negatives, and rule-FN recovery across hybrid strategies.

## ensemble_mean

- FP count: 1; IDs: F300V1-0221
- FN count: 8; IDs: F300V1-0006, F300V1-0060, F300V1-0092, F300V1-0111, F300V1-0205, F300V1-0211, F300V1-0214, F300V1-0234
- FP risk types: `{"topic_related_but_not_resonance": 1}`
- FN risk types: `{"short_answer": 2, "demonstrative_or_reference": 5, "semantic_selection": 1}`
- Rule FN recovered: 7

## rule_or_bert

- FP count: 2; IDs: F300V1-0078, F300V1-0221
- FN count: 5; IDs: F300V1-0092, F300V1-0111, F300V1-0205, F300V1-0211, F300V1-0234
- FP risk types: `{"question_response": 1, "topic_related_but_not_resonance": 1}`
- FN risk types: `{"short_answer": 1, "semantic_selection": 1, "demonstrative_or_reference": 3}`
- Rule FN recovered: 8

## rule_and_bert

- FP count: 0; IDs: (none)
- FN count: 15; IDs: F300V1-0006, F300V1-0060, F300V1-0092, F300V1-0111, F300V1-0137, F300V1-0141, F300V1-0154, F300V1-0205, F300V1-0211, F300V1-0214, F300V1-0224, F300V1-0234, F300V1-0235, F300V1-0250, F300V1-0279
- FP risk types: `{}`
- FN risk types: `{"short_answer": 3, "demonstrative_or_reference": 10, "semantic_selection": 1, "analogy": 1}`
- Rule FN recovered: 0

## rule_priority_with_bert_recall

- FP count: 2; IDs: F300V1-0078, F300V1-0221
- FN count: 5; IDs: F300V1-0092, F300V1-0111, F300V1-0205, F300V1-0211, F300V1-0234
- FP risk types: `{"question_response": 1, "topic_related_but_not_resonance": 1}`
- FN risk types: `{"short_answer": 1, "semantic_selection": 1, "demonstrative_or_reference": 3}`
- Rule FN recovered: 8

## bert_with_rule_veto

- FP count: 1; IDs: F300V1-0221
- FN count: 10; IDs: F300V1-0006, F300V1-0060, F300V1-0077, F300V1-0092, F300V1-0111, F300V1-0167, F300V1-0205, F300V1-0211, F300V1-0214, F300V1-0234
- FP risk types: `{"topic_related_but_not_resonance": 1}`
- FN risk types: `{"short_answer": 2, "demonstrative_or_reference": 6, "semantic_selection": 1, "slot_filling": 1}`
- Rule FN recovered: 7

## bert_with_rule_veto_plus_topic_guard

- FP count: 2; IDs: F300V1-0115, F300V1-0142
- FN count: 10; IDs: F300V1-0077, F300V1-0154, F300V1-0167, F300V1-0205, F300V1-0211, F300V1-0214, F300V1-0224, F300V1-0234, F300V1-0235, F300V1-0250
- FP risk types: `{"topic_related_but_not_resonance": 2}`
- FN risk types: `{"demonstrative_or_reference": 9, "slot_filling": 1}`
- Rule FN recovered: 5

