import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const defaultCsvPath = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_generation_evaluation_v1",
  "bert_candidate_pool_v0",
  "bert_candidate_pool_v0.csv",
);
const defaultXlsxPath = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_generation_evaluation_v1",
  "bert_candidate_pool_v0",
  "bert_candidate_pool_v0.xlsx",
);

function toColumnLabel(index) {
  let n = index;
  let label = "";
  while (n > 0) {
    const remainder = (n - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    n = Math.floor((n - 1) / 26);
  }
  return label;
}

const inputCsvPath = process.argv[2] ? path.resolve(process.argv[2]) : defaultCsvPath;
const outputXlsxPath = process.argv[3] ? path.resolve(process.argv[3]) : defaultXlsxPath;

const csvText = (await fs.readFile(inputCsvPath, "utf8")).replace(/^\uFEFF/, "");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "CandidatePool" });
const sheet = workbook.worksheets.getItem("CandidatePool");

sheet.freezePanes.freezeRows(1);
sheet.showGridLines = false;

const headerCount = csvText.split(/\r?\n/, 1)[0].split(",").length;
const headerRange = `A1:${toColumnLabel(headerCount)}1`;
const usedRange = sheet.getUsedRange();

sheet.getRange(headerRange).format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};
usedRange.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
usedRange.format.autofitColumns();
usedRange.format.autofitRows();

const previewRange = `A1:${toColumnLabel(Math.min(headerCount, 12))}20`;
const preview = await workbook.render({
  sheetName: "CandidatePool",
  range: previewRange,
  scale: 1,
  format: "png",
  autoCrop: "all",
});
const previewPath = path.join(os.tmpdir(), "bert_candidate_pool_v0_preview.png");
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(path.dirname(outputXlsxPath), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputXlsxPath);

console.log(
  JSON.stringify(
    {
      inputCsvPath,
      outputXlsxPath,
      previewPath,
    },
    null,
    2,
  ),
);
