# rule_baseline_v1 generation report

## Overview

- total pairs scanned: 50
- predicted columns generated: 67
- covered pairs: 33
- empty-prediction pairs: 17
- max candidates per pair: 5

## Conservative design choices

- baseline v1 only reads `diagraph_gold_50_pair_list.csv` turn text and does not read the formal database.
- baseline v1 prioritizes high-precision rules for lexical reproduction, demonstrative/coreference, slot filling, short answer, contrast, and repair.
- `semantic_substitution` is effectively near-dormant and only fires on explicit rename-style surface patterns.
- `analogy` is intentionally not auto-generated in v1; this is a deliberate conservative baseline choice.
- some pairs are allowed to stay empty rather than forcing low-quality columns.

## Relation type distribution

- lexical_reproduction: 28
- coreference_or_demonstrative: 18
- slot_filling: 8
- short_answer: 7
- contrast: 5
- repair: 1

## Confidence distribution

- medium: 52
- low: 9
- high: 6

## Triggered rule distribution

- lexical_reproduction: 28
- coreference_or_demonstrative: 18
- slot_filling: 8
- short_answer: 7
- contrast: 5
- repair: 1

## Per-pair candidate count distribution

- 0 columns: 17 pairs
- 1 columns: 13 pairs
- 2 columns: 9 pairs
- 3 columns: 8 pairs
- 4 columns: 3 pairs

## Pairs with no prediction

F300V1-0017, F300V1-0033, F300V1-0052, F300V1-0092, F300V1-0097, F300V1-0106, F300V1-0117, F300V1-0150, F300V1-0154, F300V1-0159, F300V1-0185, F300V1-0205, F300V1-0219, F300V1-0220, F300V1-0224, F300V1-0244, F300V1-0265

