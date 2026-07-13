import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

if (process.argv.length < 4) {
  throw new Error("Usage: node build_csv_to_xlsx_generic.mjs <inputCsvPath> <outputXlsxPath> [sheetName]");
}

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

const inputCsvPath = path.resolve(process.argv[2]);
const outputXlsxPath = path.resolve(process.argv[3]);
const sheetName = (process.argv[4] || "Sheet1").slice(0, 31) || "Sheet1";

const csvText = (await fs.readFile(inputCsvPath, "utf8")).replace(/^\uFEFF/, "");
const workbook = await Workbook.fromCSV(csvText, { sheetName });
const sheet = workbook.worksheets.getItem(sheetName);

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
  sheetName,
  range: previewRange,
  scale: 1,
  format: "png",
  autoCrop: "all",
});
const previewPath = path.join(
  os.tmpdir(),
  `${path.basename(outputXlsxPath, path.extname(outputXlsxPath))}_preview.png`,
);
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(path.dirname(outputXlsxPath), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputXlsxPath);

console.log(
  JSON.stringify(
    {
      inputCsvPath,
      outputXlsxPath,
      sheetName,
      previewPath,
    },
    null,
    2,
  ),
);
