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
  "remaining_hard19",
  "reviewed_v1",
);

const jobs = [
  {
    csvPath: path.join(baseDir, "remaining_hard19_column_reviewed_v1.csv"),
    xlsxPath: path.join(baseDir, "remaining_hard19_column_reviewed_v1.xlsx"),
    sheetName: "ReviewedV1",
    wideHeaders: new Set([
      "span_a",
      "span_b",
      "notes",
      "review_reason",
      "reviewer_note",
    ]),
  },
  {
    csvPath: path.join(baseDir, "remaining_hard19_review_decisions.csv"),
    xlsxPath: path.join(baseDir, "remaining_hard19_review_decisions.xlsx"),
    sheetName: "Decisions",
    wideHeaders: new Set(["reviewer_note"]),
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

  const reviewDecisionIndex = headers.indexOf("reviewer_decision");
  if (reviewDecisionIndex >= 0) {
    const decisionCol = toColumnLabel(reviewDecisionIndex);
    const reviewRange = sheet.getRange(`${decisionCol}2:${decisionCol}${rowCount}`);
    reviewRange.dataValidation = {
      rule: { type: "list", values: ["keep", "revise", "delete"] },
    };
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
