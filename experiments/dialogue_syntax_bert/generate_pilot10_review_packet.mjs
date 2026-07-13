import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARTIFACT_ROOT = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_gold_50",
);
const REVIEW_DIR = path.join(ARTIFACT_ROOT, "pilot10_review");

const REVIEW_DECISIONS = ["keep", "revise", "delete", "unsure"];
const HARD_CASE_IDS = new Set(["F300V1-0211", "F300V1-0127"]);
const COLUMN_FIELDS = [
  "column_id",
  "span_a",
  "span_b",
  "relation_type",
  "relation_strength",
  "alignment_direction",
  "is_core_column",
  "supports_resonance",
  "notes",
];

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
  return { header, rows: dataRows.filter((dataRow) => dataRow.some((value) => value !== "")) };
}

function escapeMarkdown(value) {
  return String(value ?? "")
    .replace(/\|/g, "\\|")
    .replace(/\n/g, "<br>");
}

function quoteCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function ensureFirstHeaderIndex(header, name) {
  const idx = header.indexOf(name);
  if (idx < 0) {
    throw new Error(`Missing CSV column: ${name}`);
  }
  return idx;
}

function readTableFromCsv(csvText, fields) {
  const { header, rows } = parseCsv(csvText);
  const indices = Object.fromEntries(fields.map((field) => [field, ensureFirstHeaderIndex(header, field)]));
  return rows.map((row) =>
    Object.fromEntries(fields.map((field) => [field, row[indices[field]] ?? ""])),
  );
}

function readPilot10List(csvText) {
  const wanted = [
    "annotation_id",
    "pair_id",
    "source",
    "dataset_name",
    "turn_a",
    "turn_b",
    "difficulty_level",
    "priority_rank",
    "expected_column_count",
    "dominant_relation_types",
    "why_this_difficulty",
    "annotation_warning",
    "suggested_first_pass",
  ];
  const rows = readTableFromCsv(csvText, wanted);
  const seen = new Set();
  return rows.filter((row) => {
    if (!row.annotation_id || seen.has(row.annotation_id)) {
      return false;
    }
    seen.add(row.annotation_id);
    return true;
  });
}

function groupBy(items, key) {
  return items.reduce((acc, item) => {
    const groupKey = item[key];
    if (!acc.has(groupKey)) {
      acc.set(groupKey, []);
    }
    acc.get(groupKey).push(item);
    return acc;
  }, new Map());
}

function makePairLabelSummary(pair) {
  return [
    `reproduction=${pair.label_reproduction}`,
    `parallelism=${pair.label_parallelism}`,
    `selective_reuse=${pair.label_selective_reuse}`,
    `repair=${pair.label_repair}`,
    `contrast=${pair.label_contrast}`,
    `analogy_candidate=${pair.label_analogy_candidate}`,
  ].join(" | ");
}

function inferColumnFocus(column) {
  const points = [];
  switch (column.relation_type) {
    case "semantic_substitution":
      points.push("检查是否存在可解释替换，而不只是同题相关。");
      break;
    case "analogy":
      points.push("检查是否能明确说出 A 的关系结构如何转移到 B。");
      break;
    case "slot_filling":
      points.push("检查 B 是否确实填入了 A 打开的槽位。");
      break;
    case "coreference_or_demonstrative":
      points.push("检查指称是否跨越 A/B，而不是同一话轮内部关系。");
      break;
    case "short_answer":
      points.push("检查简答是否足以支撑稳定映射。");
      break;
    case "contrast":
      points.push("检查对照轴是否稳定，如时间、主体或立场。");
      break;
    case "repair":
      points.push("检查是否真在修正前一说法、行动或判断。");
      break;
    default:
      points.push("检查该关系类型是否是当前最贴切的粒度。");
      break;
  }
  if (column.is_core_column === "1") {
    points.push("确认删去此栏后，主共鸣链是否会明显受损。");
  } else {
    points.push("确认此栏只是辅助说明，不应单独承担主链。");
  }
  return points.join(" ");
}

function inferPairFocus(item, columns) {
  const focuses = [];
  const relationTypes = new Set(columns.map((column) => column.relation_type));
  if (item.annotation_warning) {
    focuses.push(item.annotation_warning);
  }
  if (item.difficulty_level === "hard") {
    focuses.push("重点防止把低表面重合的同题相关误判成稳定纵栏映射。");
  }
  if (relationTypes.has("analogy")) {
    focuses.push("类比栏要能说清结构推理链，而不只是语气相近或讽刺延展。");
  }
  if (relationTypes.has("semantic_substitution")) {
    focuses.push("语义替换栏要能指出明确替换位，不要只停留在同题相关。");
  }
  if (relationTypes.has("slot_filling")) {
    focuses.push("填槽栏要回看 A 是否真的打开了待填位置。");
  }
  if (relationTypes.has("coreference_or_demonstrative")) {
    focuses.push("指称栏要再次确认 span 是否跨越 turn_a / turn_b。");
  }
  if (columns.some((column) => column.is_core_column === "0")) {
    focuses.push("非 core 栏需要说明它为什么只是辅助说明。");
  }
  if (item.annotation_id === "F300V1-0127") {
    focuses.length = 0;
    focuses.push("优先检查 C02/C03/C06 的亲属推理链是否完整成立。");
    focuses.push("重点区分 C04/C05 的 semantic_substitution 与普通讽刺性同题相关。");
    focuses.push("确认 C06 作为非 core 辅助栏是否合理，且不会与主链重复。");
  }
  return [...new Set(focuses)].slice(0, 3);
}

function hardCaseTag(item) {
  return item.difficulty_level === "hard" || HARD_CASE_IDS.has(item.annotation_id) ? "hard case" : item.difficulty_level;
}

function buildReviewPacketMarkdown(reviewItems) {
  const lines = [
    "# pilot10 column review packet",
    "",
    "本包用于人工复核 pilot10 v3 column-level 标注，重点确认这些样本是否适合作为后续 guide 的标准示例。",
    "",
  ];

  for (const item of reviewItems) {
    lines.push(`## ${item.annotation_id} [${hardCaseTag(item)}]`);
    lines.push("");
    lines.push(`- pair_id: \`${item.pair_id}\``);
    lines.push(`- source / dataset: ${item.source} / ${item.dataset_name}`);
    lines.push(`- pair-level labels: ${makePairLabelSummary(item.pair)}`);
    lines.push(`- evidence: ${item.pair.evidence_span_a} ||| ${item.pair.evidence_span_b}`);
    lines.push(`- why_this_difficulty: ${item.difficulty_level} | ${item.why_this_difficulty}`);
    lines.push("");
    lines.push("**Turn A**");
    lines.push(item.turn_a);
    lines.push("");
    lines.push("**Turn B**");
    lines.push(item.turn_b);
    lines.push("");
    lines.push("| column_id | span_a | span_b | relation_type | relation_strength | alignment_direction | is_core_column | supports_resonance | notes | review_focus |");
    lines.push("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |");
    for (const column of item.columns) {
      lines.push(
        [
          column.column_id,
          column.span_a,
          column.span_b,
          column.relation_type,
          column.relation_strength,
          column.alignment_direction,
          column.is_core_column,
          column.supports_resonance,
          column.notes,
          inferColumnFocus(column),
        ]
          .map(escapeMarkdown)
          .join(" | ")
          .replace(/^/, "| ")
          .replace(/$/, " |"),
      );
    }
    lines.push("");
    lines.push("**需要人工重点看什么**");
    for (const focus of item.reviewFocus) {
      lines.push(`- ${focus}`);
    }
    lines.push("");
  }

  return `${lines.join("\n")}\n`;
}

function buildChecklistMarkdown() {
  const lines = [
    "# pilot10 column review checklist",
    "",
    "人工复核时，请逐条检查以下问题：",
    "",
    "- `span_a` 是否真的来自 `turn_a`，边界是否精确。",
    "- `span_b` 是否真的来自 `turn_b`，边界是否精确。",
    "- `relation_type` 是否过粗或过细，是否有更贴切的标签。",
    "- `semantic_substitution` 是否只是普通话题相关，而不是可解释替换。",
    "- `analogy` 是否存在清楚的结构推理链。",
    "- `slot_filling` 是否确实填入了 A 打开的槽位。",
    "- `coreference_or_demonstrative` 是否真正跨越 A/B，而不是同一话轮内部指称。",
    "- `short_answer` 是否足以支撑稳定映射，而不是只有表面应答。",
    "- `is_core_column=1` 是否真的不可缺，删去后是否会伤到主共鸣链。",
    "- 是否存在过度标注，尤其是辅助说明被抬成主纵栏的情况。",
    "- 是否漏标了关键纵栏，导致主共鸣链不完整。",
    "- 当样本超过 5 行时，新增行是否有清楚的存在理由。",
    "",
  ];
  return `${lines.join("\n")}\n`;
}

function buildGuideRevisionPlanMarkdown(reviewItems, guideNotesText) {
  const lines = [
    "# pilot10 to guide revision plan",
    "",
    "本计划基于 pilot10 v3 复核包整理，目标是把当前可用但分散的经验规则，整理成正式 guide 的稳定条目。",
    "",
    "## 1. A/B 说话权转换中的“你/我”",
    "",
    "- 正式写清 speaker-role shift / deictic shift 的标注条件。",
    "- 保留原文中的“你/我”，不要改写成解释性实体。",
    "- 明确要求两个 span 必须分别来自 `turn_a` 与 `turn_b`。",
    "",
    "## 2. slot_filling 的类型",
    "",
    "- 明确区分定义问答、行动问答、名词性询问三类常见填槽场景。",
    "- 说明并列填槽值可以拆成多行，但前提是 A 真的打开了待填位置。",
    "",
    "## 3. contrast 的类型",
    "",
    "- 补充时间、行动主体、评价立场三类常见对照轴。",
    "- 强调单纯否定或不同意不自动构成 `contrast`。",
    "",
    "## 4. repair 与普通否定的区别",
    "",
    "- 规定 `repair` 必须体现对前一行动、说法、判断或路线的修正、制止或纠偏。",
    "- 明确“只有否定，没有修复”的情况不能直接标成 `repair`。",
    "",
    "## 5. analogy 的结构推理链要求",
    "",
    "- 要求标注者能口头复述 A 先建立什么关系结构，B 如何把它转移、延展或反讽映射出去。",
    "- 像 `F300V1-0127` 这样的 hard case，要把主链和辅助链分开说明。",
    "",
    "## 6. semantic_substitution 与纯话题相关的区别",
    "",
    "- 补正式例，要求标注者指出明确替换位。",
    "- 说明“都在谈同一件事”不足以支持 `semantic_substitution`。",
    "",
    "## 7. 同一话轮内部指称不能单独作为跨句纵栏",
    "",
    "- 把这条从 revision notes 升格为正式红线规则。",
    "- 明确允许在 `notes` 里解释，但不能单独占一行 A/B column。",
    "",
    "## 8. 超过 5 行时如何处理",
    "",
    "- 规定何种情况下允许扩展到 6 行或更多。",
    "- 要求新增行说明与主链的关系，并区分 `core` 与辅助说明栏。",
    "",
    "## 9. 进入正式 guide 前的复核步骤",
    "",
    "- 先用本轮 review packet 复核 10 个 pilot pair。",
    "- 收敛 hard case 的争议点，特别是 `F300V1-0127` 的 analogy / semantic_substitution / non-core 判断。",
    "- 把通过复核的样本固定为标准示例，再推进剩余 40 条。",
    "",
    "## 10. 当前依据",
    "",
    `- 现有 revision notes 文件长度：${guideNotesText.length} 字符。`,
    `- pilot10 review items：${reviewItems.length} 个 pair，${reviewItems.reduce((sum, item) => sum + item.columns.length, 0)} 条 column annotation。`,
    "",
  ];
  return `${lines.join("\n")}\n`;
}

function sheetRange(sheet, range) {
  return sheet.getRange(range);
}

function setLabelValue(sheet, labelCell, valueRange, label, value) {
  sheetRange(sheet, labelCell).values = [[label]];
  sheetRange(sheet, labelCell).format = {
    fill: "#DDEBF7",
    font: { bold: true, color: "#1F1F1F" },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
    wrapText: true,
  };
  sheetRange(sheet, valueRange).merge();
  sheetRange(sheet, valueRange).values = [[value]];
  sheetRange(sheet, valueRange).format = {
    fill: "#FFFFFF",
    borders: { preset: "all", style: "thin", color: "#D9D9D9" },
    wrapText: true,
    verticalAlignment: "top",
  };
}

function setBasicCell(sheet, range, value, format = {}) {
  sheetRange(sheet, range).values = [[value]];
  sheetRange(sheet, range).format = format;
}

function applyColumnWidths(sheet) {
  const widths = [
    ["A1:A120", 14],
    ["B1:B120", 26],
    ["C1:C120", 26],
    ["D1:D120", 20],
    ["E1:E120", 16],
    ["F1:F120", 18],
    ["G1:G120", 12],
    ["H1:H120", 16],
    ["I1:I120", 34],
    ["J1:J120", 16],
    ["K1:K120", 28],
  ];
  for (const [range, width] of widths) {
    sheetRange(sheet, range).format.columnWidth = width;
  }
}

function setRowHeights(sheet) {
  const heights = [
    ["1:1", 26],
    ["8:10", 54],
    ["12:14", 54],
    ["16:17", 42],
  ];
  for (const [range, height] of heights) {
    sheetRange(sheet, range).format.rowHeight = height;
  }
}

function buildSheet(workbook, item) {
  const sheet = workbook.worksheets.add(item.annotation_id);
  sheet.showGridLines = false;

  applyColumnWidths(sheet);
  setRowHeights(sheet);

  sheetRange(sheet, "A1:K1").merge();
  setBasicCell(sheet, "A1", `Pilot10 Column Review Packet | ${item.annotation_id}`, {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  });

  setBasicCell(sheet, "A2", "annotation_id", {
    fill: "#DDEBF7",
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
  });
  setBasicCell(sheet, "B2", item.annotation_id, { borders: { preset: "all", style: "thin", color: "#D9D9D9" } });
  setBasicCell(sheet, "D2", "pair_id", {
    fill: "#DDEBF7",
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
  });
  setBasicCell(sheet, "E2", item.pair_id, { borders: { preset: "all", style: "thin", color: "#D9D9D9" } });
  setBasicCell(sheet, "G2", "source", {
    fill: "#DDEBF7",
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
  });
  setBasicCell(sheet, "H2", item.source, { borders: { preset: "all", style: "thin", color: "#D9D9D9" } });
  setBasicCell(sheet, "J2", "dataset_name", {
    fill: "#DDEBF7",
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
  });
  setBasicCell(sheet, "K2", item.dataset_name, { borders: { preset: "all", style: "thin", color: "#D9D9D9" } });

  setBasicCell(sheet, "A3", "difficulty_level", {
    fill: "#DDEBF7",
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
  });
  setBasicCell(sheet, "B3", hardCaseTag(item), { borders: { preset: "all", style: "thin", color: "#D9D9D9" } });
  setBasicCell(sheet, "D3", "resonance_present", {
    fill: "#DDEBF7",
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
  });
  setBasicCell(sheet, "E3", item.pair.resonance_present, { borders: { preset: "all", style: "thin", color: "#D9D9D9" } });
  setBasicCell(sheet, "G3", "rule_any_positive", {
    fill: "#DDEBF7",
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: "#B8CCE4" },
  });
  setBasicCell(sheet, "H3", item.pair.rule_any_positive, { borders: { preset: "all", style: "thin", color: "#D9D9D9" } });

  setLabelValue(sheet, "A4", "B4:K4", "pair_level_labels", makePairLabelSummary(item.pair));
  setLabelValue(sheet, "A5", "B5:K5", "evidence_span_a", item.pair.evidence_span_a);
  setLabelValue(sheet, "A6", "B6:K6", "evidence_span_b", item.pair.evidence_span_b);
  setLabelValue(sheet, "A7", "B7:K10", "turn_a", item.turn_a);
  setLabelValue(sheet, "A11", "B11:K14", "turn_b", item.turn_b);
  setLabelValue(sheet, "A15", "B15:K15", "annotator_note", item.pair.annotator_note);
  setLabelValue(sheet, "A16", "B16:K17", "review_focus", item.reviewFocus.join(" "));

  const headerRow = 20;
  const dataStartRow = headerRow + 1;
  const headers = [
    "column_id",
    "span_a",
    "span_b",
    "relation_type",
    "relation_strength",
    "alignment_direction",
    "is_core_column",
    "supports_resonance",
    "notes",
    "reviewer_decision",
    "reviewer_note",
  ];
  sheetRange(sheet, `A${headerRow}:K${headerRow}`).values = [headers];
  sheetRange(sheet, `A${headerRow}:K${headerRow}`).format = {
    fill: "#5B9BD5",
    font: { bold: true, color: "#FFFFFF" },
    borders: { preset: "all", style: "thin", color: "#9CC2E5" },
    wrapText: true,
  };

  const dataRows = item.columns.map((column) => [
    column.column_id,
    column.span_a,
    column.span_b,
    column.relation_type,
    column.relation_strength,
    column.alignment_direction,
    column.is_core_column,
    column.supports_resonance,
    column.notes,
    "",
    "",
  ]);
  const dataEndRow = dataStartRow + dataRows.length - 1;
  sheetRange(sheet, `A${dataStartRow}:K${dataEndRow}`).values = dataRows;
  sheetRange(sheet, `A${dataStartRow}:K${dataEndRow}`).format = {
    borders: { preset: "all", style: "thin", color: "#D9D9D9" },
    wrapText: true,
    verticalAlignment: "top",
  };
  sheetRange(sheet, `J${dataStartRow}:J${dataEndRow}`).dataValidation = {
    rule: { type: "list", values: REVIEW_DECISIONS },
  };
  sheet.freezePanes.freezeRows(headerRow);
}

async function writeReviewWorkbook(reviewItems, outputPath, previewDir) {
  const workbook = Workbook.create();
  for (const item of reviewItems) {
    buildSheet(workbook, item);
  }

  for (const item of reviewItems) {
    const png = await workbook.render({
      sheetName: item.annotation_id,
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    const bytes = new Uint8Array(await png.arrayBuffer());
    await fs.writeFile(path.join(previewDir, `${item.annotation_id}.png`), bytes);
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);

  const fileBlob = await FileBlob.load(outputPath);
  await SpreadsheetFile.importXlsx(fileBlob);
}

async function main() {
  await fs.mkdir(REVIEW_DIR, { recursive: true });
  const previewDir = path.join(os.tmpdir(), "pilot10_review_previews");
  await fs.mkdir(previewDir, { recursive: true });

  const inputs = {
    pairList: path.join(ARTIFACT_ROOT, "diagraph_gold_50_pair_list.csv"),
    pilot10List: path.join(ARTIFACT_ROOT, "diagraph_gold_50_pilot10_list.csv"),
    draftV3: path.join(ARTIFACT_ROOT, "diagraph_gold_50_pilot10_column_annotation_draft_v3.csv"),
    guideNotesV3: path.join(ARTIFACT_ROOT, "diagraph_gold_50_pilot10_guide_revision_notes_v3.md"),
  };

  for (const [name, filePath] of Object.entries(inputs)) {
    try {
      await fs.access(filePath);
    } catch {
      throw new Error(`Missing required input: ${name} -> ${filePath}`);
    }
  }

  const [pairListText, pilot10ListText, draftV3Text, guideNotesText] = await Promise.all([
    fs.readFile(inputs.pairList, "utf8"),
    fs.readFile(inputs.pilot10List, "utf8"),
    fs.readFile(inputs.draftV3, "utf8"),
    fs.readFile(inputs.guideNotesV3, "utf8"),
  ]);

  const pairRows = readTableFromCsv(pairListText, [
    "annotation_id",
    "pair_id",
    "source",
    "dataset_name",
    "sample_stratum",
    "turn_a",
    "turn_b",
    "resonance_present",
    "label_reproduction",
    "label_parallelism",
    "label_selective_reuse",
    "label_repair",
    "label_contrast",
    "label_analogy_candidate",
    "evidence_span_a",
    "evidence_span_b",
    "annotator_note",
    "rule_any_positive",
    "bert_prob",
    "hybrid_pred",
  ]);
  const pilot10Rows = readPilot10List(pilot10ListText);
  const columnRows = readTableFromCsv(draftV3Text, [
    "annotation_id",
    "pair_id",
    "column_id",
    "span_a",
    "span_b",
    "relation_type",
    "relation_strength",
    "alignment_direction",
    "is_core_column",
    "supports_resonance",
    "notes",
  ]);

  const pairMap = new Map(pairRows.map((row) => [row.annotation_id, row]));
  const columnsByAnnotation = groupBy(columnRows, "annotation_id");

  const reviewItems = pilot10Rows.map((row) => {
    const pair = pairMap.get(row.annotation_id);
    const columns = columnsByAnnotation.get(row.annotation_id) ?? [];
    if (!pair) {
      throw new Error(`Pair metadata missing for ${row.annotation_id}`);
    }
    if (!columns.length) {
      throw new Error(`No column annotations found for ${row.annotation_id}`);
    }
    return {
      ...row,
      pair,
      columns,
      reviewFocus: inferPairFocus(row, columns),
    };
  });

  const missingCore = reviewItems
    .filter((item) => !item.columns.some((column) => column.is_core_column === "1"))
    .map((item) => item.annotation_id);

  if (reviewItems.length !== 10) {
    throw new Error(`Expected 10 pilot pairs, found ${reviewItems.length}`);
  }
  if (missingCore.length) {
    throw new Error(`Pairs missing core column: ${missingCore.join(", ")}`);
  }

  const reviewPacketXlsx = path.join(REVIEW_DIR, "pilot10_column_review_packet.xlsx");
  const reviewPacketMd = path.join(REVIEW_DIR, "pilot10_column_review_packet.md");
  const checklistMd = path.join(REVIEW_DIR, "pilot10_column_review_checklist.md");
  const guidePlanMd = path.join(REVIEW_DIR, "pilot10_to_guide_revision_plan.md");
  const inspectSidecar = `${reviewPacketXlsx}.inspect.ndjson`;

  await fs.rm(inspectSidecar, { force: true });

  await writeReviewWorkbook(reviewItems, reviewPacketXlsx, previewDir);
  await fs.writeFile(reviewPacketMd, buildReviewPacketMarkdown(reviewItems), "utf8");
  await fs.writeFile(checklistMd, buildChecklistMarkdown(), "utf8");
  await fs.writeFile(
    guidePlanMd,
    buildGuideRevisionPlanMarkdown(reviewItems, guideNotesText),
    "utf8",
  );
  await fs.rm(inspectSidecar, { force: true });

  const workbookBlob = await FileBlob.load(reviewPacketXlsx);
  await SpreadsheetFile.importXlsx(workbookBlob);

  console.log(`review_items=${reviewItems.length}`);
  console.log(
    `column_total=${reviewItems.reduce((sum, item) => sum + item.columns.length, 0)}`,
  );
  console.log(
    `core_ok=${reviewItems.every((item) => item.columns.some((column) => column.is_core_column === "1"))}`,
  );
  console.log("xlsx_reimport_ok=true");
  console.log(`preview_dir=${previewDir}`);
  console.log(`output_xlsx=${reviewPacketXlsx}`);
  console.log(`output_md=${reviewPacketMd}`);
  process.exitCode = 0;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
