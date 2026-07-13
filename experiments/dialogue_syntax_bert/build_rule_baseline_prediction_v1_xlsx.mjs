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
  "rule_baseline_v1",
  "rule_baseline_prediction_v1.csv",
);
const defaultXlsxPath = path.join(
  __dirname,
  "artifacts",
  "formal_300_v1",
  "diagraph_generation_evaluation_v1",
  "rule_baseline_v1",
  "rule_baseline_prediction_v1.xlsx",
);

const inputCsvPath = process.argv[2] ? path.resolve(process.argv[2]) : defaultCsvPath;
const outputXlsxPath = process.argv[3] ? path.resolve(process.argv[3]) : defaultXlsxPath;

const csvText = (await fs.readFile(inputCsvPath, "utf8")).replace(/^\uFEFF/, "");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "RuleBaselinePred" });
const sheet = workbook.worksheets.getItem("RuleBaselinePred");

sheet.freezePanes.freezeRows(1);
sheet.showGridLines = false;

const header = sheet.getRange("A1:N1");
header.format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};

const usedRange = sheet.getUsedRange();
usedRange.format.autofitColumns();
usedRange.format.autofitRows();
usedRange.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };

const preview = await workbook.render({
  sheetName: "RuleBaselinePred",
  range: "A1:N20",
  scale: 1,
  format: "png",
  autoCrop: "all",
});
const previewPath = path.join(os.tmpdir(), "rule_baseline_prediction_v1_preview.png");
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
