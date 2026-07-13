# AI exploratory annotation prompt v1

你正在做“现代汉语连续对话句法检索”的探索性标注，不是在生成金标准。只依据每条记录给出的两个话轮，不补充网络、常识或上下文。若信息不足，使用 `uncertain` 或 `?`，并在 `uncertainty_reason` 说明。

## 输入

每行包含 `annotation_id`、`turn_a`、`turn_b` 和来源信息。来源只用于事后切片，不得改变判断标准。

## 输出

对每个 `annotation_id` 输出一行 CSV，保留原 ID，并填写以下字段：

`resonance_present`（`yes`/`no`/`uncertain`）、`label_reproduction`、`label_parallelism`、`label_selective_reuse`、`label_repair`、`label_contrast`、`label_analogy_candidate`（均为 `1`/`0`/`?`）、`evidence_span_a`、`evidence_span_b`、`annotator_note`、`uncertainty_reason`、`ai_model`、`ai_prompt_version`、`ai_run_id`、`ai_confidence`、`ai_review_status`。

`evidence_span_a` 必须逐字出现在 `turn_a`，`evidence_span_b` 必须逐字出现在 `turn_b`。没有可复制的证据时留空并解释原因。`ai_confidence` 是 0 到 1 的数字；`ai_review_status` 使用 `ai_draft_v1`，二次审计使用 `ai_second_pass_v1`。

## 判断提示

- `resonance_present=yes`：后一个话轮对前一个话轮形成可解释的形式或功能呼应，不只是话题相同。
- `label_reproduction=1`：重复或近似重复前一话轮的词、结构或关键成分。
- `label_parallelism=1`：两个话轮形成可比的结构/功能对应，即使词汇不完全相同。
- `label_selective_reuse=1`：只复用前话轮的部分成分，并在新功能中重新组织。
- `label_repair=1`：后话轮修正、澄清、重说或处理前话轮的问题。
- `label_contrast=1`：后话轮以否定、转折、对照等方式回应前话轮。
- `label_analogy_candidate=1`：存在值得后续研究的类比/平行候选，但证据不足时仍可标为 `?`。

只返回 CSV，不附加解释性段落。此输出只用于开发集错误切片、提示词比较和不确定性分析；不要把它称为独立人工标注、金标准、确认性外部验证或生产排序依据。
