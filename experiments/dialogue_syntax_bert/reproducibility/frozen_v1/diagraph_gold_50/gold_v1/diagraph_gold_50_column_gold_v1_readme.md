# diagraph_gold_50 column gold v1

## What This Is

- 这是 `diagraph_gold_50` 的 column-level gold v1。
- `active` 文件是后续 column-level graph-generation evaluation 的主输入。
- `all_rows` 文件是审计输入，保留 keep / revise / delete / spot_review 轨迹。

## What It Is For

- 本 gold 用于评估跨句图谱纵栏生成质量。
- 它不用于重新训练 BERT。
- 它也不等于 pair-level gold；pair-level gold 与 column-level gold 分工不同。

## Suggested Evaluation Directions

- column precision
- column recall
- relation_type accuracy
- core column recall
- overgeneration rate
- missing-core rate
- resonance-degree error
