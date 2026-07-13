# diagraph evaluation summary: rule_baseline_prediction_v1

## Counts

- gold columns: 135
- valid predictions: 67
- invalid predictions: 0
- exact matches: 21
- relaxed matches: 49

## Column metrics

- exact precision: 0.313433
- exact recall: 0.155556
- exact F1: 0.207921
- relaxed precision: 0.731343
- relaxed recall: 0.362963
- relaxed F1: 0.485149

## Type / core metrics

- relation_type accuracy on exact matches: 0.904762
- relation_type accuracy on relaxed matches: 0.591837
- core column precision: 0.717949
- core column recall: 0.282828
- missing-core rate: 0.717172
- false-core rate: 0.282051

## Generation balance

- overgeneration rate: 0.268657
- missing column rate: 0.637037
- mean abs column count error by pair: 1.48

## Pair-level diagnostics

- pairs with zero matched columns: 20
- pairs with missing core columns: 43
- pairs with high overgeneration: 3
