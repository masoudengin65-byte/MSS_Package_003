import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const inputPath = path.resolve(
  process.argv[2] ?? "reports/MSS_Multi_Asset_Historical_Replay_v1.json",
);
const outputPath = path.resolve(
  process.argv[3] ?? "reports/MSS_Multi_Asset_Historical_Replay_v1.xlsx",
);
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();
const navy = "#17365D";
const blue = "#1F4E78";
const paleBlue = "#D9EAF7";
const paleGreen = "#E2F0D9";
const paleRed = "#FCE4D6";

function columnName(index) {
  let value = index + 1;
  let output = "";
  while (value > 0) {
    value -= 1;
    output = String.fromCharCode(65 + (value % 26)) + output;
    value = Math.floor(value / 26);
  }
  return output;
}

function scalar(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "object") return JSON.stringify(value);
  return value;
}

function typedValue(key, value) {
  // MT5 candle timestamps are broker-time-naive. Keep the exact ISO evidence
  // string rather than allowing a host timezone conversion to shift the value.
  return scalar(value);
}

function styleTitle(sheet, lastColumn, title, subtitle) {
  const titleRange = `A1:${columnName(lastColumn - 1)}1`;
  sheet.getRange(titleRange).merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(titleRange).format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF", size: 15 },
    verticalAlignment: "center",
  };
  sheet.getRange(titleRange).format.rowHeight = 28;
  const subtitleRange = `A2:${columnName(lastColumn - 1)}2`;
  sheet.getRange(subtitleRange).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(subtitleRange).format = {
    fill: paleBlue,
    font: { italic: true, color: "#404040" },
    wrapText: true,
  };
  sheet.getRange(subtitleRange).format.rowHeight = 30;
}

function applyColumnFormats(sheet, headers, rowCount) {
  headers.forEach((header, index) => {
    const letter = columnName(index);
    const range = sheet.getRange(`${letter}5:${letter}${Math.max(5, rowCount + 4)}`);
    if (header.includes("percent") || header === "win_rate_percent") {
      range.format.numberFormat = '0.00"%";[Red](0.00)"%";-';
    } else if ([
      "gross_profit", "gross_loss", "net_profit", "expectancy",
      "maximum_drawdown", "starting_balance", "ending_balance",
      "entry_price", "stop_loss", "take_profit", "exit_price", "profit",
      "spread", "commission", "slippage", "volume", "point", "spread_price",
    ].includes(header)) {
      range.format.numberFormat = "#,##0.00####;[Red](#,##0.00####);-";
    } else if (header.endsWith("_r") || header === "r_multiple" || header === "profit_factor") {
      range.format.numberFormat = "0.0000;[Red](0.0000);-";
    }
    const maxLength = Math.max(
      header.length,
      ...Array.from({ length: Math.min(rowCount, 100) }, (_, row) => {
        const value = sheet.getCell(row + 4, index).values?.[0]?.[0];
        return String(value ?? "").length;
      }),
    );
    sheet.getRange(`${letter}:${letter}`).format.columnWidth = Math.min(
      42,
      Math.max(11, maxLength + 2),
    );
  });
}

function addTableSheet(name, title, subtitle, rows, selectedHeaders = null) {
  const sheet = workbook.worksheets.add(name);
  const headers = selectedHeaders ?? (rows.length ? Object.keys(rows[0]) : ["status"]);
  const values = rows.length
    ? rows.map((row) => headers.map((key) => typedValue(key, row[key])))
    : [["NO_DATA"]];
  styleTitle(sheet, headers.length, title, subtitle);
  sheet.getRangeByIndexes(3, 0, 1, headers.length).values = [headers];
  sheet.getRangeByIndexes(4, 0, values.length, headers.length).values = values;
  const lastColumn = columnName(headers.length - 1);
  const lastRow = values.length + 4;
  sheet.getRange(`A4:${lastColumn}4`).format = {
    fill: blue,
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getRange(`A4:${lastColumn}4`).format.rowHeight = 30;
  sheet.tables.add(`A4:${lastColumn}${lastRow}`, true, `${name.replace(/[^A-Za-z0-9]/g, "")}Table`);
  sheet.freezePanes.freezeRows(4);
  sheet.showGridLines = false;
  applyColumnFormats(sheet, headers, values.length);
  return { sheet, headers, lastRow };
}

function addKeyValueSheet(name, title, subtitle, value) {
  return addTableSheet(
    name,
    title,
    subtitle,
    Object.entries(value).map(([metric, metricValue]) => ({ metric, value: scalar(metricValue) })),
  );
}

addKeyValueSheet(
  "Summary",
  "Sprint 91 Multi-Asset Historical Replay",
  "Research-only summed independent-symbol performance; this is not a shared-capital portfolio simulation.",
  {
    schema_version: data.schema_version,
    generated_as_of: data.generated_as_of,
    common_candle_count: data.replay_configuration.common_candle_count,
    symbol_count: data.diagnostics.symbol_count,
    closed_trade_count: data.diagnostics.closed_trade_count,
    unresolved_trade_count: data.diagnostics.unresolved_trade_count,
    net_profit: data.combined_independent_results.net_profit,
    profit_factor: data.combined_independent_results.profit_factor,
    win_rate_percent: data.combined_independent_results.win_rate_percent,
    maximum_drawdown: data.combined_independent_results.maximum_drawdown,
    total_return_percent: data.combined_independent_results.total_return_percent,
    true_shared_capital_portfolio: false,
    real_orders_sent: false,
    production_change_justified: false,
  },
);
const perSymbol = addTableSheet(
  "Per Symbol",
  "Per-Symbol Replay Results",
  "Each symbol uses an independent starting balance and the same completed M15 candle count.",
  data.per_symbol_results,
  [
    "canonical_symbol", "broker_symbol", "asset_class", "source_candles",
    "data_start", "data_end", "decisions", "buy_signals", "sell_signals",
    "wait_results", "opened_trades", "closed_trades", "unresolved_trades",
    "rejected_trades", "wins", "losses", "win_rate_percent", "gross_profit",
    "gross_loss", "net_profit", "profit_factor", "expectancy", "average_r",
    "median_r", "maximum_drawdown", "maximum_drawdown_percent",
    "maximum_consecutive_wins", "maximum_consecutive_losses",
    "average_holding_minutes", "starting_balance", "ending_balance",
    "total_return_percent", "context_snapshot_count",
  ],
);
addTableSheet(
  "Asset Classes",
  "Asset-Class Results",
  "FOREX, METAL, and CRYPTO are aggregated as sums of independent symbol balances.",
  data.asset_class_results,
  [
    "scope", "symbols", "symbol_count", "capital_model",
    "true_shared_capital_portfolio", "opened_trades", "closed_trades",
    "unresolved_trades", "wins", "losses", "win_rate_percent",
    "gross_profit", "gross_loss", "net_profit", "profit_factor",
    "expectancy", "average_r", "median_r", "maximum_drawdown",
    "maximum_drawdown_percent", "starting_balance", "ending_balance",
    "total_return_percent",
  ],
);
addKeyValueSheet(
  "Combined View",
  "Combined Independent-Symbol Research View",
  "Simultaneous capital competition and portfolio-level exposure limits were not simulated.",
  data.combined_independent_results,
);
addTableSheet(
  "Trades",
  "Historical Trades",
  "Closed and unresolved trades are retained; unresolved trades are excluded from outcome statistics.",
  data.trades,
  [
    "trade_key", "trade_id", "canonical_symbol", "broker_symbol", "asset_class",
    "timeframe", "direction", "signal_time", "entry_time", "entry_price",
    "stop_loss", "take_profit", "exit_time", "exit_price", "exit_reason",
    "spread", "commission", "slippage", "volume", "profit", "r_multiple",
    "status", "outcome", "legacy_score", "legacy_confidence", "shadow_score",
    "shadow_confidence", "context_snapshot_available", "context_snapshot_sha256",
  ],
);
addTableSheet(
  "Context References",
  "Immutable Decision-Time Context References",
  "Full frozen context payloads are preserved for later Sprint 92 analysis.",
  data.trades.map((row) => ({
    trade_key: row.trade_key,
    canonical_symbol: row.canonical_symbol,
    status: row.status,
    signal_time: row.signal_time,
    entry_time: row.entry_time,
    context_snapshot_available: row.context_snapshot_available,
    context_snapshot_sha256: row.context_snapshot_sha256,
    context_payload_location: `MSS_Multi_Asset_Historical_Replay_v1.json#${row.trade_key}`,
  })),
);
addTableSheet(
  "History Availability",
  "M15 History Availability",
  "The replay uses the same deterministic tail count for every registered symbol.",
  data.history_availability,
);
addTableSheet(
  "Broker Metadata",
  "Broker-Aware Symbol Metadata",
  "Canonical identity is preserved separately from broker symbol and trading conditions.",
  data.broker_metadata,
);
addKeyValueSheet(
  "Configuration",
  "Validated Replay Configuration",
  "Baseline execution assumptions are unchanged; no parameters were optimized.",
  data.replay_configuration,
);
addKeyValueSheet(
  "Diagnostics",
  "Replay Diagnostics",
  "No-lookahead, context-preservation, and trading-operation guardrails.",
  data.diagnostics,
);

const checks = workbook.worksheets.add("Checks");
styleTitle(
  checks,
  6,
  "Audit Checks",
  "Formula-driven reconciliations between per-symbol and combined results.",
);
const psHeaders = perSymbol.headers;
const psLastRow = perSymbol.lastRow;
const psCol = (name) => columnName(psHeaders.indexOf(name));
const combined = data.combined_independent_results;
checks.getRange("A4:F4").values = [["check", "actual", "expected", "difference", "status", "notes"]];
checks.getRange("A5:A9").values = [
  ["Net profit tie-out"],
  ["Closed trades tie-out"],
  ["Opened trades tie-out"],
  ["Common source-candle count"],
  ["Opened equals closed plus unresolved"],
];
checks.getRange("B5:B9").formulas = [
  [`=SUM('Per Symbol'!${psCol("net_profit")}5:${psCol("net_profit")}${psLastRow})`],
  [`=SUM('Per Symbol'!${psCol("closed_trades")}5:${psCol("closed_trades")}${psLastRow})`],
  [`=SUM('Per Symbol'!${psCol("opened_trades")}5:${psCol("opened_trades")}${psLastRow})`],
  [`=MIN('Per Symbol'!${psCol("source_candles")}5:${psCol("source_candles")}${psLastRow})`],
  [`=SUM('Per Symbol'!${psCol("closed_trades")}5:${psCol("closed_trades")}${psLastRow})+SUM('Per Symbol'!${psCol("unresolved_trades")}5:${psCol("unresolved_trades")}${psLastRow})`],
];
checks.getRange("C5:C9").values = [[
  combined.net_profit,
], [
  combined.closed_trades,
], [
  combined.opened_trades,
], [
  data.replay_configuration.common_candle_count,
], [
  combined.opened_trades,
]];
checks.getRange("D5").formulas = [["=B5-C5"]];
checks.getRange("D5:D9").fillDown();
checks.getRange("E5").formulas = [["=IF(ABS(D5)<0.01,\"OK\",\"FAIL\")"]];
checks.getRange("E5:E9").fillDown();
checks.getRange("F5:F9").values = [
  ["Sum of independent-symbol net profits"],
  ["Closed trades across all symbols"],
  ["Opened trades across all symbols"],
  ["Fixed completed M15 candle count"],
  ["No trade silently removed"],
];
checks.getRange("A4:F4").format = { fill: blue, font: { bold: true, color: "#FFFFFF" } };
checks.getRange("A4:F9").format.borders = { preset: "inside", style: "thin", color: "#D9E2F3" };
checks.getRange("B5:D9").format.numberFormat = "#,##0.00####;[Red](#,##0.00####);-";
checks.getRange("E5:E9").conditionalFormats.add("containsText", {
  text: "OK",
  format: { fill: paleGreen, font: { bold: true, color: "#375623" } },
});
checks.getRange("E5:E9").conditionalFormats.add("containsText", {
  text: "FAIL",
  format: { fill: paleRed, font: { bold: true, color: "#9C0006" } },
});
checks.getRange("A:A").format.columnWidth = 34;
checks.getRange("B:E").format.columnWidth = 18;
checks.getRange("F:F").format.columnWidth = 42;
checks.freezePanes.freezeRows(4);
checks.showGridLines = false;
checks.tables.add("A4:F9", true, "ChecksTable");

addKeyValueSheet(
  "Audit",
  "Immutable Replay Audit",
  "Hashes and guardrails provide an inspectable lineage from source candles to replay output.",
  data.audit,
);

const keyInspect = await workbook.inspect({
  kind: "table",
  range: "Per Symbol!A1:AG12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 33,
  maxChars: 5000,
});
console.log(keyInspect.ndjson);
const checkInspect = await workbook.inspect({
  kind: "table",
  range: "Checks!A1:F9",
  include: "values,formulas",
  tableMaxRows: 9,
  tableMaxCols: 6,
  maxChars: 3000,
});
console.log(checkInspect.ndjson);

const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "Sprint 91 workbook formula error scan",
});
console.log(errorScan.ndjson);

const renderDir = process.env.MSS_RENDER_DIR;
if (renderDir) {
  await fs.mkdir(renderDir, { recursive: true });
  for (const sheet of workbook.worksheets.items) {
    const renderRanges = {
      "Trades": "A1:AC24",
      "Context References": "A1:H24",
      "History Availability": "A1:AF13",
    };
    const renderRange = renderRanges[sheet.name];
    const preview = await workbook.render({
      sheetName: sheet.name,
      range: renderRange,
      autoCrop: renderRange ? undefined : "all",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(
      path.join(renderDir, `${sheet.name.replace(/[^A-Za-z0-9]+/g, "_")}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
execFileSync(
  process.env.PYTHON_EXECUTABLE ?? "python",
  [path.join(scriptDirectory, "normalize_xlsx_package.py"), outputPath],
  { stdio: "inherit" },
);
const finalBlob = await FileBlob.load(outputPath);
const finalWorkbook = await SpreadsheetFile.importXlsx(finalBlob);
const finalOverview = await finalWorkbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 3500,
  tableMaxRows: 2,
  tableMaxCols: 6,
  tableMaxCellChars: 60,
});
console.log(finalOverview.ndjson);
const finalErrors = await finalWorkbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "Normalized Sprint 91 workbook formula error scan",
});
console.log(finalErrors.ndjson);
console.log(`EXPORTED ${outputPath}`);
