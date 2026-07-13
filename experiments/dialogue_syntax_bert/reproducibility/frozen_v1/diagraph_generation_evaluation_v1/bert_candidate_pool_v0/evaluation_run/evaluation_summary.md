# diagraph evaluation summary: bert_candidate_pool_v0

## Counts

- gold columns: 135
- valid predictions: 70
- invalid predictions: 0
- exact matches: 21
- relaxed matches: 51

## Column metrics

- exact precision: 0.3
- exact recall: 0.155556
- exact F1: 0.204878
- relaxed precision: 0.728571
- relaxed recall: 0.377778
- relaxed F1: 0.497561

## Type / core metrics

- relation_type accuracy on exact matches: 0.904762
- relation_type accuracy on relaxed matches: 0.627451
- core column precision: 0.688889
- core column recall: 0.313131
- missing-core rate: 0.686869
- false-core rate: 0.311111

## Generation balance

- overgeneration rate: 0.271429
- missing column rate: 0.622222
- mean abs column count error by pair: 1.46

## Pair-level diagnostics

- pairs with zero matched columns: 20
- pairs with missing core columns: 42
- pairs with high overgeneration: 4
