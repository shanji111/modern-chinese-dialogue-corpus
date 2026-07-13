import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARTIFACT_ROOT = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_gold_50",
);
const REVIEW_DIR = path.join(ARTIFACT_ROOT, "pilot10_review");

const INPUTS = {
  reviewPacketXlsx: path.join(REVIEW_DIR, "pilot10_column_review_packet.xlsx"),
  reviewPacketMd: path.join(REVIEW_DIR, "pilot10_column_review_packet.md"),
  draftV3Csv: path.join(ARTIFACT_ROOT, "diagraph_gold_50_pilot10_column_annotation_draft_v3.csv"),
  draftV3Xlsx: path.join(ARTIFACT_ROOT, "diagraph_gold_50_pilot10_column_annotation_draft_v3.xlsx"),
};

const REVIEWED_FIELDS = [
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
  "reviewer_decision",
  "reviewer_note",
  "reviewed_relation_type",
  "reviewed_relation_strength",
  "reviewed_is_core_column",
  "reviewed_supports_resonance",
];

const DECISION_FIELDS = [
  "annotation_id",
  "pair_id",
  "column_id",
  "span_a",
  "span_b",
  "alignment_direction",
  "original_relation_type",
  "reviewed_relation_type",
  "original_relation_strength",
  "reviewed_relation_strength",
  "original_is_core_column",
  "reviewed_is_core_column",
  "original_supports_resonance",
  "reviewed_supports_resonance",
  "reviewer_decision",
  "reviewer_note",
];

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
const VALID_RELATION_STRENGTHS = new Set(["strong", "medium", "weak"]);
const VALID_TERNARY = new Set(["1", "0", "?"]);

const REVIEW_OVERRIDES = {
  "F300V1-0020/C03": {
    reviewer_decision: "revise",
    reviewer_note:
      "“什么→科学”更像定义问答中的类别填槽，不宜标为 semantic_substitution；该栏辅助说明类别槽位，主链由 C01/C02 支撑。",
    reviewed_relation_type: "slot_filling",
    reviewed_relation_strength: "medium",
    reviewed_is_core_column: "0",
    reviewed_supports_resonance: "1",
  },
  "F300V1-0170/C04": {
    reviewer_decision: "revise",
    reviewer_note:
      "“当然有喽”是对隐含询问的短回应，但主共鸣链由“你/我”“喜欢/喜欢”“喜欢的人/喜欢你”承担，因此降为 weak auxiliary column。",
    reviewed_relation_type: "short_answer",
    reviewed_relation_strength: "weak",
    reviewed_is_core_column: "0",
    reviewed_supports_resonance: "1",
  },
  "F300V1-0196/C04": {
    reviewer_decision: "revise",
    reviewer_note:
      "“世事都是会变的”不是对“还说女生”的直接语义替换，而是解释前后变化的语用性回应。",
    reviewed_relation_type: "pragmatic_function",
    reviewed_relation_strength: "medium",
    reviewed_is_core_column: "0",
    reviewed_supports_resonance: "1",
  },
  "F300V1-0023/C04": {
    reviewer_decision: "revise",
    reviewer_note:
      "C04 是对 C02/C03 的整句扩展，适合作为辅助栏；核心行动槽位已由“到书房”“看看”承担。",
    reviewed_relation_type: "slot_filling",
    reviewed_relation_strength: "medium",
    reviewed_is_core_column: "0",
    reviewed_supports_resonance: "1",
  },
  "F300V1-0211/C01": {
    reviewer_decision: "revise",
    reviewer_note:
      "“这/这样”表层指示关系较泛，真正核心纵栏是 C02 中“让其中一人抛弃朋友→这样”的命题回指。",
    reviewed_relation_type: "coreference_or_demonstrative",
    reviewed_relation_strength: "weak",
    reviewed_is_core_column: "0",
    reviewed_supports_resonance: "1",
  },
  "F300V1-0211/C03": {
    reviewer_decision: "revise",
    reviewer_note:
      "“是这样吗？”不是严格意义上的 short_answer，而是对 A 命题内容的确认请求，宜标为 pragmatic_function。",
    reviewed_relation_type: "pragmatic_function",
    reviewed_relation_strength: "medium",
    reviewed_is_core_column: "1",
    reviewed_supports_resonance: "1",
  },
  "F300V1-0127/C06": {
    reviewer_decision: "keep",
    reviewer_note:
      "该栏保留为非核心辅助链，用于说明“佛母”亲属定位如何被 B 讽刺性延展为“外甥”关系；不承担主链。",
    reviewed_relation_type: "analogy",
    reviewed_relation_strength: "medium",
    reviewed_is_core_column: "0",
    reviewed_supports_resonance: "1",
  },
};

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

function readTableFromCsv(csvText, fields) {
  const { header, rows } = parseCsv(csvText);
  const indices = Object.fromEntries(
    fields.map((field) => {
      const idx = header.indexOf(field);
      if (idx < 0) {
        throw new Error(`Missing CSV column: ${field}`);
      }
      return [field, idx];
    }),
  );
  return rows.map((row) =>
    Object.fromEntries(fields.map((field) => [field, row[indices[field]] ?? ""])),
  );
}

function quoteCsvCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function toCsvText(rows, fields) {
  const lines = [
    fields.map(quoteCsvCell).join(","),
    ...rows.map((row) => fields.map((field) => quoteCsvCell(row[field] ?? "")).join(",")),
  ];
  return `\uFEFF${lines.join("\n")}\n`;
}

function parseTurnsFromReviewPacket(reviewPacketMdText) {
  const result = new Map();
  const sections = reviewPacketMdText.split(/^## /m).slice(1);
  for (const section of sections) {
    const newlineIndex = section.indexOf("\n");
    const heading = newlineIndex >= 0 ? section.slice(0, newlineIndex).trim() : section.trim();
    const body = newlineIndex >= 0 ? section.slice(newlineIndex + 1) : "";
    const headingMatch = heading.match(/^(F300V1-\d{4}) \[[^\]]+\]$/);
    if (!headingMatch) {
      continue;
    }
    const annotationId = headingMatch[1];
    const turnAMatch = body.match(/\*\*Turn A\*\*\n([\s\S]*?)\n\n\*\*Turn B\*\*/);
    const turnBMatch = body.match(/\*\*Turn B\*\*\n([\s\S]*?)\n\n\| column_id /);
    if (!turnAMatch || !turnBMatch) {
      throw new Error(`Unable to parse turns for ${annotationId}`);
    }
    result.set(annotationId, {
      turn_a: turnAMatch[1].trim(),
      turn_b: turnBMatch[1].trim(),
    });
  }
  return result;
}

function normalizeReviewedRow(row) {
  const key = `${row.annotation_id}/${row.column_id}`;
  const override = REVIEW_OVERRIDES[key];
  const reviewedRow = {
    ...row,
    reviewer_decision: override?.reviewer_decision ?? "keep",
    reviewer_note: override?.reviewer_note ?? "",
    reviewed_relation_type: override?.reviewed_relation_type ?? row.relation_type,
    reviewed_relation_strength: override?.reviewed_relation_strength ?? row.relation_strength,
    reviewed_is_core_column: override?.reviewed_is_core_column ?? row.is_core_column,
    reviewed_supports_resonance:
      override?.reviewed_supports_resonance ?? row.supports_resonance,
  };
  return reviewedRow;
}

function buildDecisionRow(reviewedRow) {
  return {
    annotation_id: reviewedRow.annotation_id,
    pair_id: reviewedRow.pair_id,
    column_id: reviewedRow.column_id,
    span_a: reviewedRow.span_a,
    span_b: reviewedRow.span_b,
    alignment_direction: reviewedRow.alignment_direction,
    original_relation_type: reviewedRow.relation_type,
    reviewed_relation_type: reviewedRow.reviewed_relation_type,
    original_relation_strength: reviewedRow.relation_strength,
    reviewed_relation_strength: reviewedRow.reviewed_relation_strength,
    original_is_core_column: reviewedRow.is_core_column,
    reviewed_is_core_column: reviewedRow.reviewed_is_core_column,
    original_supports_resonance: reviewedRow.supports_resonance,
    reviewed_supports_resonance: reviewedRow.reviewed_supports_resonance,
    reviewer_decision: reviewedRow.reviewer_decision,
    reviewer_note: reviewedRow.reviewer_note,
  };
}

function countBy(rows, field) {
  const counter = new Map();
  for (const row of rows) {
    const key = row[field];
    counter.set(key, (counter.get(key) ?? 0) + 1);
  }
  return counter;
}

function buildSummaryMarkdown(reviewedRows, decisionRows) {
  const decisionCounts = countBy(reviewedRows, "reviewer_decision");
  const revisedColumns = decisionRows.filter((row) => row.reviewer_decision === "revise");
  const revisedRelationTypes = revisedColumns
    .filter((row) => row.original_relation_type !== row.reviewed_relation_type)
    .map((row) => `${row.annotation_id}/${row.column_id}: ${row.original_relation_type} -> ${row.reviewed_relation_type}`);
  const demotedCoreColumns = revisedColumns
    .filter((row) => row.original_is_core_column === "1" && row.reviewed_is_core_column === "0")
    .map((row) => `${row.annotation_id}/${row.column_id}`);

  const lines = [
    "# pilot10 column review summary",
    "",
    "## 1. 决策分布",
    "",
    `- keep: ${decisionCounts.get("keep") ?? 0}`,
    `- revise: ${decisionCounts.get("revise") ?? 0}`,
    `- delete: ${decisionCounts.get("delete") ?? 0}`,
    `- unsure: ${decisionCounts.get("unsure") ?? 0}`,
    "",
    "## 2. 哪些 relation_type 被修订",
    "",
  ];

  if (revisedRelationTypes.length) {
    for (const item of revisedRelationTypes) {
      lines.push(`- ${item}`);
    }
  } else {
    lines.push("- 本轮没有发生 relation_type 改写。");
  }

  lines.push(
    "",
    "## 3. 为什么 semantic_substitution 要谨慎",
    "",
    "- `semantic_substitution` 必须指出明确替换位，不能因为两句话谈同一主题就直接成立。",
    "- `F300V1-0020/C03` 从 `semantic_substitution` 改为 `slot_filling`，说明定义问答里的类别槽位更适合按填槽处理。",
    "- `F300V1-0196/C04` 改为 `pragmatic_function`，说明有些回应更像对前文命题变化的解释，而不是直接替换。",
    "",
    "## 4. 为什么 pragmatic_function 需要加入正式 guide",
    "",
    "- `F300V1-0196/C04` 和 `F300V1-0211/C03` 都表明，有一类共鸣不是词汇替换，也不是简答本身，而是对前文命题的解释、确认或响应功能。",
    "- 如果 guide 没有 `pragmatic_function`，这类栏位会被误塞进 `semantic_substitution` 或 `short_answer`，削弱标注一致性。",
    "",
    "## 5. 为什么部分 column 从 core 降为 auxiliary",
    "",
    "- 有些栏位能帮助解释共鸣，但并不承担主链，比如 `F300V1-0020/C03`、`F300V1-0023/C04`、`F300V1-0170/C04`、`F300V1-0211/C01`。",
    "- 这类调整的原则是：删去该栏后，如果主共鸣链仍由其他栏稳定支撑，就应降为 auxiliary。",
  );

  if (demotedCoreColumns.length) {
    lines.push(`- 本轮从 core 降为 auxiliary 的栏位：${demotedCoreColumns.join("、")}。`);
  }

  lines.push(
    "",
    "## 6. F300V1-0127 为什么仍作为 hard case 保留",
    "",
    "- 该样本同时包含命题回指、亲属推理链、类比延展和评价性替换，结构比普通 lexical / slot_filling 样本复杂得多。",
    "- `C06` 继续保留为非核心辅助链，原因不是它无效，而是它负责补充说明亲属结构如何被讽刺性延展，不承担主链。",
    "",
    "## 7. reviewed_v1 的定位",
    "",
    "- `reviewed_v1` 已经吸收 pilot10 人工复核意见，可以作为修订正式 guide 的直接依据。",
    "- 但它暂时仍不等于 full gold：范围仅限 pilot10，且 hard case 的解释规则还需要在 guide 中进一步固定。",
    "",
  );
  return `${lines.join("\n")}\n`;
}

function rowValues(rows, fields) {
  return rows.map((row) => fields.map((field) => row[field] ?? ""));
}

function applyWorkbookStyle(sheet, rowCount, columnWidths, reviseRows = new Set()) {
  const headers = Object.keys(columnWidths);
  const lastColumn = String.fromCharCode("A".charCodeAt(0) + headers.length - 1);
  const dataEndRow = rowCount + 1;

  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}${dataEndRow}`).format = {
    borders: { preset: "all", style: "thin", color: "#D9D9D9" },
    wrapText: true,
    verticalAlignment: "top",
  };
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
    borders: { preset: "all", style: "thin", color: "#1F4E78" },
  };
  for (const [columnLetter, width] of Object.entries(columnWidths)) {
    sheet.getRange(`${columnLetter}1:${columnLetter}${dataEndRow}`).format.columnWidth = width;
  }
  for (const rowNumber of reviseRows) {
    sheet.getRange(`A${rowNumber}:${lastColumn}${rowNumber}`).format = {
      fill: "#FFF2CC",
      borders: { preset: "all", style: "thin", color: "#D9D9D9" },
      wrapText: true,
      verticalAlignment: "top",
    };
  }
  sheet.freezePanes.freezeRows(1);
}

async function buildWorkbook(outputPath, sheetName, fields, rows, widths, previewPath, revisePredicate) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add(sheetName);
  sheet.getRange(`A1:${String.fromCharCode("A".charCodeAt(0) + fields.length - 1)}1`).values = [fields];
  sheet
    .getRange(`A2:${String.fromCharCode("A".charCodeAt(0) + fields.length - 1)}${rows.length + 1}`)
    .values = rowValues(rows, fields);
  const reviseRows = new Set();
  rows.forEach((row, index) => {
    if (revisePredicate(row)) {
      reviseRows.add(index + 2);
    }
  });
  applyWorkbookStyle(sheet, rows.length, widths, reviseRows);

  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(outputPath);
}

function validate(reviewedRows, turnsByAnnotation) {
  const invalidSpanA = [];
  const invalidSpanB = [];
  const invalidRelationType = [];
  const invalidRelationStrength = [];
  const invalidTernary = [];
  const rowCounts = new Map();
  const coreCounts = new Map();

  for (const row of reviewedRows) {
    const turns = turnsByAnnotation.get(row.annotation_id);
    if (!turns) {
      invalidSpanA.push(`${row.annotation_id}/${row.column_id}: missing turn_a`);
      invalidSpanB.push(`${row.annotation_id}/${row.column_id}: missing turn_b`);
      continue;
    }
    if (!turns.turn_a.includes(row.span_a)) {
      invalidSpanA.push(`${row.annotation_id}/${row.column_id}: ${row.span_a}`);
    }
    if (!turns.turn_b.includes(row.span_b)) {
      invalidSpanB.push(`${row.annotation_id}/${row.column_id}: ${row.span_b}`);
    }
    if (!VALID_RELATION_TYPES.has(row.reviewed_relation_type)) {
      invalidRelationType.push(`${row.annotation_id}/${row.column_id}: ${row.reviewed_relation_type}`);
    }
    if (!VALID_RELATION_STRENGTHS.has(row.reviewed_relation_strength)) {
      invalidRelationStrength.push(
        `${row.annotation_id}/${row.column_id}: ${row.reviewed_relation_strength}`,
      );
    }
    if (!VALID_TERNARY.has(row.reviewed_is_core_column)) {
      invalidTernary.push(`${row.annotation_id}/${row.column_id}: reviewed_is_core_column=${row.reviewed_is_core_column}`);
    }
    if (!VALID_TERNARY.has(row.reviewed_supports_resonance)) {
      invalidTernary.push(
        `${row.annotation_id}/${row.column_id}: reviewed_supports_resonance=${row.reviewed_supports_resonance}`,
      );
    }
    rowCounts.set(row.annotation_id, (rowCounts.get(row.annotation_id) ?? 0) + 1);
    if (row.reviewed_is_core_column === "1") {
      coreCounts.set(row.annotation_id, (coreCounts.get(row.annotation_id) ?? 0) + 1);
    }
  }

  const annotationIds = [...rowCounts.keys()].sort();
  const missingCore = annotationIds.filter((annotationId) => (coreCounts.get(annotationId) ?? 0) < 1);
  const nonPilotIds = annotationIds.filter((annotationId) => !turnsByAnnotation.has(annotationId));

  return {
    annotationIds,
    rowCounts,
    invalidSpanA,
    invalidSpanB,
    invalidRelationType,
    invalidRelationStrength,
    invalidTernary,
    missingCore,
    nonPilotIds,
  };
}

async function ensureInputsExist() {
  await Promise.all(
    Object.values(INPUTS).map(async (inputPath) => {
      await fs.access(inputPath);
    }),
  );
}

async function main() {
  await ensureInputsExist();
  await fs.mkdir(REVIEW_DIR, { recursive: true });

  const [reviewPacketMdText, draftV3CsvText] = await Promise.all([
    fs.readFile(INPUTS.reviewPacketMd, "utf8"),
    fs.readFile(INPUTS.draftV3Csv, "utf8"),
  ]);

  const draftRows = readTableFromCsv(draftV3CsvText, [
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
  const turnsByAnnotation = parseTurnsFromReviewPacket(reviewPacketMdText);
  const reviewedRows = draftRows.map(normalizeReviewedRow);
  const decisionRows = reviewedRows.map(buildDecisionRow);
  const validation = validate(reviewedRows, turnsByAnnotation);

  if (reviewedRows.length !== 39) {
    throw new Error(`Expected 39 reviewed rows, found ${reviewedRows.length}`);
  }
  if (validation.annotationIds.length !== 10) {
    throw new Error(`Expected 10 pilot pairs, found ${validation.annotationIds.length}`);
  }
  if (validation.invalidSpanA.length || validation.invalidSpanB.length) {
    throw new Error(
      `Span validation failed: span_a=${validation.invalidSpanA.length}, span_b=${validation.invalidSpanB.length}`,
    );
  }
  if (
    validation.invalidRelationType.length ||
    validation.invalidRelationStrength.length ||
    validation.invalidTernary.length
  ) {
    throw new Error("Reviewed field value-domain validation failed.");
  }
  if (validation.nonPilotIds.length) {
    throw new Error(`Non-pilot annotation ids detected: ${validation.nonPilotIds.join(", ")}`);
  }
  if (validation.missingCore.length) {
    throw new Error(`Pairs missing reviewed core columns: ${validation.missingCore.join(", ")}`);
  }
  if ((validation.rowCounts.get("F300V1-0127") ?? 0) !== 6) {
    throw new Error("F300V1-0127 must remain at 6 rows.");
  }

  const reviewedCsvPath = path.join(REVIEW_DIR, "pilot10_column_annotation_reviewed_v1.csv");
  const reviewedXlsxPath = path.join(REVIEW_DIR, "pilot10_column_annotation_reviewed_v1.xlsx");
  const decisionsCsvPath = path.join(REVIEW_DIR, "pilot10_column_review_decisions.csv");
  const decisionsXlsxPath = path.join(REVIEW_DIR, "pilot10_column_review_decisions.xlsx");
  const summaryMdPath = path.join(REVIEW_DIR, "pilot10_column_review_summary.md");
  const previewDir = path.join(os.tmpdir(), "pilot10_reviewed_v1_previews");

  await fs.mkdir(previewDir, { recursive: true });
  await fs.writeFile(reviewedCsvPath, toCsvText(reviewedRows, REVIEWED_FIELDS), "utf8");
  await fs.writeFile(decisionsCsvPath, toCsvText(decisionRows, DECISION_FIELDS), "utf8");
  await fs.writeFile(summaryMdPath, buildSummaryMarkdown(reviewedRows, decisionRows), "utf8");

  await buildWorkbook(
    reviewedXlsxPath,
    "reviewed_v1",
    REVIEWED_FIELDS,
    reviewedRows,
    {
      A: 16,
      B: 12,
      C: 10,
      D: 18,
      E: 24,
      F: 24,
      G: 16,
      H: 16,
      I: 12,
      J: 14,
      K: 40,
      L: 16,
      M: 34,
      N: 24,
      O: 18,
      P: 16,
      Q: 22,
    },
    path.join(previewDir, "reviewed_v1.png"),
    (row) => row.reviewer_decision === "revise",
  );
  await buildWorkbook(
    decisionsXlsxPath,
    "review_decisions",
    DECISION_FIELDS,
    decisionRows,
    {
      A: 16,
      B: 12,
      C: 10,
      D: 16,
      E: 24,
      F: 16,
      G: 22,
      H: 22,
      I: 18,
      J: 18,
      K: 16,
      L: 16,
      M: 20,
      N: 20,
      O: 16,
      P: 36,
    },
    path.join(previewDir, "review_decisions.png"),
    (row) => row.reviewer_decision === "revise",
  );

  const decisionCounts = countBy(reviewedRows, "reviewer_decision");
  console.log(`reviewed_rows=${reviewedRows.length}`);
  console.log(`pair_count=${validation.annotationIds.length}`);
  console.log(`keep=${decisionCounts.get("keep") ?? 0}`);
  console.log(`revise=${decisionCounts.get("revise") ?? 0}`);
  console.log(`delete=${decisionCounts.get("delete") ?? 0}`);
  console.log(`unsure=${decisionCounts.get("unsure") ?? 0}`);
  console.log(`span_a_invalid=${validation.invalidSpanA.length}`);
  console.log(`span_b_invalid=${validation.invalidSpanB.length}`);
  console.log(`value_domain_invalid=${validation.invalidRelationType.length + validation.invalidRelationStrength.length + validation.invalidTernary.length}`);
  console.log(`preview_dir=${previewDir}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
