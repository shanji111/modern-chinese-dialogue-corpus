# diagraph evaluation metrics spec v1

## 1. matching 总则

- 所有 matching 都应在同一 pair 内进行。
- 使用 one-to-one matching，避免一个 pred 重复命中多个 gold。
- exact 与 relaxed 应各自独立做匹配。

## 2. A. Column matching metrics

### exact column precision
```
exact_precision = exact_matched_pred_columns / all_pred_columns
```

### exact column recall
```
exact_recall = exact_matched_gold_columns / all_gold_columns
```

### exact column F1
```
exact_f1 = 2 * precision * recall / (precision + recall)
```

### relaxed column precision / recall / F1
```
relaxed_precision = relaxed_matched_pred_columns / all_pred_columns
relaxed_recall = relaxed_matched_gold_columns / all_gold_columns
relaxed_f1 = 2 * relaxed_precision * relaxed_recall / (relaxed_precision + relaxed_recall)
```

## 3. B. Relation metrics

- relation_type accuracy on matched columns
- relation_type macro accuracy / per-type accuracy
- confusion matrix

建议公式：

```
relation_type_accuracy = matched_columns_with_correct_type / all_matched_columns
```

## 4. C. Core column metrics

```
core_recall = correctly_predicted_gold_core_columns / all_gold_core_columns
core_precision = predicted_core_columns_aligned_to_gold_core / all_predicted_core_columns
missing_core_rate = gold_core_columns_not_recovered_as_core / all_gold_core_columns
false_core_rate = predicted_core_columns_not_supported_by_gold_core / all_predicted_core_columns
```

## 5. D. Overgeneration / undergeneration

```
overgeneration_rate = unmatched_pred_columns / all_pred_columns
missing_column_rate = unmatched_gold_columns / all_gold_columns
pair_column_count_error = abs(predicted_column_count - gold_column_count)
aux_overgeneration_rate = unmatched_pred_auxiliary_columns / all_pred_auxiliary_columns
```

## 6. E. Resonance degree metrics

建议同时保留 unweighted 与 weighted 两版：

```
gold_resonance_degree = count(gold columns where supports_resonance = 1)
weighted_gold_degree = 1.0 * gold_core_count + 0.5 * gold_aux_supporting_count
pred_resonance_degree = count(pred columns where pred_supports_resonance = 1)
abs_error = abs(pred_degree - gold_degree)
mae = average(abs_error over pairs)
```

并按 difficulty / source / dataset_name 进一步分组。

## 7. F. Pair-level summary

- per-pair precision / recall / F1
- samples with zero matched columns
- samples with missing core columns
- samples with high overgeneration

## 8. 推荐呈现顺序

1. overall exact / relaxed metrics
2. relation_type metrics
3. core-column metrics
4. overgeneration / undergeneration
5. resonance-degree error
6. per-pair worst cases
