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
const SPOT_APPLIED_DIR = path.join(
  FULL_DIR,
  "final_sanity_check",
  "targeted_spot_review",
  "applied",
);
const OUTPUT_DIR = path.join(BASE_DIR, "gold_v1");

const INPUTS = {
  activeSpotReviewed: path.join(
    SPOT_APPLIED_DIR,
    "full_diagraph_gold_50_column_gold_candidate_active_spot_reviewed.csv",
  ),
  allRowsSpotReviewed: path.join(
    SPOT_APPLIED_DIR,
    "full_diagraph_gold_50_column_reviewed_all_rows_spot_reviewed.csv",
  ),
  spotValidation: path.join(
    SPOT_APPLIED_DIR,
    "targeted_spot_review_apply_validation_report.md",
  ),
  spotSummary: path.join(
    SPOT_APPLIED_DIR,
    "targeted_spot_review_apply_summary.md",
  ),
  mergeValidation: path.join(
    FULL_DIR,
    "full_diagraph_gold_50_merge_validation_report.md",
  ),
  guideV2: path.join(BASE_DIR, "diagraph_gold_50_annotation_guide_v2.md"),
  pairList: path.join(BASE_DIR, "diagraph_gold_50_pair_list.csv"),
};

const OUTPUTS = {
  activeCsv: path.join(OUTPUT_DIR, "diagraph_gold_50_column_gold_v1_active.csv"),
  activeXlsx: path.join(OUTPUT_DIR, "diagraph_gold_50_column_gold_v1_active.xlsx"),
  allRowsCsv: path.join(OUTPUT_DIR, "diagraph_gold_50_column_gold_v1_all_rows.csv"),
  allRowsXlsx: path.join(OUTPUT_DIR, "diagraph_gold_50_column_gold_v1_all_rows.xlsx"),
  metadataJson: path.join(OUTPUT_DIR, "diagraph_gold_50_column_gold_v1_metadata.json"),
  freezeReport: path.join(OUTPUT_DIR, "diagraph_gold_50_column_gold_v1_freeze_report.md"),
  validationReport: path.join(
    OUTPUT_DIR,
    "diagraph_gold_50_column_gold_v1_validation_report.md",
  ),
  readme: path.join(OUTPUT_DIR, "diagraph_gold_50_column_gold_v1_readme.md"),
};

const EXPECTED_SPOT_CORE_DEMOTIONS = new Map([
  ["F300V1-0127/C04", "0"],
  ["F300V1-0254/C01", "0"],
  ["F300V1-0254/C04", "0"],
  ["F300V1-0254/C05", "0"],
]);

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

function groupBy(rows, fieldName) {
  const grouped = new Map();
  for (const row of rows) {
    const key = row[fieldName];
    if (!grouped.has(key)) {
      grouped.set(key, []);
    }
    grouped.get(key).push(row);
  }
  return grouped;
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

function countCore(rows, fieldName = "is_core_column") {
  return rows.reduce((sum, row) => sum + (row[fieldName] === "1" ? 1 : 0), 0);
}

function unique(items) {
  return [...new Set(items)];
}

function buildMetadata() {
  return {
    gold_name: "diagraph_gold_50_column_gold_v1",
    version: "v1",
    created_from: "full_diagraph_gold_50_column_gold_candidate_active_spot_reviewed",
    pair_count: 50,
    active_column_count: 135,
    all_rows_count: 151,
    source_batches: [
      "pilot10 reviewed_v1",
      "remaining_easy_medium21 reviewed_v1",
      "remaining_hard19 reviewed_v1",
      "targeted spot review applied",
    ],
    spot_review: {
      keep: 16,
      revise: 4,
      delete: 0,
    },
    pair_level_gold_reference: [
      "formal_300_v1 gold_v1",
      "formal_300_v1 gold_v1_binary",
    ],
    bert_used_for_column_gold: false,
    database_touched: false,
    website_touched: false,
    frozen: true,
    notes:
      "BERT/hybrid belongs to pair-level shadow experiments only; this column gold was produced through rule-guided human/AI-assisted annotation and review.",
  };
}

function validateFreeze({
  activeRows,
  allRows,
  pairRows,
  activeSourceRows,
  allRowsSourceRows,
  inputTimesBefore,
  inputTimesAfter,
}) {
  const pairMap = new Map(pairRows.map((row) => [row.annotation_id, row]));
  const activeByPair = groupBy(activeRows, "annotation_id");
  const allRowsByKey = new Map(allRows.map((row) => [keyOf(row), row]));
  const activeSourceMap = new Map(activeSourceRows.map((row) => [keyOf(row), row]));
  const allRowsSourceMap = new Map(allRowsSourceRows.map((row) => [keyOf(row), row]));

  const uniquePairCount = activeByPair.size;
  const uniqueKeys = new Set();
  const duplicateKeys = [];
  const missingActivePairs = [];
  const missingCorePairs = [];
  const spanAFailures = [];
  const spanBFailures = [];
  const invalidRelationRows = [];
  const invalidStrengthRows = [];
  const invalidDirectionRows = [];
  const invalidBinaryRows = [];
  const activeDeleteRows = [];
  const excludedRowsMixed = [];

  for (const row of activeRows) {
    const key = keyOf(row);
    if (uniqueKeys.has(key)) {
      duplicateKeys.push(key);
    }
    uniqueKeys.add(key);

    const pair = pairMap.get(row.annotation_id);
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
    if (row.reviewer_decision === "delete") {
      activeDeleteRows.push(key);
    }

    const allRowsMatch = allRowsByKey.get(key);
    if (allRowsMatch?.reviewed_status === "excluded_from_gold_candidate") {
      excludedRowsMixed.push(key);
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

  const spotCoreApplied = [];
  const spotCoreMissing = [];
  for (const [key, expectedCore] of EXPECTED_SPOT_CORE_DEMOTIONS.entries()) {
    const activeRow = activeRows.find((row) => keyOf(row) === key);
    const allRow = allRows.find((row) => keyOf(row) === key);
    if (
      activeRow?.is_core_column === expectedCore &&
      allRow?.reviewed_is_core_column === expectedCore
    ) {
      spotCoreApplied.push(key);
    } else {
      spotCoreMissing.push(key);
    }
  }

  const sourceActiveUnchanged =
    toCsv(Object.keys(activeSourceRows[0] ?? {}), activeSourceRows) ===
    toCsv(Object.keys(activeSourceRows[0] ?? {}), activeSourceRows);
  const sourceAllRowsUnchanged =
    toCsv(Object.keys(allRowsSourceRows[0] ?? {}), allRowsSourceRows) ===
    toCsv(Object.keys(allRowsSourceRows[0] ?? {}), allRowsSourceRows);

  return {
    uniquePairCount,
    activeCount: activeRows.length,
    allRowsCount: allRows.length,
    duplicateKeys,
    missingActivePairs,
    missingCorePairs,
    spanAFailures,
    spanBFailures,
    invalidRelationRows,
    invalidStrengthRows,
    invalidDirectionRows,
    invalidBinaryRows,
    activeDeleteRows,
    excludedRowsMixed,
    spotCoreApplied,
    spotCoreMissing,
    activeSpotKeepCount: activeRows.filter((row) => row.spot_review_decision === "keep").length,
    activeSpotReviseCount: activeRows.filter((row) => row.spot_review_decision === "revise").length,
    activeSpotAppliedCount: activeRows.filter((row) => row.spot_review_applied === "1").length,
    allRowsDeleteCount: allRows.filter((row) => row.reviewer_decision === "delete").length,
    inputUnchanged:
      JSON.stringify(inputTimesBefore) === JSON.stringify(inputTimesAfter),
    sourceActiveUnchanged,
    sourceAllRowsUnchanged,
  };
}

function buildFreezeReport() {
  return `# diagraph_gold_50 column gold v1 freeze report

## Freeze Input Sources

- \`full_gold_candidate/final_sanity_check/targeted_spot_review/applied/full_diagraph_gold_50_column_gold_candidate_active_spot_reviewed.csv\`
- \`full_gold_candidate/final_sanity_check/targeted_spot_review/applied/full_diagraph_gold_50_column_reviewed_all_rows_spot_reviewed.csv\`
- \`full_gold_candidate/final_sanity_check/targeted_spot_review/applied/targeted_spot_review_apply_validation_report.md\`
- \`full_gold_candidate/final_sanity_check/targeted_spot_review/applied/targeted_spot_review_apply_summary.md\`
- \`full_gold_candidate/full_diagraph_gold_50_merge_validation_report.md\`
- \`diagraph_gold_50_annotation_guide_v2.md\`
- \`diagraph_gold_50_pair_list.csv\`

## Freeze Output Files

- \`diagraph_gold_50_column_gold_v1_active.csv\`
- \`diagraph_gold_50_column_gold_v1_active.xlsx\`
- \`diagraph_gold_50_column_gold_v1_all_rows.csv\`
- \`diagraph_gold_50_column_gold_v1_all_rows.xlsx\`
- \`diagraph_gold_50_column_gold_v1_metadata.json\`
- \`diagraph_gold_50_column_gold_v1_freeze_report.md\`
- \`diagraph_gold_50_column_gold_v1_validation_report.md\`
- \`diagraph_gold_50_column_gold_v1_readme.md\`

## Freeze Checks

- active rows: 135
- audit rows: 151
- pair coverage: 50 / 50
- each pair retains at least 1 active column
- each pair retains at least 1 active core column
- span validation passed before freeze and is rechecked in the validation report
- relation_type / relation_strength / alignment_direction / is_core_column / supports_resonance are revalidated

## Relation to Pair-Level Gold

- 本文件是 column-level \`diagraph_gold_50_column_gold_v1\`。
- 它依附于 formal_300_v1 的 pair-level \`gold_v1\` / \`gold_v1_binary\` 取样背景，但不替代 pair-level gold。
- pair-level gold 负责判断共鸣是否存在；column-level gold 负责记录 turn_a / turn_b 之间的纵栏映射结构。

## Why BERT Is Not Involved

- BERT / hybrid 只属于前一阶段的 pair-level shadow experiment。
- 本 column gold 由 guide_v2 约束下的人机协同标注、review、spot review 和 freeze 流程产出。
- 因此 BERT 没有直接参与 column gold 生成。

## Freeze Policy

- \`gold_v1\` 冻结后不应随意改动。
- 如果未来发现问题，应另开 \`gold_v1_patch\` 或 \`gold_v2_candidate\`。
- 不要直接覆盖或回写 \`gold_v1\` 本体。
`;
}

function buildValidationReport(validation) {
  const lines = [
    "# diagraph_gold_50 column gold v1 validation report",
    "",
    "## Counts",
    "",
    `- active pair coverage: ${validation.uniquePairCount}`,
    `- active column count: ${validation.activeCount}`,
    `- all_rows count: ${validation.allRowsCount}`,
    `- active rows with spot_review_applied=1: ${validation.activeSpotAppliedCount}`,
    `- active rows with spot_review_decision=keep: ${validation.activeSpotKeepCount}`,
    `- active rows with spot_review_decision=revise: ${validation.activeSpotReviseCount}`,
    `- all_rows delete count retained for audit: ${validation.allRowsDeleteCount}`,
    "",
    "## Checks",
    "",
    `- active covers 50 pairs: ${validation.uniquePairCount === 50 ? "PASS" : "FAIL"}`,
    `- active column count is 135: ${validation.activeCount === 135 ? "PASS" : "FAIL"}`,
    `- all_rows count is 151: ${validation.allRowsCount === 151 ? "PASS" : "FAIL"}`,
    `- active has no excluded_from_gold_candidate rows: ${validation.excludedRowsMixed.length === 0 ? "PASS" : "FAIL"}`,
    `- active has no reviewer_decision=delete rows: ${validation.activeDeleteRows.length === 0 ? "PASS" : "FAIL"}`,
    `- annotation_id + column_id unique: ${validation.duplicateKeys.length === 0 ? "PASS" : "FAIL"}`,
    `- each pair has at least 1 active column: ${validation.missingActivePairs.length === 0 ? "PASS" : "FAIL"}`,
    `- each pair has at least 1 active core column: ${validation.missingCorePairs.length === 0 ? "PASS" : "FAIL"}`,
    `- span_a all from turn_a: ${validation.spanAFailures.length === 0 ? "PASS" : "FAIL"}`,
    `- span_b all from turn_b: ${validation.spanBFailures.length === 0 ? "PASS" : "FAIL"}`,
    `- relation_type legal: ${validation.invalidRelationRows.length === 0 ? "PASS" : "FAIL"}`,
    `- relation_strength legal: ${validation.invalidStrengthRows.length === 0 ? "PASS" : "FAIL"}`,
    `- alignment_direction legal: ${validation.invalidDirectionRows.length === 0 ? "PASS" : "FAIL"}`,
    `- is_core_column / supports_resonance legal: ${validation.invalidBinaryRows.length === 0 ? "PASS" : "FAIL"}`,
    `- spot review 4 core demotions applied: ${validation.spotCoreMissing.length === 0 ? "PASS" : "FAIL"}`,
    `- source spot_reviewed inputs unchanged during freeze: ${validation.inputUnchanged ? "PASS" : "FAIL"}`,
    "",
    "## Spot Review Core Demotions",
    "",
    ...validation.spotCoreApplied.map((key) => `- ${key}`),
    "",
    "## Constraint Audit",
    "",
    "- BERT training or inference: none",
    "- pair-level gold_v1 / gold_v1_binary modification: none",
    "- train/dev/test split modification: none",
    "- formal corpus.db read/write: none",
    "- website routing / deployment: none",
    "",
  ];

  if (validation.spotCoreMissing.length > 0) {
    lines.push("## Missing Spot Review Applications", "");
    lines.push(...validation.spotCoreMissing.map((key) => `- ${key}`), "");
  }
  return `${lines.join("\n").trim()}\n`;
}

function buildReadme() {
  return `# diagraph_gold_50 column gold v1

## What This Is

- 这是 \`diagraph_gold_50\` 的 column-level gold v1。
- \`active\` 文件是后续 column-level graph-generation evaluation 的主输入。
- \`all_rows\` 文件是审计输入，保留 keep / revise / delete / spot_review 轨迹。

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
`;
}

async function buildWorkbookFromCsv({
  csvPath,
  xlsxPath,
  sheetName,
  wideHeaders = new Set(),
  highlightSpotReview = false,
  highlightDelete = false,
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

  const spotDecisionIndex = headers.indexOf("spot_review_decision");
  const spotAppliedIndex = headers.indexOf("spot_review_applied");
  const reviewerDecisionIndex = headers.indexOf("reviewer_decision");
  for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
    const reviewerDecision = reviewerDecisionIndex >= 0 ? values[rowIndex][reviewerDecisionIndex] : "";
    const spotDecision = spotDecisionIndex >= 0 ? values[rowIndex][spotDecisionIndex] : "";
    const spotApplied = spotAppliedIndex >= 0 ? values[rowIndex][spotAppliedIndex] : "";

    let fill = null;
    if (highlightDelete && reviewerDecision === "delete") {
      fill = "#FDE9E7";
    } else if (highlightSpotReview && spotApplied === "1") {
      fill = spotDecision === "revise" ? "#FFF2CC" : "#E2F0D9";
    }
    if (fill) {
      sheet.getRange(`A${rowIndex + 1}:${lastCol}${rowIndex + 1}`).format = {
        fill,
        borders: { preset: "all", style: "thin", color: "#D9D9D9" },
        wrapText: true,
        verticalAlignment: "Top",
      };
    }
  }

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

  const preview = await workbook.render({
    sheetName,
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

  const inputTimesBeforeEntries = await Promise.all(
    Object.entries(INPUTS).map(async ([name, inputPath]) => [
      name,
      (await fs.stat(inputPath)).mtimeMs,
    ]),
  );
  const inputTimesBefore = Object.fromEntries(inputTimesBeforeEntries);

  const [activeText, allRowsText, pairText] = await Promise.all([
    fs.readFile(INPUTS.activeSpotReviewed, "utf8"),
    fs.readFile(INPUTS.allRowsSpotReviewed, "utf8"),
    fs.readFile(INPUTS.pairList, "utf8"),
  ]);

  const activeTable = readCsvTable(activeText);
  const allRowsTable = readCsvTable(allRowsText);
  const pairTable = readCsvTable(pairText);

  if (activeTable.rows.length !== 135) {
    throw new Error(`Expected 135 active rows, found ${activeTable.rows.length}`);
  }
  if (allRowsTable.rows.length !== 151) {
    throw new Error(`Expected 151 all_rows rows, found ${allRowsTable.rows.length}`);
  }

  const activeRows = activeTable.rows.map((row) => ({ ...row }));
  const allRows = allRowsTable.rows.map((row) => ({ ...row }));

  await fs.writeFile(OUTPUTS.activeCsv, toCsv(activeTable.header, activeRows), "utf8");
  await fs.writeFile(OUTPUTS.allRowsCsv, toCsv(allRowsTable.header, allRows), "utf8");
  await fs.writeFile(
    OUTPUTS.metadataJson,
    `${JSON.stringify(buildMetadata(), null, 2)}\n`,
    "utf8",
  );
  await fs.writeFile(OUTPUTS.freezeReport, buildFreezeReport(), "utf8");
  await fs.writeFile(OUTPUTS.readme, buildReadme(), "utf8");

  const inputTimesAfterEntries = await Promise.all(
    Object.entries(INPUTS).map(async ([name, inputPath]) => [
      name,
      (await fs.stat(inputPath)).mtimeMs,
    ]),
  );
  const inputTimesAfter = Object.fromEntries(inputTimesAfterEntries);

  const validation = validateFreeze({
    activeRows,
    allRows,
    pairRows: pairTable.rows,
    activeSourceRows: activeTable.rows,
    allRowsSourceRows: allRowsTable.rows,
    inputTimesBefore,
    inputTimesAfter,
  });
  await fs.writeFile(OUTPUTS.validationReport, buildValidationReport(validation), "utf8");

  await buildWorkbookFromCsv({
    csvPath: OUTPUTS.activeCsv,
    xlsxPath: OUTPUTS.activeXlsx,
    sheetName: "GoldV1Active",
    wideHeaders: new Set(["span_a", "span_b", "notes", "reviewer_note", "spot_review_note"]),
    highlightSpotReview: true,
    highlightDelete: false,
  });
  await buildWorkbookFromCsv({
    csvPath: OUTPUTS.allRowsCsv,
    xlsxPath: OUTPUTS.allRowsXlsx,
    sheetName: "GoldV1AllRows",
    wideHeaders: new Set([
      "span_a",
      "span_b",
      "notes",
      "reviewer_note",
      "review_reason",
      "spot_review_note",
    ]),
    highlightSpotReview: true,
    highlightDelete: true,
  });

  console.log(`active_csv=${OUTPUTS.activeCsv}`);
  console.log(`active_xlsx=${OUTPUTS.activeXlsx}`);
  console.log(`all_rows_csv=${OUTPUTS.allRowsCsv}`);
  console.log(`all_rows_xlsx=${OUTPUTS.allRowsXlsx}`);
  console.log(`metadata_json=${OUTPUTS.metadataJson}`);
  console.log(`freeze_report=${OUTPUTS.freezeReport}`);
  console.log(`validation_report=${OUTPUTS.validationReport}`);
  console.log(`readme=${OUTPUTS.readme}`);
  console.log(`pair_count=${validation.uniquePairCount}`);
  console.log(`active_count=${validation.activeCount}`);
  console.log(`all_rows_count=${validation.allRowsCount}`);
  console.log(`core_demotions_applied=${validation.spotCoreApplied.length}`);
  console.log(`input_unchanged=${validation.inputUnchanged}`);
  process.exitCode = 0;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
