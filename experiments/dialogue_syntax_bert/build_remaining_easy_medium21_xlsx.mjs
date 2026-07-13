import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile, FileBlob } from "@oai/artifact-tool";

const baseDir =
  "D:\\现代汉语对话语料库-BERT实验\\experiments\\dialogue_syntax_bert\\artifacts\\formal_300_v1\\diagraph_gold_50\\remaining_easy_medium21";

const jobs = [
  {
    csvPath: path.join(baseDir, "remaining_easy_medium21_pair_list.csv"),
    xlsxPath: path.join(baseDir, "remaining_easy_medium21_pair_list.xlsx"),
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
    csvPath: path.join(baseDir, "remaining_easy_medium21_column_draft_v1.csv"),
    xlsxPath: path.join(baseDir, "remaining_easy_medium21_column_draft_v1.xlsx"),
    sheetName: "Draft",
    wideHeaders: new Set([
      "span_a",
      "span_b",
      "notes",
      "review_reason",
    ]),
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

async function styleWorkbook(job) {
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
      headers[i] === "column_id" ||
      headers[i] === "pair_id"
    ) {
      colRange.format.columnWidth = 14;
    } else {
      colRange.format.columnWidth = Math.min(Math.max(colRange.format.columnWidth || 12, 12), 18);
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
}

for (const job of jobs) {
  await styleWorkbook(job);
}
