import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const baseDir = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_gold_50",
  "full_gold_candidate",
);

const jobs = [
  {
    csvPath: path.join(baseDir, "full_diagraph_gold_50_column_reviewed_all_rows.csv"),
    xlsxPath: path.join(baseDir, "full_diagraph_gold_50_column_reviewed_all_rows.xlsx"),
    sheetName: "AllRows",
    wideHeaders: new Set([
      "span_a",
      "span_b",
      "notes",
      "review_reason",
      "reviewer_note",
    ]),
    highlightByDecision: true,
  },
  {
    csvPath: path.join(baseDir, "full_diagraph_gold_50_column_gold_candidate_active.csv"),
    xlsxPath: path.join(baseDir, "full_diagraph_gold_50_column_gold_candidate_active.xlsx"),
    sheetName: "ActiveCandidate",
    wideHeaders: new Set(["span_a", "span_b", "notes", "reviewer_note"]),
    highlightByDecision: true,
  },
];

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
      if (ch === "\"") {
        if (text[i + 1] === "\"") {
          cell += "\"";
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        cell += ch;
      }
    } else if (ch === "\"") {
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
  return { header, body: body.filter((items) => items.some((item) => item !== "")) };
}

async function buildWorkbook(job) {
  const csvText = await fs.readFile(job.csvPath, "utf8");
  const workbook = await Workbook.fromCSV(csvText, { sheetName: job.sheetName });
  const sheet = workbook.worksheets.getItem(job.sheetName);
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

  if (job.highlightByDecision) {
    const decisionIndex = headers.indexOf("reviewer_decision");
    if (decisionIndex >= 0) {
      for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
        const decision = values[rowIndex][decisionIndex];
        if (decision === "delete") {
          sheet.getRange(`A${rowIndex + 1}:${lastCol}${rowIndex + 1}`).format = {
            fill: "#FDE9E7",
            borders: { preset: "all", style: "thin", color: "#D9D9D9" },
            wrapText: true,
            verticalAlignment: "Top",
          };
        } else if (decision === "revise") {
          sheet.getRange(`A${rowIndex + 1}:${lastCol}${rowIndex + 1}`).format = {
            fill: "#FFF2CC",
            borders: { preset: "all", style: "thin", color: "#D9D9D9" },
            wrapText: true,
            verticalAlignment: "Top",
          };
        }
      }
    }
  }

  const preview = await workbook.render({
    sheetName: job.sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await preview.arrayBuffer();

  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(job.xlsxPath);

  const blob = await FileBlob.load(job.xlsxPath);
  await SpreadsheetFile.importXlsx(blob);
  await fs.rm(`${job.xlsxPath}.inspect.ndjson`, { force: true });
}

for (const job of jobs) {
  await buildWorkbook(job);
}
