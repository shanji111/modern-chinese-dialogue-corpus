import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE_DIR = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_gold_50",
);
const GOLD_DIR = path.join(BASE_DIR, "gold_v1");
const OUTPUT_DIR = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_generation_evaluation_v1",
);
const TEMPLATE_DIR = path.join(OUTPUT_DIR, "diagraph_evaluation_input_templates");

const INPUTS = {
  activeGold: path.join(GOLD_DIR, "diagraph_gold_50_column_gold_v1_active.csv"),
  allRowsGold: path.join(GOLD_DIR, "diagraph_gold_50_column_gold_v1_all_rows.csv"),
  metadata: path.join(GOLD_DIR, "diagraph_gold_50_column_gold_v1_metadata.json"),
  pairList: path.join(BASE_DIR, "diagraph_gold_50_pair_list.csv"),
  guideV2: path.join(BASE_DIR, "diagraph_gold_50_annotation_guide_v2.md"),
};

const OUTPUTS = {
  design: path.join(OUTPUT_DIR, "diagraph_generation_evaluation_design_v1.md"),
  schema: path.join(OUTPUT_DIR, "diagraph_prediction_schema_v1.md"),
  metrics: path.join(OUTPUT_DIR, "diagraph_evaluation_metrics_spec_v1.md"),
  runnerPlan: path.join(OUTPUT_DIR, "diagraph_evaluation_runner_plan_v1.md"),
  ruleBaseline: path.join(OUTPUT_DIR, "diagraph_rule_baseline_plan_v1.md"),
  bertRoadmap: path.join(OUTPUT_DIR, "diagraph_bert_assisted_generation_roadmap_v1.md"),
  readme: path.join(OUTPUT_DIR, "diagraph_generation_evaluation_readme.md"),
  predictionCsv: path.join(TEMPLATE_DIR, "prediction_template.csv"),
  predictionXlsx: path.join(TEMPLATE_DIR, "prediction_template.xlsx"),
};

const PREDICTION_FIELDS = [
  "annotation_id",
  "pair_id",
  "pred_column_id",
  "pred_span_a",
  "pred_span_b",
  "pred_relation_type",
  "pred_relation_strength",
  "pred_alignment_direction",
  "pred_is_core_column",
  "pred_supports_resonance",
  "pred_confidence",
  "generator_name",
  "generator_version",
  "notes",
];

const VALID_RELATION_TYPES = [
  "lexical_reproduction",
  "syntactic_parallelism",
  "semantic_substitution",
  "coreference_or_demonstrative",
  "slot_filling",
  "short_answer",
  "contrast",
  "repair",
  "analogy",
  "pragmatic_function",
  "punctuation_or_modal",
  "other",
];
const VALID_RELATION_STRENGTH = ["strong", "medium", "weak"];
const VALID_ALIGNMENT_DIRECTION = ["A_to_B", "B_to_A", "mutual"];
const VALID_BINARY_OR_UNKNOWN = ["1", "0", "?"];

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        cell += ch;
      }
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else if (ch !== "\r") {
      cell += ch;
    }
  }
  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }

  const [header = [], ...dataRows] = rows;
  if (header.length > 0) {
    header[0] = header[0].replace(/^\uFEFF/, "");
  }
  return {
    header,
    rows: dataRows.filter((dataRow) => dataRow.some((value) => value !== "")),
  };
}

function readCsvTable(text) {
  const { header, rows } = parseCsv(text);
  return {
    header,
    rows: rows.map((row) =>
      Object.fromEntries(header.map((column, index) => [column, row[index] ?? ""])),
    ),
  };
}

function escapeCsv(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function toCsv(header, rows) {
  const lines = [
    header.map((column) => escapeCsv(column)).join(","),
    ...rows.map((row) => header.map((column) => escapeCsv(row[column] ?? "")).join(",")),
  ];
  return `\uFEFF${lines.join("\r\n")}\r\n`;
}

function toColumnLabel(index) {
  let n = index + 1;
  let label = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    label = String.fromCharCode(65 + rem) + label;
    n = Math.floor((n - 1) / 26);
  }
  return label;
}

function buildDesignMd(meta) {
  return [
    "# diagraph generation evaluation design v1",
    "",
    "## 1. 本阶段目标",
    "",
    "本阶段的目标是评估自动生成的跨句图谱纵栏质量，而不是继续修改 gold，也不是训练新模型。",
    "",
    `当前冻结基准：${meta.pair_count} pair / ${meta.active_column_count} active columns / ${meta.all_rows_count} audit rows。`,
    "",
    "## 2. gold_v1 的角色",
    "",
    "- `diagraph_gold_50_column_gold_v1` 只作为评估基准，不再修改。",
    "- active 文件是主评估输入。",
    "- all_rows 文件保留 keep / revise / delete / spot review 轨迹，用于审计。",
    "",
    "## 3. BERT / hybrid 的角色",
    "",
    "- 当前不让 BERT / hybrid 直接参与 column generation。",
    "- 后续只考虑作为 reranker、filter 或 recall supplement。",
    "- pair-level 分数不能替代 column-level 纵栏预测。",
    "",
    "## 4. 为什么先做 rule-based baseline",
    "",
    "- 当前数据更适合作为 evaluation set，而不是直接训练端到端 generator。",
    "- rule baseline 可解释、可控、便于 error analysis。",
    "- 先跑保守基线，更容易判断后续 BERT 应该介入哪里。",
    "",
    "## 5. evaluation 的输入、输出与流程",
    "",
    "### 输入",
    "",
    "- `diagraph_gold_50_column_gold_v1_active.csv`",
    "- `diagraph_gold_50_pair_list.csv`",
    "- 任意符合 `diagraph_prediction_schema_v1.md` 的 prediction file",
    "",
    "### 输出",
    "",
    "- overall metrics summary",
    "- per-pair precision / recall / F1",
    "- relation_type confusion analysis",
    "- core column analysis",
    "- unmatched gold columns",
    "- overgenerated prediction columns",
    "",
    "### 流程",
    "",
    "1. 读取 gold_v1 active",
    "2. 读取 prediction file",
    "3. 校验 prediction span 是否来自 turn_a / turn_b",
    "4. 在 pair 内做 one-to-one matching",
    "5. 先算 exact match，再算 relaxed match",
    "6. 在 matched columns 上计算 relation_type / core 指标",
    "7. 再算 overgeneration / undergeneration / resonance-degree 指标",
    "8. 输出整体报告和 per-pair report",
    "",
    "## 6. exact match 与 relaxed match",
    "",
    "### exact match",
    "",
    "建议 exact match 满足：",
    "",
    "- 同一 `annotation_id`",
    "- `pred_span_a == gold.span_a`",
    "- `pred_span_b == gold.span_b`",
    "- `pred_alignment_direction == gold.alignment_direction`",
    "",
    "relation_type、core flag、supports_resonance 不并入 exact column matching，而在 matched columns 上单独评。",
    "",
    "### relaxed match",
    "",
    "建议 relaxed match 满足：",
    "",
    "- 同一 `annotation_id`",
    "- `pred_alignment_direction == gold.alignment_direction`",
    "- `pred_span_a` 与 `gold.span_a` 为完全相等、包含关系，或非空重叠且较短 span 覆盖率 >= 0.5",
    "- `pred_span_b` 与 `gold.span_b` 同理",
    "",
    "relaxed match 用于回答：系统是否大致找到了该纵栏，但边界不够准。",
    "",
    "## 7. 为什么要同时评 column-level / relation_type-level / core-column-level",
    "",
    "- 只看 column F1，不知道 type 是否判断正确。",
    "- 只看 type，也不知道主链有没有找回来。",
    "- hard case 中最常见的问题是 auxiliary 被抬成 core，或主链漏掉。",
    "",
    "因此应同时评：",
    "",
    "- column-level matching",
    "- relation_type accuracy",
    "- core-column recall / precision",
    "- overgeneration / undergeneration",
    "- resonance-degree error",
    "",
    "## 8. 本版本边界",
    "",
    "本版本只产出 evaluation design 文档与 prediction template。",
    "",
    "- 不修改 `gold_v1`",
    "- 不训练模型",
    "- 不运行 BERT",
    "- 不实现正式 runner",
    "- 不接网站",
    "- 不读写正式数据库",
    "",
  ].join("\n");
}

function buildSchemaMd() {
  return [
    "# diagraph prediction schema v1",
    "",
    "## 1. 目标",
    "",
    "本文件定义自动图谱生成器的统一输出格式。任何 baseline、future generator、reranker 输出，只要要进入 evaluation runner，都应先转换到这个 schema。",
    "",
    "## 2. 必备字段",
    "",
    "| field | required | description |",
    "| --- | --- | --- |",
    "| `annotation_id` | yes | gold pair 对应 annotation id |",
    "| `pair_id` | yes | pair id |",
    "| `pred_column_id` | yes | 预测 column 局部编号，如 `P01` |",
    "| `pred_span_a` | yes | 预测 A 侧 span |",
    "| `pred_span_b` | yes | 预测 B 侧 span |",
    "| `pred_relation_type` | yes | 预测 relation type |",
    "| `pred_relation_strength` | yes | 预测 relation strength |",
    "| `pred_alignment_direction` | yes | 预测方向 |",
    "| `pred_is_core_column` | yes | 是否预测为 core |",
    "| `pred_supports_resonance` | yes | 是否预测支撑 resonance |",
    "| `pred_confidence` | keep-field | 可为空，但字段必须保留 |",
    "| `generator_name` | yes | 生成器名称 |",
    "| `generator_version` | yes | 生成器版本 |",
    "| `notes` | no | 备注，可记录规则来源或 `needs_review` |",
    "",
    "## 3. 字段约束",
    "",
    "### span 约束",
    "",
    "- `pred_span_a` 必须原样来自 `turn_a`",
    "- `pred_span_b` 必须原样来自 `turn_b`",
    "- 不允许生成原文中不存在的解释性实体",
    "",
    "### relation_type 合法值",
    "",
    ...VALID_RELATION_TYPES.map((item) => `- \`${item}\``),
    "",
    "### relation_strength 合法值",
    "",
    ...VALID_RELATION_STRENGTH.map((item) => `- \`${item}\``),
    "",
    "### alignment_direction 合法值",
    "",
    ...VALID_ALIGNMENT_DIRECTION.map((item) => `- \`${item}\``),
    "",
    "### core / resonance 标志",
    "",
    "- `pred_is_core_column` 推荐取值：`1` / `0` / `?`",
    "- `pred_supports_resonance` 推荐取值：`1` / `0` / `?`",
    "- 正式可评估输出优先使用 `1` / `0`；若 generator 暂时无法决定，可保留 `?`",
    "",
    "### confidence",
    "",
    "- `pred_confidence` 字段必须保留",
    "- 可以为空",
    "- 也可以使用 `high / medium / low`、0-1 分数或其他一致格式",
    "",
    "## 4. 示例",
    "",
    "```csv",
    "annotation_id,pair_id,pred_column_id,pred_span_a,pred_span_b,pred_relation_type,pred_relation_strength,pred_alignment_direction,pred_is_core_column,pred_supports_resonance,pred_confidence,generator_name,generator_version,notes",
    "F300V1-0001,2700001,P01,你,我,coreference_or_demonstrative,strong,A_to_B,1,1,0.83,rule_baseline,v1,role-shift candidate",
    "```",
    "",
    "## 5. 设计原则",
    "",
    "- prediction schema 是 evaluation 输入，不是 gold",
    "- schema 允许保守输出",
    "- schema 不要求 generator 一次性覆盖所有 relation_type",
    "- schema 不允许拿 pair-level 分数直接冒充 column prediction",
    "",
  ].join("\n");
}

function buildMetricsMd() {
  return [
    "# diagraph evaluation metrics spec v1",
    "",
    "## 1. matching 总则",
    "",
    "- 所有 matching 都应在同一 pair 内进行。",
    "- 使用 one-to-one matching，避免一个 pred 重复命中多个 gold。",
    "- exact 与 relaxed 应各自独立做匹配。",
    "",
    "## 2. A. Column matching metrics",
    "",
    "### exact column precision",
    "```",
    "exact_precision = exact_matched_pred_columns / all_pred_columns",
    "```",
    "",
    "### exact column recall",
    "```",
    "exact_recall = exact_matched_gold_columns / all_gold_columns",
    "```",
    "",
    "### exact column F1",
    "```",
    "exact_f1 = 2 * precision * recall / (precision + recall)",
    "```",
    "",
    "### relaxed column precision / recall / F1",
    "```",
    "relaxed_precision = relaxed_matched_pred_columns / all_pred_columns",
    "relaxed_recall = relaxed_matched_gold_columns / all_gold_columns",
    "relaxed_f1 = 2 * relaxed_precision * relaxed_recall / (relaxed_precision + relaxed_recall)",
    "```",
    "",
    "## 3. B. Relation metrics",
    "",
    "- relation_type accuracy on matched columns",
    "- relation_type macro accuracy / per-type accuracy",
    "- confusion matrix",
    "",
    "建议公式：",
    "",
    "```",
    "relation_type_accuracy = matched_columns_with_correct_type / all_matched_columns",
    "```",
    "",
    "## 4. C. Core column metrics",
    "",
    "```",
    "core_recall = correctly_predicted_gold_core_columns / all_gold_core_columns",
    "core_precision = predicted_core_columns_aligned_to_gold_core / all_predicted_core_columns",
    "missing_core_rate = gold_core_columns_not_recovered_as_core / all_gold_core_columns",
    "false_core_rate = predicted_core_columns_not_supported_by_gold_core / all_predicted_core_columns",
    "```",
    "",
    "## 5. D. Overgeneration / undergeneration",
    "",
    "```",
    "overgeneration_rate = unmatched_pred_columns / all_pred_columns",
    "missing_column_rate = unmatched_gold_columns / all_gold_columns",
    "pair_column_count_error = abs(predicted_column_count - gold_column_count)",
    "aux_overgeneration_rate = unmatched_pred_auxiliary_columns / all_pred_auxiliary_columns",
    "```",
    "",
    "## 6. E. Resonance degree metrics",
    "",
    "建议同时保留 unweighted 与 weighted 两版：",
    "",
    "```",
    "gold_resonance_degree = count(gold columns where supports_resonance = 1)",
    "weighted_gold_degree = 1.0 * gold_core_count + 0.5 * gold_aux_supporting_count",
    "pred_resonance_degree = count(pred columns where pred_supports_resonance = 1)",
    "abs_error = abs(pred_degree - gold_degree)",
    "mae = average(abs_error over pairs)",
    "```",
    "",
    "并按 difficulty / source / dataset_name 进一步分组。",
    "",
    "## 7. F. Pair-level summary",
    "",
    "- per-pair precision / recall / F1",
    "- samples with zero matched columns",
    "- samples with missing core columns",
    "- samples with high overgeneration",
    "",
    "## 8. 推荐呈现顺序",
    "",
    "1. overall exact / relaxed metrics",
    "2. relation_type metrics",
    "3. core-column metrics",
    "4. overgeneration / undergeneration",
    "5. resonance-degree error",
    "6. per-pair worst cases",
    "",
  ].join("\n");
}

function buildRunnerPlanMd(meta) {
  return [
    "# diagraph evaluation runner plan v1",
    "",
    "## 1. 本轮目标",
    "",
    "本轮只设计 runner，不真正执行评估。",
    "",
    "## 2. 输入",
    "",
    "- `diagraph_gold_50_column_gold_v1_active.csv`",
    "- `diagraph_gold_50_pair_list.csv`",
    "- 任意符合 `diagraph_prediction_schema_v1.md` 的 prediction file",
    "",
    "## 3. runner 主流程",
    "",
    "1. 读取 gold_v1 active",
    "2. 读取 prediction file",
    "3. 校验 prediction file header 是否符合 schema",
    "4. 校验 `annotation_id` / `pair_id` 是否存在于 gold 集",
    "5. 校验 `pred_span_a` 是否来自 `turn_a`",
    "6. 校验 `pred_span_b` 是否来自 `turn_b`",
    "7. 校验 relation_type / strength / direction / core 值域",
    "8. 在每个 pair 内做 exact matching",
    "9. 在每个 pair 内做 relaxed matching",
    "10. 计算 overall metrics",
    "11. 输出 per-pair report",
    "12. 输出 unmatched gold / overgenerated pred / confusion analysis",
    "",
    "## 4. exact matching 实现建议",
    "",
    "- 仅在同一 pair 内配对",
    "- exact rule：`pred_span_a == gold.span_a`、`pred_span_b == gold.span_b`、`pred_alignment_direction == gold.alignment_direction`",
    "- 推荐 one-to-one greedy 或 bipartite matching",
    "",
    "## 5. relaxed matching 实现建议",
    "",
    "判断顺序建议：",
    "",
    "1. exact equality",
    "2. containment",
    "3. overlap + shorter-span coverage >= 0.5",
    "",
    "若同一 pred 可匹配多个 gold，优先：",
    "",
    "1. overlap 更高",
    "2. 边界更接近",
    "3. core gold column 优先",
    "",
    "## 6. runner 至少输出",
    "",
    "- exact / relaxed column precision / recall / F1",
    "- relation_type accuracy",
    "- confusion matrix",
    "- core recall / precision",
    "- missing-core / false-core",
    "- overgeneration / undergeneration",
    "- per-pair predicted column count error",
    "- resonance degree error",
    "",
    "## 7. 推荐输出文件",
    "",
    "- `overall_metrics.json`",
    "- `overall_metrics.md`",
    "- `per_pair_metrics.csv`",
    "- `unmatched_gold_columns.csv`",
    "- `overgenerated_prediction_columns.csv`",
    "- `relation_confusion_matrix.csv`",
    "- `missing_core_cases.csv`",
    "- `zero_match_cases.csv`",
    "",
    "## 8. 与当前 gold_v1 的关系",
    "",
    `runner 默认面向当前冻结集：${meta.pair_count} pair / ${meta.active_column_count} active columns。`,
    "",
    "本轮不改 gold_v1，只把它当作固定 benchmark。",
    "",
  ].join("\n");
}

function buildRuleBaselinePlanMd() {
  return [
    "# diagraph rule baseline plan v1",
    "",
    "## 1. 目标",
    "",
    "rule-based baseline 是 evaluation target，不是 gold。第一版应保守、可解释、便于 error analysis。",
    "",
    "## 2. 数据边界",
    "",
    "- 不读取正式数据库",
    "- 只读取 `diagraph_gold_50_pair_list.csv` 的 `turn_a` / `turn_b`",
    "- 尽量复用现有规则逻辑",
    "",
    "## 3. 不强行把 pair-level 规则改造成 column generator",
    "",
    "- 若现有规则只擅长判断 pair-level resonance，可以作为触发器或前置筛选",
    "- 不要把 pair-level 分数直接改写成 column predictions",
    "",
    "## 4. 第一版建议覆盖的 relation_type",
    "",
    "- `lexical_reproduction`",
    "- `coreference_or_demonstrative`",
    "- `slot_filling`",
    "- `contrast`",
    "",
    "## 5. 保守输出原则",
    "",
    "- 不确定时，不要硬标高风险类型",
    "- `relation_type` 先保守",
    "- 不确定时可输出 `pred_confidence = low`，并在 `notes` 里写 `needs_review`",
    "",
    "## 6. 第一版触发思路",
    "",
    "### lexical_reproduction",
    "- 同词或同短语复现",
    "- 位置接近 pair-level evidence span 者优先",
    "",
    "### coreference_or_demonstrative",
    "- 代词 / 指示词跨 turn 回指",
    "- speaker-role / deictic shift 仅在 A/B 跨句条件满足时触发",
    "",
    "### slot_filling",
    "- A 中有问句槽位",
    "- B 中有对位填入值",
    "- 优先覆盖定义问答、行动问答、名词性询问",
    "",
    "### contrast",
    "- 必须有稳定对照轴",
    "- 例如时间、行动主体、处理方式、立场",
    "",
    "## 7. baseline 输出定位",
    "",
    "- baseline 是被评估对象",
    "- baseline 不是 gold",
    "- baseline 不覆盖或回写 gold_v1",
    "",
  ].join("\n");
}

function buildBertRoadmapMd(meta) {
  return [
    "# diagraph bert assisted generation roadmap v1",
    "",
    "## 1. 当前边界",
    "",
    "本轮不训练模型，也不运行 BERT；这里只说明未来 BERT 适合介入哪里。",
    "",
    "## 2. BERT 不直接生成 gold",
    "",
    "- BERT 不直接生成 gold",
    "- gold_v1 是 benchmark，不是模型输出",
    "- 未来模型输出应先落到 prediction schema，再进入 evaluation runner",
    "",
    "## 3. BERT 可介入的位置",
    "",
    "### candidate column reranker",
    "- 对 rule baseline 生成的候选列打分和排序",
    "",
    "### false-positive filter",
    "- 识别更可能是误报的候选列",
    "- 重点帮助控制 overgeneration",
    "",
    "### relation_type assist",
    "- 辅助判断 `semantic_substitution`、`pragmatic_function`、`short_answer`、`coreference_or_demonstrative`、`analogy` 等高混淆类型",
    "",
    "### hidden-column recall supplement",
    "- 补出 rule baseline 难以发现的低表面重合列，再交给 runner 评估",
    "",
    "## 4. 为什么现在不适合直接训练端到端 generator",
    "",
    `当前冻结集规模是 ${meta.pair_count} pair / ${meta.active_column_count} active columns，更适合作为 evaluation set。`,
    "",
    "主要原因：",
    "",
    "1. 数据量仍偏小",
    "2. relation_type 分布不均衡",
    "3. hard case 需要更大规模 gold 才能稳定训练",
    "4. 还没有独立的 column-level train/dev/test split",
    "",
    "## 5. 若以后要训练，需要补什么",
    "",
    "- 扩大 column-level gold",
    "- 建立 column-level train/dev/test split",
    "- 设计 negative predictions / hard negatives",
    "- 明确 generator 输出单位",
    "- 明确 relaxed / exact evaluation 与训练目标的关系",
    "",
    "## 6. 当前推荐路线",
    "",
    "1. 先做 rule-based baseline",
    "2. 实现 evaluation runner",
    "3. 跑 baseline 看 error profile",
    "4. 再决定 BERT 介入 rerank、filter、type-assist 还是 recall supplement",
    "",
  ].join("\n");
}

function buildReadmeMd(meta) {
  return [
    "# diagraph generation evaluation v1",
    "",
    "## 本目录做什么",
    "",
    "本目录用于设计 column-level diagraph generation evaluation framework。",
    "",
    `当前冻结 benchmark：${meta.gold_name}，${meta.pair_count} pair / ${meta.active_column_count} active columns / ${meta.all_rows_count} audit rows。`,
    "",
    "## 和 pair-level BERT shadow experiment 的关系",
    "",
    "- pair-level BERT shadow experiment 关注 resonance detection、shadow model、hybrid 筛选",
    "- 本目录不继续训练 BERT",
    "- 本目录只关注 column-level generation evaluation 如何设计",
    "",
    "## 和 column gold_v1 的关系",
    "",
    "- `diagraph_gold_50_column_gold_v1` 是当前固定 benchmark",
    "- 本目录不修改 gold_v1",
    "- 本目录产出的是评估规范、prediction schema、metrics spec、runner plan 和模板",
    "",
    "## 当前阶段不会做什么",
    "",
    "- 不训练 BERT",
    "- 不运行 BERT",
    "- 不接网站",
    "- 不读写正式数据库",
    "",
    "## 下一步",
    "",
    "下一步才是实现 evaluation runner，并让 rule baseline 或 future generator 产出 prediction file 后接入评估。",
    "",
  ].join("\n");
}

async function buildPredictionTemplateWorkbook(csvPath, xlsxPath) {
  const csvText = (await fs.readFile(csvPath, "utf8")).replace(/^\uFEFF/, "");
  const workbook = await Workbook.fromCSV(csvText, { sheetName: "PredictionTemplate" });
  const sheet = workbook.worksheets.getItem("PredictionTemplate");
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);

  const used = sheet.getUsedRange();
  const values = used.values;
  const rowCount = used.rowCount;
  const colCount = used.columnCount;
  const lastCol = toColumnLabel(colCount - 1);

  const header = sheet.getRange(`A1:${lastCol}1`);
  header.format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "Center",
    verticalAlignment: "Center",
    borders: { preset: "all", style: "thin", color: "#D9E2F3" },
  };

  used.format.wrapText = true;
  used.format.verticalAlignment = "Top";
  used.format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
  used.format.autofitColumns();
  used.format.autofitRows();

  const headers = values[0];
  for (let i = 0; i < headers.length; i += 1) {
    const colRange = sheet.getRangeByIndexes(0, i, Math.max(rowCount, 2), 1);
    if (
      headers[i] === "pred_span_a" ||
      headers[i] === "pred_span_b" ||
      headers[i] === "notes"
    ) {
      colRange.format.columnWidth = 28;
    } else if (
      headers[i] === "annotation_id" ||
      headers[i] === "pair_id" ||
      headers[i] === "pred_column_id"
    ) {
      colRange.format.columnWidth = 14;
    } else {
      colRange.format.columnWidth = Math.min(
        Math.max(colRange.format.columnWidth || 12, 12),
        18,
      );
    }
  }

  sheet.getRange("F2:F500").dataValidation = {
    rule: { type: "list", values: VALID_RELATION_TYPES },
  };
  sheet.getRange("G2:G500").dataValidation = {
    rule: { type: "list", values: VALID_RELATION_STRENGTH },
  };
  sheet.getRange("H2:H500").dataValidation = {
    rule: { type: "list", values: VALID_ALIGNMENT_DIRECTION },
  };
  sheet.getRange("I2:I500").dataValidation = {
    rule: { type: "list", values: VALID_BINARY_OR_UNKNOWN },
  };
  sheet.getRange("J2:J500").dataValidation = {
    rule: { type: "list", values: VALID_BINARY_OR_UNKNOWN },
  };

  await workbook.inspect({
    kind: "table",
    sheetId: "PredictionTemplate",
    range: "A1:N3",
    include: "values",
    tableMaxRows: 3,
    tableMaxCols: 14,
    maxChars: 3000,
  });
  await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 30 },
    summary: "prediction template formula error scan",
    maxChars: 1000,
  });

  const preview = await workbook.render({
    sheetName: "PredictionTemplate",
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await preview.arrayBuffer();

  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(xlsxPath);

  const blob = await FileBlob.load(xlsxPath);
  await SpreadsheetFile.importXlsx(blob);
  await fs.rm(`${xlsxPath}.inspect.ndjson`, { force: true });
}

async function main() {
  await Promise.all(Object.values(INPUTS).map((inputPath) => fs.access(inputPath)));
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await fs.mkdir(TEMPLATE_DIR, { recursive: true });

  const [activeText, allRowsText, metadataText, pairText] = await Promise.all([
    fs.readFile(INPUTS.activeGold, "utf8"),
    fs.readFile(INPUTS.allRowsGold, "utf8"),
    fs.readFile(INPUTS.metadata, "utf8"),
    fs.readFile(INPUTS.pairList, "utf8"),
  ]);

  const activeTable = readCsvTable(activeText);
  const allRowsTable = readCsvTable(allRowsText);
  const pairTable = readCsvTable(pairText);
  const meta = JSON.parse(metadataText);

  if (activeTable.rows.length !== meta.active_column_count) {
    throw new Error(
      `Active count mismatch: csv=${activeTable.rows.length}, metadata=${meta.active_column_count}`,
    );
  }
  if (allRowsTable.rows.length !== meta.all_rows_count) {
    throw new Error(
      `All-rows count mismatch: csv=${allRowsTable.rows.length}, metadata=${meta.all_rows_count}`,
    );
  }
  const pairCount = new Set(activeTable.rows.map((row) => row.annotation_id)).size;
  if (pairCount !== meta.pair_count) {
    throw new Error(`Pair count mismatch: active=${pairCount}, metadata=${meta.pair_count}`);
  }
  if (pairTable.rows.length !== meta.pair_count) {
    throw new Error(`Pair list length mismatch: pair_list=${pairTable.rows.length}, metadata=${meta.pair_count}`);
  }

  await fs.writeFile(OUTPUTS.design, buildDesignMd(meta), "utf8");
  await fs.writeFile(OUTPUTS.schema, buildSchemaMd(), "utf8");
  await fs.writeFile(OUTPUTS.metrics, buildMetricsMd(), "utf8");
  await fs.writeFile(OUTPUTS.runnerPlan, buildRunnerPlanMd(meta), "utf8");
  await fs.writeFile(OUTPUTS.ruleBaseline, buildRuleBaselinePlanMd(), "utf8");
  await fs.writeFile(OUTPUTS.bertRoadmap, buildBertRoadmapMd(meta), "utf8");
  await fs.writeFile(OUTPUTS.readme, buildReadmeMd(meta), "utf8");

  await fs.writeFile(
    OUTPUTS.predictionCsv,
    toCsv(PREDICTION_FIELDS, []),
    "utf8",
  );
  await buildPredictionTemplateWorkbook(OUTPUTS.predictionCsv, OUTPUTS.predictionXlsx);

  console.log(`design=${OUTPUTS.design}`);
  console.log(`schema=${OUTPUTS.schema}`);
  console.log(`metrics=${OUTPUTS.metrics}`);
  console.log(`runner_plan=${OUTPUTS.runnerPlan}`);
  console.log(`rule_baseline=${OUTPUTS.ruleBaseline}`);
  console.log(`bert_roadmap=${OUTPUTS.bertRoadmap}`);
  console.log(`readme=${OUTPUTS.readme}`);
  console.log(`prediction_csv=${OUTPUTS.predictionCsv}`);
  console.log(`prediction_xlsx=${OUTPUTS.predictionXlsx}`);
  console.log(`pair_count=${pairCount}`);
  console.log(`active_count=${activeTable.rows.length}`);
  console.log(`all_rows_count=${allRowsTable.rows.length}`);
  process.exit(0);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
