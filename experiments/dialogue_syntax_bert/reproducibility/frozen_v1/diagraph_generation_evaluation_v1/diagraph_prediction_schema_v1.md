# diagraph prediction schema v1

## 1. 目标

本文件定义自动图谱生成器的统一输出格式。任何 baseline、future generator、reranker 输出，只要要进入 evaluation runner，都应先转换到这个 schema。

## 2. 必备字段

| field | required | description |
| --- | --- | --- |
| `annotation_id` | yes | gold pair 对应 annotation id |
| `pair_id` | yes | pair id |
| `pred_column_id` | yes | 预测 column 局部编号，如 `P01` |
| `pred_span_a` | yes | 预测 A 侧 span |
| `pred_span_b` | yes | 预测 B 侧 span |
| `pred_relation_type` | yes | 预测 relation type |
| `pred_relation_strength` | yes | 预测 relation strength |
| `pred_alignment_direction` | yes | 预测方向 |
| `pred_is_core_column` | yes | 是否预测为 core |
| `pred_supports_resonance` | yes | 是否预测支撑 resonance |
| `pred_confidence` | keep-field | 可为空，但字段必须保留 |
| `generator_name` | yes | 生成器名称 |
| `generator_version` | yes | 生成器版本 |
| `notes` | no | 备注，可记录规则来源或 `needs_review` |

## 3. 字段约束

### span 约束

- `pred_span_a` 必须原样来自 `turn_a`
- `pred_span_b` 必须原样来自 `turn_b`
- 不允许生成原文中不存在的解释性实体

### relation_type 合法值

- `lexical_reproduction`
- `syntactic_parallelism`
- `semantic_substitution`
- `coreference_or_demonstrative`
- `slot_filling`
- `short_answer`
- `contrast`
- `repair`
- `analogy`
- `pragmatic_function`
- `punctuation_or_modal`
- `other`

### relation_strength 合法值

- `strong`
- `medium`
- `weak`

### alignment_direction 合法值

- `A_to_B`
- `B_to_A`
- `mutual`

### core / resonance 标志

- `pred_is_core_column` 推荐取值：`1` / `0` / `?`
- `pred_supports_resonance` 推荐取值：`1` / `0` / `?`
- 正式可评估输出优先使用 `1` / `0`；若 generator 暂时无法决定，可保留 `?`

### confidence

- `pred_confidence` 字段必须保留
- 可以为空
- 也可以使用 `high / medium / low`、0-1 分数或其他一致格式

## 4. 示例

```csv
annotation_id,pair_id,pred_column_id,pred_span_a,pred_span_b,pred_relation_type,pred_relation_strength,pred_alignment_direction,pred_is_core_column,pred_supports_resonance,pred_confidence,generator_name,generator_version,notes
F300V1-0001,2700001,P01,你,我,coreference_or_demonstrative,strong,A_to_B,1,1,0.83,rule_baseline,v1,role-shift candidate
```

## 5. 设计原则

- prediction schema 是 evaluation 输入，不是 gold
- schema 允许保守输出
- schema 不要求 generator 一次性覆盖所有 relation_type
- schema 不允许拿 pair-level 分数直接冒充 column prediction
