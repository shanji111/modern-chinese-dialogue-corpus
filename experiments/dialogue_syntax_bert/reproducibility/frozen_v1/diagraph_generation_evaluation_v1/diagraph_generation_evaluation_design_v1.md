# diagraph generation evaluation design v1

## 1. 本阶段目标

本阶段的目标是评估自动生成的跨句图谱纵栏质量，而不是继续修改 gold，也不是训练新模型。

当前冻结基准：50 pair / 135 active columns / 151 audit rows。

## 2. gold_v1 的角色

- `diagraph_gold_50_column_gold_v1` 只作为评估基准，不再修改。
- active 文件是主评估输入。
- all_rows 文件保留 keep / revise / delete / spot review 轨迹，用于审计。

## 3. BERT / hybrid 的角色

- 当前不让 BERT / hybrid 直接参与 column generation。
- 后续只考虑作为 reranker、filter 或 recall supplement。
- pair-level 分数不能替代 column-level 纵栏预测。

## 4. 为什么先做 rule-based baseline

- 当前数据更适合作为 evaluation set，而不是直接训练端到端 generator。
- rule baseline 可解释、可控、便于 error analysis。
- 先跑保守基线，更容易判断后续 BERT 应该介入哪里。

## 5. evaluation 的输入、输出与流程

### 输入

- `diagraph_gold_50_column_gold_v1_active.csv`
- `diagraph_gold_50_pair_list.csv`
- 任意符合 `diagraph_prediction_schema_v1.md` 的 prediction file

### 输出

- overall metrics summary
- per-pair precision / recall / F1
- relation_type confusion analysis
- core column analysis
- unmatched gold columns
- overgenerated prediction columns

### 流程

1. 读取 gold_v1 active
2. 读取 prediction file
3. 校验 prediction span 是否来自 turn_a / turn_b
4. 在 pair 内做 one-to-one matching
5. 先算 exact match，再算 relaxed match
6. 在 matched columns 上计算 relation_type / core 指标
7. 再算 overgeneration / undergeneration / resonance-degree 指标
8. 输出整体报告和 per-pair report

## 6. exact match 与 relaxed match

### exact match

建议 exact match 满足：

- 同一 `annotation_id`
- `pred_span_a == gold.span_a`
- `pred_span_b == gold.span_b`
- `pred_alignment_direction == gold.alignment_direction`

relation_type、core flag、supports_resonance 不并入 exact column matching，而在 matched columns 上单独评。

### relaxed match

建议 relaxed match 满足：

- 同一 `annotation_id`
- `pred_alignment_direction == gold.alignment_direction`
- `pred_span_a` 与 `gold.span_a` 为完全相等、包含关系，或非空重叠且较短 span 覆盖率 >= 0.5
- `pred_span_b` 与 `gold.span_b` 同理

relaxed match 用于回答：系统是否大致找到了该纵栏，但边界不够准。

## 7. 为什么要同时评 column-level / relation_type-level / core-column-level

- 只看 column F1，不知道 type 是否判断正确。
- 只看 type，也不知道主链有没有找回来。
- hard case 中最常见的问题是 auxiliary 被抬成 core，或主链漏掉。

因此应同时评：

- column-level matching
- relation_type accuracy
- core-column recall / precision
- overgeneration / undergeneration
- resonance-degree error

## 8. 本版本边界

本版本只产出 evaluation design 文档与 prediction template。

- 不修改 `gold_v1`
- 不训练模型
- 不运行 BERT
- 不实现正式 runner
- 不接网站
- 不读写正式数据库
