import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const baseDir =
  "D:\\现代汉语对话语料库-BERT实验\\experiments\\dialogue_syntax_bert\\artifacts\\formal_300_v1\\diagraph_gold_50\\remaining_hard19";

const csvJobs = [
  {
    csvPath: path.join(baseDir, "remaining_hard19_pair_list.csv"),
    xlsxPath: path.join(baseDir, "remaining_hard19_pair_list.xlsx"),
    sheetName: "Pairs",
    wideHeaders: new Set([
      "why_this_difficulty",
      "annotation_warning",
      "turn_a",
      "turn_b",
      "annotator_note",
      "evidence_span_a",
      "evidence_span_b",
      "dominant_relation_types",
    ]),
  },
  {
    csvPath: path.join(baseDir, "remaining_hard19_column_draft_v1.csv"),
    xlsxPath: path.join(baseDir, "remaining_hard19_column_draft_v1.xlsx"),
    sheetName: "Draft",
    wideHeaders: new Set([
      "span_a",
      "span_b",
      "notes",
      "review_reason",
    ]),
  },
];

const reviewPacketXlsxPath = path.join(baseDir, "remaining_hard19_review_packet.xlsx");
const pairListCsvPath = path.join(baseDir, "remaining_hard19_pair_list.csv");
const draftCsvPath = path.join(baseDir, "remaining_hard19_column_draft_v1.csv");

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
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n") {
      row.push(cell.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += ch;
    }
  }
  if (cell.length > 0 || row.length > 0) {
    row.push(cell.replace(/\r$/, ""));
    rows.push(row);
  }
  const [header, ...body] = rows;
  if (header?.length) {
    header[0] = header[0].replace(/^\uFEFF/, "");
  }
  return body
    .filter((items) => items.length && items.some((item) => item !== ""))
    .map((items) => Object.fromEntries(header.map((key, idx) => [key, items[idx] ?? ""])));
}

async function styleCsvWorkbook(job) {
  const csvText = await fs.readFile(job.csvPath, "utf8");
  const workbook = await Workbook.fromCSV(csvText, { sheetName: job.sheetName });
  const sheet = workbook.worksheets.getItem(job.sheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);

  const used = sheet.getUsedRange();
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

  const values = used.values;
  const headers = values[0];
  for (let i = 0; i < headers.length; i += 1) {
    const colRange = sheet.getRangeByIndexes(0, i, rowCount, 1);
    if (job.wideHeaders.has(headers[i])) {
      colRange.format.columnWidth = 28;
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

  await workbook.render({
    sheetName: job.sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });

  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(job.xlsxPath);
  const blob = await FileBlob.load(job.xlsxPath);
  await SpreadsheetFile.importXlsx(blob);
  await fs.rm(`${job.xlsxPath}.inspect.ndjson`, { force: true });
}

async function buildReviewPacketWorkbook() {
  const pairRows = parseCsv(await fs.readFile(pairListCsvPath, "utf8"));
  const draftRows = parseCsv(await fs.readFile(draftCsvPath, "utf8"));
  const rowsByPair = new Map();
  for (const row of draftRows) {
    const items = rowsByPair.get(row.annotation_id) || [];
    items.push(row);
    rowsByPair.set(row.annotation_id, items);
  }

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Index");
  summary.showGridLines = false;
  summary.freezePanes.freezeRows(1);
  summary.getRange("A1:F1").values = [[
    "annotation_id",
    "pair_id",
    "difficulty_level",
    "dataset_name",
    "expected_column_count",
    "draft_row_count",
  ]];
  summary.getRange(`A2:F${pairRows.length + 1}`).values = pairRows.map((pair) => [
    pair.annotation_id,
    pair.pair_id,
    pair.difficulty_level,
    pair.dataset_name,
    pair.expected_column_count,
    String((rowsByPair.get(pair.annotation_id) || []).length),
  ]);
  summary.getRange(`A1:F${pairRows.length + 1}`).format.borders = {
    preset: "all",
    style: "thin",
    color: "#D9D9D9",
  };
  summary.getRange("A1:F1").format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "Center",
    verticalAlignment: "Center",
  };
  summary.getUsedRange().format.wrapText = true;
  summary.getUsedRange().format.autofitColumns();
  summary.getUsedRange().format.autofitRows();

  for (const pair of pairRows) {
    const sheet = workbook.worksheets.add(pair.annotation_id);
    sheet.showGridLines = false;

    const metaRows = [
      ["annotation_id", pair.annotation_id],
      ["pair_id", pair.pair_id],
      ["difficulty_level", pair.difficulty_level],
      ["source", pair.source],
      ["dataset_name", pair.dataset_name],
      ["dominant_relation_types", pair.dominant_relation_types],
      ["annotation_warning", pair.annotation_warning],
      ["expected_column_count", pair.expected_column_count],
      ["pair-level labels", `reproduction=${pair.label_reproduction}; parallelism=${pair.label_parallelism}; selective_reuse=${pair.label_selective_reuse}; repair=${pair.label_repair}; contrast=${pair.label_contrast}; analogy_candidate=${pair.label_analogy_candidate}`],
      ["evidence_span_a", pair.evidence_span_a],
      ["evidence_span_b", pair.evidence_span_b],
      ["turn_a", pair.turn_a],
      ["turn_b", pair.turn_b],
    ];
    sheet.getRange(`A1:B${metaRows.length}`).values = metaRows;
    sheet.getRange(`A1:B${metaRows.length}`).format.borders = {
      preset: "all",
      style: "thin",
      color: "#D9D9D9",
    };
    sheet.getRange(`A1:A${metaRows.length}`).format = {
      fill: "#EAF2F8",
      font: { bold: true, color: "#0F172A" },
      verticalAlignment: "Top",
    };
    sheet.getRange(`B1:B${metaRows.length}`).format.wrapText = true;
    sheet.getRange(`B1:B${metaRows.length}`).format.verticalAlignment = "Top";

    const headerRow = metaRows.length + 2;
    const headers = [
      "column_id",
      "span_a",
      "span_b",
      "relation_type",
      "relation_strength",
      "alignment_direction",
      "is_core_column",
      "supports_resonance",
      "draft_confidence",
      "needs_human_review",
      "review_reason",
      "notes",
    ];
    sheet.getRange(`A${headerRow}:L${headerRow}`).values = [headers];
    const pairDraftRows = rowsByPair.get(pair.annotation_id) || [];
    if (pairDraftRows.length) {
      sheet.getRange(`A${headerRow + 1}:L${headerRow + pairDraftRows.length}`).values =
        pairDraftRows.map((row) => [
          row.column_id,
          row.span_a,
          row.span_b,
          row.relation_type,
          row.relation_strength,
          row.alignment_direction,
          row.is_core_column,
          row.supports_resonance,
          row.draft_confidence,
          row.needs_human_review,
          row.review_reason,
          row.notes,
        ]);
    }
    sheet.getRange(`A${headerRow}:L${headerRow}`).format = {
      fill: "#1F4E78",
      font: { bold: true, color: "#FFFFFF" },
      wrapText: true,
      horizontalAlignment: "Center",
      verticalAlignment: "Center",
    };
    if (pairDraftRows.length) {
      sheet.getRange(`A${headerRow}:L${headerRow + pairDraftRows.length}`).format.borders = {
        preset: "all",
        style: "thin",
        color: "#D9D9D9",
      };
      sheet.getRange(`A${headerRow + 1}:L${headerRow + pairDraftRows.length}`).format.wrapText = true;
      sheet.getRange(`A${headerRow + 1}:L${headerRow + pairDraftRows.length}`).format.verticalAlignment = "Top";
    }

    sheet.getRange("A:A").format.columnWidth = 16;
    sheet.getRange("B:C").format.columnWidth = 28;
    sheet.getRange("D:F").format.columnWidth = 16;
    sheet.getRange("G:J").format.columnWidth = 14;
    sheet.getRange("K:L").format.columnWidth = 30;
    sheet.getUsedRange().format.autofitRows();
    sheet.freezePanes.freezeRows(headerRow);
  }

  await workbook.render({
    sheetName: "Index",
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(reviewPacketXlsxPath);
  const blob = await FileBlob.load(reviewPacketXlsxPath);
  await SpreadsheetFile.importXlsx(blob);
  await fs.rm(`${reviewPacketXlsxPath}.inspect.ndjson`, { force: true });
}

for (const job of csvJobs) {
  await styleCsvWorkbook(job);
}
await buildReviewPacketWorkbook();
