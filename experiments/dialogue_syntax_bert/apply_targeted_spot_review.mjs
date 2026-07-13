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
const FULL_DIR = path.join(BASE_DIR, "full_gold_candidate");
const SANITY_DIR = path.join(FULL_DIR, "final_sanity_check");
const SPOT_DIR = path.join(SANITY_DIR, "targeted_spot_review");
const OUTPUT_DIR = path.join(SPOT_DIR, "applied");

const INPUTS = {
  packetMd: path.join(SPOT_DIR, "targeted_spot_review_packet.md"),
  decisionsTemplateCsv: path.join(SPOT_DIR, "targeted_spot_review_decisions_template.csv"),
  activeCsv: path.join(FULL_DIR, "full_diagraph_gold_50_column_gold_candidate_active.csv"),
  allRowsCsv: path.join(FULL_DIR, "full_diagraph_gold_50_column_reviewed_all_rows.csv"),
  mergeValidationMd: path.join(FULL_DIR, "full_diagraph_gold_50_merge_validation_report.md"),
  pairListCsv: path.join(BASE_DIR, "diagraph_gold_50_pair_list.csv"),
  guideV2Md: path.join(BASE_DIR, "diagraph_gold_50_annotation_guide_v2.md"),
};

const OUTPUTS = {
  activeCsv: path.join(
    OUTPUT_DIR,
    "full_diagraph_gold_50_column_gold_candidate_active_spot_reviewed.csv",
  ),
  activeXlsx: path.join(
    OUTPUT_DIR,
    "full_diagraph_gold_50_column_gold_candidate_active_spot_reviewed.xlsx",
  ),
  allRowsCsv: path.join(
    OUTPUT_DIR,
    "full_diagraph_gold_50_column_reviewed_all_rows_spot_reviewed.csv",
  ),
  allRowsXlsx: path.join(
    OUTPUT_DIR,
    "full_diagraph_gold_50_column_reviewed_all_rows_spot_reviewed.xlsx",
  ),
  decisionsCsv: path.join(OUTPUT_DIR, "targeted_spot_review_decisions_applied.csv"),
  decisionsXlsx: path.join(OUTPUT_DIR, "targeted_spot_review_decisions_applied.xlsx"),
  validationMd: path.join(OUTPUT_DIR, "targeted_spot_review_apply_validation_report.md"),
  summaryMd: path.join(OUTPUT_DIR, "targeted_spot_review_apply_summary.md"),
};

const TARGET_IDS = new Set([
  "F300V1-0127",
  "F300V1-0220",
  "F300V1-0287",
  "F300V1-0214",
  "F300V1-0111",
  "F300V1-0254",
]);

const REVISION_RULES = new Map(
  [
    [
      "F300V1-0127/C04",
      {
        spot_review_decision: "revise",
        spot_review_note:
          "大鹏→妖精是评价性重命名，可作为辅助 semantic_substitution 支撑亲属类比链，但不应承担主链；主链由 C02/C03/C05 承担。",
        relation_type: "semantic_substitution",
        relation_strength: "medium",
        is_core_column: "0",
        supports_resonance: "1",
      },
    ],
    [
      "F300V1-0254/C01",
      {
        spot_review_decision: "revise",
        spot_review_note:
          "顾养民→他是必要的指称辅助，但删去后主行动/修正链仍可由 C02/C03 支撑，因此降为 auxiliary。",
        relation_type: "coreference_or_demonstrative",
        relation_strength: "strong",
        is_core_column: "0",
        supports_resonance: "1",
      },
    ],
    [
      "F300V1-0254/C04",
      {
        spot_review_decision: "revise",
        spot_review_note:
          "我→你是说话权转换造成的指称辅助，不应与行动修正主链同等作为 core。",
        relation_type: "coreference_or_demonstrative",
        relation_strength: "strong",
        is_core_column: "0",
        supports_resonance: "1",
      },
    ],
    [
      "F300V1-0254/C05",
      {
        spot_review_decision: "revise",
        spot_review_note:
          "我想捶→由我出面说明行动主体和处理方式转移，可作为辅助 contrast；主链已由 C02 暴力行动改写和 C03 制止修正承担。",
        relation_type: "contrast",
        relation_strength: "medium",
        is_core_column: "0",
        supports_resonance: "1",
      },
    ],
  ],
);

const KEEP_NOTE = "accepted in targeted spot review";

const VALID_RELATION_TYPES = new Set([
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
]);
const VALID_STRENGTHS = new Set(["strong", "medium", "weak"]);
const VALID_DIRECTIONS = new Set(["A_to_B", "B_to_A", "mutual"]);
const VALID_BINARY = new Set(["0", "1"]);

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

function keyOf(row) {
  return `${row.annotation_id}/${row.column_id}`;
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

function ensureExists(pathValue) {
  return fs.access(pathValue);
}

function makeDecisionMap(templateRows) {
  const decisions = new Map();
  for (const row of templateRows) {
    const key = `${row.annotation_id}/${row.column_id}`;
    const revised = REVISION_RULES.get(key);
    if (revised) {
      decisions.set(key, {
        annotation_id: row.annotation_id,
        pair_id: row.pair_id,
        column_id: row.column_id,
        current_relation_type: row.current_relation_type,
        current_relation_strength: row.current_relation_strength,
        current_is_core_column: row.current_is_core_column,
        current_supports_resonance: row.current_supports_resonance,
        spot_review_decision: revised.spot_review_decision,
        applied_relation_type: revised.relation_type,
        applied_relation_strength: revised.relation_strength,
        applied_is_core_column: revised.is_core_column,
        applied_supports_resonance: revised.supports_resonance,
        spot_review_note: revised.spot_review_note,
        spot_review_applied: "1",
        freeze_impact: row.freeze_impact ?? "",
      });
    } else {
      decisions.set(key, {
        annotation_id: row.annotation_id,
        pair_id: row.pair_id,
        column_id: row.column_id,
        current_relation_type: row.current_relation_type,
        current_relation_strength: row.current_relation_strength,
        current_is_core_column: row.current_is_core_column,
        current_supports_resonance: row.current_supports_resonance,
        spot_review_decision: "keep",
        applied_relation_type: row.current_relation_type,
        applied_relation_strength: row.current_relation_strength,
        applied_is_core_column: row.current_is_core_column,
        applied_supports_resonance: row.current_supports_resonance,
        spot_review_note: KEEP_NOTE,
        spot_review_applied: "1",
        freeze_impact: row.freeze_impact ?? "",
      });
    }
  }
  return decisions;
}

function applyToActiveRows(activeRows, decisionMap) {
  return activeRows.map((row) => {
    const decision = decisionMap.get(keyOf(row));
    const next = { ...row };
    if (decision) {
      next.relation_type = decision.applied_relation_type;
      next.relation_strength = decision.applied_relation_strength;
      next.is_core_column = decision.applied_is_core_column;
      next.supports_resonance = decision.applied_supports_resonance;
      next.spot_review_decision = decision.spot_review_decision;
      next.spot_review_note = decision.spot_review_note;
      next.spot_review_applied = "1";
    } else {
      next.spot_review_decision = "";
      next.spot_review_note = "";
      next.spot_review_applied = "0";
    }
    return next;
  });
}

function applyToAllRows(allRows, decisionMap) {
  return allRows.map((row) => {
    const decision = decisionMap.get(keyOf(row));
    const next = { ...row };
    if (decision) {
      next.reviewed_relation_type = decision.applied_relation_type;
      next.reviewed_relation_strength = decision.applied_relation_strength;
      next.reviewed_is_core_column = decision.applied_is_core_column;
      next.reviewed_supports_resonance = decision.applied_supports_resonance;
      next.spot_review_decision = decision.spot_review_decision;
      next.spot_review_note = decision.spot_review_note;
      next.spot_review_applied = "1";
    } else {
      next.spot_review_decision = "";
      next.spot_review_note = "";
      next.spot_review_applied = "0";
    }
    return next;
  });
}

function appendHeader(header, columns) {
  return [...header, ...columns.filter((column) => !header.includes(column))];
}

function groupBy(rows, key) {
  const grouped = new Map();
  for (const row of rows) {
    const groupKey = row[key];
    if (!grouped.has(groupKey)) {
      grouped.set(groupKey, []);
    }
    grouped.get(groupKey).push(row);
  }
  return grouped;
}

function countCore(rows, fieldName = "is_core_column") {
  return rows.reduce((sum, row) => sum + (row[fieldName] === "1" ? 1 : 0), 0);
}

function validateOutputs({
  activeOriginal,
  activeReviewed,
  allRowsOriginal,
  allRowsReviewed,
  pairRows,
  decisionMap,
  inputTimesBefore,
  inputTimesAfter,
}) {
  const pairMap = new Map(pairRows.map((row) => [row.annotation_id, row]));
  const activeByPair = groupBy(activeReviewed, "annotation_id");
  const activeOriginalMap = new Map(activeOriginal.map((row) => [keyOf(row), row]));
  const allRowsOriginalMap = new Map(allRowsOriginal.map((row) => [keyOf(row), row]));
  const allRowsReviewedMap = new Map(allRowsReviewed.map((row) => [keyOf(row), row]));

  const uniquePairCount = activeByPair.size;
  const spanAFailures = [];
  const spanBFailures = [];
  const invalidRelationRows = [];
  const invalidStrengthRows = [];
  const invalidDirectionRows = [];
  const invalidBinaryRows = [];
  const missingActivePairs = [];
  const missingCorePairs = [];
  const changedCoreKeys = [];
  const changedCoreReviewKeys = [];

  for (const row of activeReviewed) {
    const pair = pairMap.get(row.annotation_id);
    const key = keyOf(row);
    if (!pair) {
      spanAFailures.push(`${key} (missing pair metadata)`);
      continue;
    }
    if (!pair.turn_a.includes(row.span_a)) {
      spanAFailures.push(key);
    }
    if (!pair.turn_b.includes(row.span_b)) {
      spanBFailures.push(key);
    }
    if (!VALID_RELATION_TYPES.has(row.relation_type)) {
      invalidRelationRows.push(key);
    }
    if (!VALID_STRENGTHS.has(row.relation_strength)) {
      invalidStrengthRows.push(key);
    }
    if (!VALID_DIRECTIONS.has(row.alignment_direction)) {
      invalidDirectionRows.push(key);
    }
    if (!VALID_BINARY.has(row.is_core_column) || !VALID_BINARY.has(row.supports_resonance)) {
      invalidBinaryRows.push(key);
    }

    const original = activeOriginalMap.get(key);
    if (original && original.is_core_column !== row.is_core_column) {
      changedCoreKeys.push(key);
    }
  }

  for (const pair of pairRows) {
    const rows = activeByPair.get(pair.annotation_id) ?? [];
    if (rows.length < 1) {
      missingActivePairs.push(pair.annotation_id);
    }
    if (countCore(rows) < 1) {
      missingCorePairs.push(pair.annotation_id);
    }
  }

  for (const [key, reviewedRow] of allRowsReviewedMap.entries()) {
    const original = allRowsOriginalMap.get(key);
    if (
      original &&
      original.reviewed_is_core_column !== reviewedRow.reviewed_is_core_column
    ) {
      changedCoreReviewKeys.push(key);
    }
  }

  const decisionCounts = { keep: 0, revise: 0, delete: 0 };
  for (const decision of decisionMap.values()) {
    decisionCounts[decision.spot_review_decision] += 1;
  }

  const activeSpotAppliedCount = activeReviewed.filter(
    (row) => row.spot_review_applied === "1",
  ).length;
  const allRowsSpotAppliedCount = allRowsReviewed.filter(
    (row) => row.spot_review_applied === "1",
  ).length;

  return {
    uniquePairCount,
    activeCount: activeReviewed.length,
    allRowsCount: allRowsReviewed.length,
    decisionCounts,
    activeSpotAppliedCount,
    allRowsSpotAppliedCount,
    changedCoreKeys,
    changedCoreReviewKeys,
    missingActivePairs,
    missingCorePairs,
    spanAFailures,
    spanBFailures,
    invalidRelationRows,
    invalidStrengthRows,
    invalidDirectionRows,
    invalidBinaryRows,
    inputUnchanged:
      JSON.stringify(inputTimesBefore) === JSON.stringify(inputTimesAfter),
  };
}

function buildValidationReport(validation) {
  const lines = [
    "# targeted spot review apply validation report",
    "",
    "## Scope",
    "",
    `- active_spot_reviewed pair coverage: ${validation.uniquePairCount}`,
    `- active_spot_reviewed active column count: ${validation.activeCount}`,
    `- all_rows_spot_reviewed row count: ${validation.allRowsCount}`,
    `- targeted spot-reviewed active columns: ${validation.activeSpotAppliedCount}`,
    `- spot-reviewed rows inside all_rows: ${validation.allRowsSpotAppliedCount}`,
    "",
    "## Decision Counts",
    "",
    `- keep: ${validation.decisionCounts.keep}`,
    `- revise: ${validation.decisionCounts.revise}`,
    `- delete: ${validation.decisionCounts.delete}`,
    "",
    "## Checks",
    "",
    `- active_spot_reviewed covers 50 pairs: ${validation.uniquePairCount === 50 ? "PASS" : "FAIL"}`,
    `- active_spot_reviewed has 135 columns: ${validation.activeCount === 135 ? "PASS" : "FAIL"}`,
    `- all_rows_spot_reviewed has 151 rows: ${validation.allRowsCount === 151 ? "PASS" : "FAIL"}`,
    `- only 4 active columns changed core flag: ${validation.changedCoreKeys.length === 4 ? "PASS" : "FAIL"}`,
    `- only 4 reviewed rows changed reviewed_is_core_column: ${validation.changedCoreReviewKeys.length === 4 ? "PASS" : "FAIL"}`,
    `- no delete applied in spot review: ${validation.decisionCounts.delete === 0 ? "PASS" : "FAIL"}`,
    `- every pair still has at least 1 active column: ${validation.missingActivePairs.length === 0 ? "PASS" : "FAIL"}`,
    `- every pair still has at least 1 active core column: ${validation.missingCorePairs.length === 0 ? "PASS" : "FAIL"}`,
    `- span_a stays in turn_a: ${validation.spanAFailures.length === 0 ? "PASS" : "FAIL"}`,
    `- span_b stays in turn_b: ${validation.spanBFailures.length === 0 ? "PASS" : "FAIL"}`,
    `- relation_type legal: ${validation.invalidRelationRows.length === 0 ? "PASS" : "FAIL"}`,
    `- relation_strength legal: ${validation.invalidStrengthRows.length === 0 ? "PASS" : "FAIL"}`,
    `- alignment_direction legal: ${validation.invalidDirectionRows.length === 0 ? "PASS" : "FAIL"}`,
    `- is_core_column / supports_resonance legal: ${validation.invalidBinaryRows.length === 0 ? "PASS" : "FAIL"}`,
    `- original candidate inputs unchanged: ${validation.inputUnchanged ? "PASS" : "FAIL"}`,
    "",
    "## Changed Core Flags",
    "",
    ...validation.changedCoreKeys.map((key) => `- ${key}`),
    "",
    "## Constraint Audit",
    "",
    "- no candidate_v2 generated",
    "- no original candidate file overwritten",
    "- no BERT training or inference",
    "- no gold_v1 / gold_v1_binary modification",
    "- no train/dev/test split modification",
    "- no formal corpus.db read/write",
    "- no website routing / deployment",
    "",
  ];

  if (validation.missingCorePairs.length > 0) {
    lines.push("## Missing Core Pairs", "");
    lines.push(...validation.missingCorePairs.map((pairId) => `- ${pairId}`), "");
  }
  if (validation.spanAFailures.length > 0) {
    lines.push("## span_a Failures", "");
    lines.push(...validation.spanAFailures.map((key) => `- ${key}`), "");
  }
  if (validation.spanBFailures.length > 0) {
    lines.push("## span_b Failures", "");
    lines.push(...validation.spanBFailures.map((key) => `- ${key}`), "");
  }
  return `${lines.join("\n").trim()}\n`;
}

function buildSummary() {
  const lines = [
    "# targeted spot review apply summary",
    "",
    "## Why no candidate_v2",
    "",
    "- 本轮不是重新生成或重审整表，而是把 final sanity check 之后的 targeted spot review 决策应用到 candidate 的副本中。",
    "- 变更范围严格限于 6 个 targeted 样本中的 20 条 active columns，且只有 4 条发生 core 降格，因此无需另起一份 candidate_v2。",
    "",
    "## Why no deletions",
    "",
    "- targeted spot review 没有发现必须剔除的错误纵栏。",
    "- 现有纵栏仍能提供有用的结构证据，只是部分列此前承担了过多主链权重，因此保留 column、只调整 core / auxiliary 分工更合适。",
    "",
    "## Why only core demotions",
    "",
    "- 本轮 revise 都不涉及 span 边界、relation_type、relation_strength 或 supports_resonance 的推翻。",
    "- 争议点集中在“这条纵栏是否不可缺”，因此只做 is_core_column 从 1 降到 0 的修正。",
    "",
    "## Targeted rationale",
    "",
    "- `F300V1-0127/C04` 降为 auxiliary：`大鹏→妖精` 属于评价性重命名，能支撑亲属类比链，但主链应由 `C02/C03/C05` 承担。",
    "- `F300V1-0254/C01` 降为 auxiliary：`顾养民→他` 是必要的指称辅助，但删去后主行动/修正链仍可由 `C02/C03` 支撑。",
    "- `F300V1-0254/C04` 降为 auxiliary：`我→你` 是说话权转换带来的指称辅助，不应与行动修正主链同级。",
    "- `F300V1-0254/C05` 降为 auxiliary：`我想捶→由我出面` 更适合作为行动主体与处理方式转移的辅助 contrast，而非主链核心。",
    "",
    "## Freeze recommendation",
    "",
    "- 经过 targeted spot review 应用后，candidate 的主要风险点已经从“是否误保留列”转为“core 分配是否均衡”，而本轮正是对该问题的最小修正。",
    "- 建议可以进入 `gold_v1 freeze`。",
    "- freeze 前不再需要额外内容层人工复核；保留一次常规文件级 sanity check 即可，例如核对导出文件名、行数、校验报告和归档说明。",
    "",
  ];
  return `${lines.join("\n").trim()}\n`;
}

async function buildWorkbookFromCsv({
  csvPath,
  xlsxPath,
  sheetName,
  wideHeaders = new Set(),
  highlightBySpotReview = false,
}) {
  const csvText = await fs.readFile(csvPath, "utf8");
  const workbook = await Workbook.fromCSV(csvText, { sheetName });
  const sheet = workbook.worksheets.getItem(sheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);

  const used = sheet.getUsedRange();
  const values = used.values;
  const rowCount = used.rowCount;
  const colCount = used.columnCount;
  const lastCol = toColumnLabel(colCount - 1);

  const headerRange = sheet.getRange(`A1:${lastCol}1`);
  headerRange.format = {
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
    const colRange = sheet.getRangeByIndexes(0, i, rowCount, 1);
    if (wideHeaders.has(headers[i])) {
      colRange.format.columnWidth = 30;
    } else if (
      headers[i] === "annotation_id" ||
      headers[i] === "pair_id" ||
      headers[i] === "column_id"
    ) {
      colRange.format.columnWidth = 14;
    } else {
      colRange.format.columnWidth = Math.min(
        Math.max(colRange.format.columnWidth || 12, 12),
        18,
      );
    }
  }

  if (highlightBySpotReview) {
    const decisionIndex = headers.indexOf("spot_review_decision");
    const appliedIndex = headers.indexOf("spot_review_applied");
    if (decisionIndex >= 0 && appliedIndex >= 0) {
      for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
        const decision = values[rowIndex][decisionIndex];
        const applied = values[rowIndex][appliedIndex];
        if (applied !== "1") {
          continue;
        }
        let fill = "#E2F0D9";
        if (decision === "revise") {
          fill = "#FFF2CC";
        }
        sheet.getRange(`A${rowIndex + 1}:${lastCol}${rowIndex + 1}`).format = {
          fill,
          borders: { preset: "all", style: "thin", color: "#D9D9D9" },
          wrapText: true,
          verticalAlignment: "Top",
        };
      }
    }
  }

  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await preview.arrayBuffer();

  await workbook.inspect({
    kind: "table",
    sheetId: sheetName,
    range: `A1:${lastCol}${Math.min(rowCount, 6)}`,
    include: "values",
    tableMaxRows: Math.min(rowCount, 6),
    tableMaxCols: Math.min(colCount, 10),
    maxChars: 3000,
  });

  await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 50 },
    summary: `${sheetName} formula error scan`,
    maxChars: 1000,
  });

  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(xlsxPath);

  const blob = await FileBlob.load(xlsxPath);
  await SpreadsheetFile.importXlsx(blob);
  await fs.rm(`${xlsxPath}.inspect.ndjson`, { force: true });
}

async function main() {
  await Promise.all(Object.values(INPUTS).map((inputPath) => ensureExists(inputPath)));
  await fs.mkdir(OUTPUT_DIR, { recursive: true });

  const inputTimesBeforeEntries = await Promise.all(
    Object.entries(INPUTS).map(async ([name, inputPath]) => [
      name,
      (await fs.stat(inputPath)).mtimeMs,
    ]),
  );
  const inputTimesBefore = Object.fromEntries(inputTimesBeforeEntries);

  const [
    activeText,
    allRowsText,
    decisionTemplateText,
    pairListText,
  ] = await Promise.all([
    fs.readFile(INPUTS.activeCsv, "utf8"),
    fs.readFile(INPUTS.allRowsCsv, "utf8"),
    fs.readFile(INPUTS.decisionsTemplateCsv, "utf8"),
    fs.readFile(INPUTS.pairListCsv, "utf8"),
  ]);

  const activeTable = readCsvTable(activeText);
  const allRowsTable = readCsvTable(allRowsText);
  const decisionTemplateTable = readCsvTable(decisionTemplateText);
  const pairListTable = readCsvTable(pairListText);

  if (activeTable.rows.length !== 135) {
    throw new Error(`Expected 135 active rows, found ${activeTable.rows.length}`);
  }
  if (allRowsTable.rows.length !== 151) {
    throw new Error(`Expected 151 all_rows rows, found ${allRowsTable.rows.length}`);
  }
  if (decisionTemplateTable.rows.length !== 20) {
    throw new Error(`Expected 20 targeted decision rows, found ${decisionTemplateTable.rows.length}`);
  }
  if (
    decisionTemplateTable.rows.some((row) => !TARGET_IDS.has(row.annotation_id))
  ) {
    throw new Error("Decision template contains non-targeted annotation_id values.");
  }

  const decisionMap = makeDecisionMap(decisionTemplateTable.rows);
  const activeReviewedRows = applyToActiveRows(activeTable.rows, decisionMap);
  const allRowsReviewedRows = applyToAllRows(allRowsTable.rows, decisionMap);

  const extraColumns = ["spot_review_decision", "spot_review_note", "spot_review_applied"];
  const activeHeader = appendHeader(activeTable.header, extraColumns);
  const allRowsHeader = appendHeader(allRowsTable.header, extraColumns);
  const decisionsHeader = [
    "annotation_id",
    "pair_id",
    "column_id",
    "current_relation_type",
    "current_relation_strength",
    "current_is_core_column",
    "current_supports_resonance",
    "spot_review_decision",
    "applied_relation_type",
    "applied_relation_strength",
    "applied_is_core_column",
    "applied_supports_resonance",
    "spot_review_note",
    "spot_review_applied",
    "freeze_impact",
  ];
  const decisionsRows = [...decisionMap.values()];

  await fs.writeFile(OUTPUTS.activeCsv, toCsv(activeHeader, activeReviewedRows), "utf8");
  await fs.writeFile(OUTPUTS.allRowsCsv, toCsv(allRowsHeader, allRowsReviewedRows), "utf8");
  await fs.writeFile(OUTPUTS.decisionsCsv, toCsv(decisionsHeader, decisionsRows), "utf8");

  const inputTimesAfterEntries = await Promise.all(
    Object.entries(INPUTS).map(async ([name, inputPath]) => [
      name,
      (await fs.stat(inputPath)).mtimeMs,
    ]),
  );
  const inputTimesAfter = Object.fromEntries(inputTimesAfterEntries);

  const validation = validateOutputs({
    activeOriginal: activeTable.rows,
    activeReviewed: activeReviewedRows,
    allRowsOriginal: allRowsTable.rows,
    allRowsReviewed: allRowsReviewedRows,
    pairRows: pairListTable.rows,
    decisionMap,
    inputTimesBefore,
    inputTimesAfter,
  });

  await fs.writeFile(OUTPUTS.validationMd, buildValidationReport(validation), "utf8");
  await fs.writeFile(OUTPUTS.summaryMd, buildSummary(), "utf8");

  await buildWorkbookFromCsv({
    csvPath: OUTPUTS.activeCsv,
    xlsxPath: OUTPUTS.activeXlsx,
    sheetName: "ActiveSpotReviewed",
    wideHeaders: new Set(["span_a", "span_b", "notes", "reviewer_note", "spot_review_note"]),
    highlightBySpotReview: true,
  });
  await buildWorkbookFromCsv({
    csvPath: OUTPUTS.allRowsCsv,
    xlsxPath: OUTPUTS.allRowsXlsx,
    sheetName: "AllRowsSpotReviewed",
    wideHeaders: new Set([
      "span_a",
      "span_b",
      "notes",
      "reviewer_note",
      "review_reason",
      "spot_review_note",
    ]),
    highlightBySpotReview: true,
  });
  await buildWorkbookFromCsv({
    csvPath: OUTPUTS.decisionsCsv,
    xlsxPath: OUTPUTS.decisionsXlsx,
    sheetName: "SpotReviewDecisions",
    wideHeaders: new Set(["spot_review_note", "freeze_impact"]),
    highlightBySpotReview: true,
  });

  await Promise.all(
    [OUTPUTS.activeXlsx, OUTPUTS.allRowsXlsx, OUTPUTS.decisionsXlsx].map((xlsxPath) =>
      fs.rm(`${xlsxPath}.inspect.ndjson`, { force: true }),
    ),
  );

  console.log(`active_output=${OUTPUTS.activeCsv}`);
  console.log(`all_rows_output=${OUTPUTS.allRowsCsv}`);
  console.log(`decisions_output=${OUTPUTS.decisionsCsv}`);
  console.log(`validation_report=${OUTPUTS.validationMd}`);
  console.log(`summary_report=${OUTPUTS.summaryMd}`);
  console.log(`spot_review_keep=${validation.decisionCounts.keep}`);
  console.log(`spot_review_revise=${validation.decisionCounts.revise}`);
  console.log(`spot_review_delete=${validation.decisionCounts.delete}`);
  console.log(`active_count=${validation.activeCount}`);
  console.log(`all_rows_count=${validation.allRowsCount}`);
  console.log(`changed_core_flags=${validation.changedCoreKeys.length}`);
  console.log(`input_unchanged=${validation.inputUnchanged}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
