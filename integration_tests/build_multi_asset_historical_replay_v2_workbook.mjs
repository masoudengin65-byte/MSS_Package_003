import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const inputPath = path.resolve(process.argv[2] ?? "reports/MSS_Multi_Asset_Historical_Replay_v2.json");
const outputPath = path.resolve(process.argv[3] ?? "reports/MSS_Multi_Asset_Historical_Replay_v2.xlsx");
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();
const colors = {navy:"#17365D", blue:"#1F4E78", pale:"#D9EAF7", green:"#E2F0D9", red:"#FCE4D6", border:"#D9E2F3"};

function col(index) { let value=index+1, out=""; while(value){value--;out=String.fromCharCode(65+value%26)+out;value=Math.floor(value/26);} return out; }
function scalar(value) { return value == null ? null : typeof value === "object" ? JSON.stringify(value) : value; }
function flatten(row) {
  const output={};
  for (const [key,value] of Object.entries(row)) {
    if (key === "equity_curve") continue;
    if (value && typeof value === "object" && !Array.isArray(value)) for (const [child,v] of Object.entries(value)) output[`${key}.${child}`]=scalar(v);
    else output[key]=scalar(value);
  }
  return output;
}
function title(sheet, width, text, subtitle) {
  const last=col(width-1); sheet.getRange(`A1:${last}1`).merge(); sheet.getRange("A1").values=[[text]];
  sheet.getRange(`A1:${last}1`).format={fill:colors.navy,font:{bold:true,color:"#FFFFFF",size:15},verticalAlignment:"center"};
  sheet.getRange(`A1:${last}1`).format.rowHeight=28; sheet.getRange(`A2:${last}2`).merge(); sheet.getRange("A2").values=[[subtitle]];
  sheet.getRange(`A2:${last}2`).format={fill:colors.pale,font:{italic:true,color:"#404040"},wrapText:true}; sheet.getRange(`A2:${last}2`).format.rowHeight=30;
}
function tableSheet(name, heading, subtitle, rawRows, selected=null) {
  const rows=rawRows.map(flatten); const headers=selected ?? (rows.length ? Object.keys(rows[0]) : ["status"]); const values=rows.length?rows.map(r=>headers.map(h=>scalar(r[h]))):[["NO_DATA"]];
  const sheet=workbook.worksheets.add(name); title(sheet,headers.length,heading,subtitle);
  sheet.getRangeByIndexes(3,0,1,headers.length).values=[headers]; sheet.getRangeByIndexes(4,0,values.length,headers.length).values=values;
  const last=col(headers.length-1), lastRow=values.length+4; sheet.getRange(`A4:${last}4`).format={fill:colors.blue,font:{bold:true,color:"#FFFFFF"},wrapText:true};
  sheet.getRange(`A4:${last}4`).format.rowHeight=32; sheet.tables.add(`A4:${last}${lastRow}`,true,`${name.replace(/[^A-Za-z0-9]/g,"")}Table`);
  sheet.freezePanes.freezeRows(4); sheet.showGridLines=false;
  headers.forEach((header,index)=>{const letter=col(index),range=sheet.getRange(`${letter}5:${letter}${lastRow}`);
    if(header.includes("percent")||header.includes("rate")) range.format.numberFormat='0.0000"%";[Red](0.0000)"%";-';
    else if(/balance|profit|loss|expectancy|drawdown|risk/.test(header)) range.format.numberFormat='#,##0.00####;[Red](#,##0.00####);-';
    else if(/factor|_r$|r_multiple/.test(header)) range.format.numberFormat='0.000000;[Red](0.000000);-';
    sheet.getRange(`${letter}:${letter}`).format.columnWidth=Math.min(42,Math.max(12,header.length+2)); });
  return {sheet,headers,lastRow};
}
function kvSheet(name, heading, subtitle, object) { return tableSheet(name,heading,subtitle,Object.entries(object).map(([metric,value])=>({metric,value:scalar(value)}))); }

const executive=kvSheet("Executive Summary","Sprint 92A.3 Corrected Multi-Asset Replay v2","Authoritative in-sample research replay; eight independent $10,000 accounts.",{
  schema_version:data.schema_version, acceptance_status:data.acceptance_status, generated_as_of:data.generated_as_of,
  combined_starting_balance:data.combined_independent_results.starting_balance, combined_ending_balance:data.combined_independent_results.ending_balance,
  combined_net_profit:data.combined_independent_results.net_profit, combined_return_percent:data.combined_independent_results.return_percent,
  combined_profit_factor:data.combined_independent_results.profit_factor, closed_trades:data.combined_independent_results.closed_trades,
  profitable_symbols:data.research_conclusions.profitable_symbols, losing_symbols:data.research_conclusions.losing_symbols,
  xauusd_only_profitable:data.research_conclusions.xauusd_only_profitable, real_orders_sent:false, production_change_justified:false,
});
tableSheet("V1 vs V2","Sprint 91 v1 vs Corrected v2","Separates trade selection, corrected monetary valuation, and risk-sizing/rejection effects.",data.v1_vs_v2);
const assets=tableSheet("Asset Performance","Corrected Per-Asset Performance","Canonical and broker symbols remain separate; tick value is reference metadata only.",data.per_symbol_results,[
  "canonical_symbol","broker_symbol","asset_class","account_currency","currency_profit","source_candles","decisions","buy_signals","sell_signals","wait_results","opened_trades","closed_trades","unresolved_trades","rejected_trades","minimum_volume_rejections","starting_balance","ending_balance","return_percent","winners","losers","win_rate_percent","gross_profit","gross_loss","net_profit","profit_factor","expectancy","average_r","median_r","maximum_drawdown","maximum_drawdown_percent","maximum_consecutive_wins","maximum_consecutive_losses","average_holding_minutes"
]);
tableSheet("Asset Class Performance","Independent-Account Asset-Class Aggregates","FOREX, METAL, and CRYPTO aggregates do not share capital.",data.asset_class_results);
tableSheet("Trades","Frozen Corrected Trade Dataset","Entry and exit conversion evidence is preserved per trade.",data.trades,[
  "canonical_symbol","broker_symbol","asset_class","trade_id","timeframe","direction","signal_time","entry_time","entry_price","stop_loss","take_profit","exit_time","exit_price","exit_reason","spread","commission","slippage","volume","profit","r_multiple","status","entry_conversion_factor","entry_conversion_time","entry_conversion_path","exit_conversion_factor","exit_conversion_time","exit_conversion_path","account_currency_stop_risk"
]);
const curves=[]; for(const row of data.per_symbol_results) for(const point of row.equity_curve) curves.push({canonical_symbol:row.canonical_symbol,trade_index:point[0],equity:point[1]});
tableSheet("Equity Curves","Independent Symbol Equity Curves","Each curve starts at $10,000 and is not a shared-capital portfolio curve.",curves);
tableSheet("Risk Audit","Losing-Trade Risk Consistency","Threshold counts and accepted stop risk are calculated against pre-trade equity.",data.risk_audit);
tableSheet("Rejections","Replay Rejection Reasons","Includes explicit minimum-volume and conversion-unavailable rejections.",data.rejections);
tableSheet("Broker Metadata","Broker Metadata Snapshot","Current tick_value is retained only as reference metadata.",data.broker_metadata);
const fx=[]; for(const row of data.historical_fx_conversion){if(row.sample_conversions.length) for(const sample of row.sample_conversions) fx.push({...row,sample_conversions:undefined,...sample}); else fx.push(row);}
tableSheet("Historical FX Conversion","Historical Account-Currency Conversion Audit","Latest completed conversion candle at or before each valuation timestamp; no current-rate fallback.",fx);
kvSheet("Configuration","Frozen Sprint 91 Configuration","No strategy parameter or production behavior was changed.",data.configuration);
tableSheet("Source Windows","Exact Sprint 91 Frozen Source Windows","Saved Sprint 91 timestamps are authoritative; intervals were not filled or expanded.",data.source_windows);
tableSheet("Data Quality","Frozen Source Data Quality","Known market gaps are preserved; no imputation was performed.",data.data_quality);
kvSheet("Diagnostics","Replay Diagnostics","One full strategy replay; frozen-result artifact rebuilds are used for determinism.",data.diagnostics);
kvSheet("Audit","Lineage and Determinism Audit","Protected v1 artifacts are retained and current tick values are reference-only.",{...data.audit,...data.acceptance});

const ap=assets.sheet, end=assets.lastRow; ap.getRange(`X5:X${end}`).conditionalFormats.add("cellIs",{operator:"greaterThan",formula:0,format:{fill:colors.green,font:{color:"#375623"}}});
ap.getRange(`X5:X${end}`).conditionalFormats.add("cellIs",{operator:"lessThan",formula:0,format:{fill:colors.red,font:{color:"#9C0006"}}});
const summaryInspect=await workbook.inspect({kind:"table",range:"Executive Summary!A1:B20",include:"values,formulas",tableMaxRows:20,tableMaxCols:2,maxChars:4000}); console.log(summaryInspect.ndjson);
const errors=await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:200},summary:"v2 formula error scan"}); console.log(errors.ndjson);
const renderDir=process.env.MSS_RENDER_DIR; if(renderDir){await fs.mkdir(renderDir,{recursive:true}); for(const sheet of workbook.worksheets.items){const preview=await workbook.render({sheetName:sheet.name,range:["Trades","Equity Curves"].includes(sheet.name)?"A1:AB24":undefined,autoCrop:["Trades","Equity Curves"].includes(sheet.name)?undefined:"all",scale:1,format:"png"}); await fs.writeFile(path.join(renderDir,`${sheet.name.replace(/[^A-Za-z0-9]+/g,"_")}.png`),new Uint8Array(await preview.arrayBuffer()));}}
await fs.mkdir(path.dirname(outputPath),{recursive:true}); const output=await SpreadsheetFile.exportXlsx(workbook); await output.save(outputPath);
const scriptDir=path.dirname(fileURLToPath(import.meta.url)); execFileSync(process.env.PYTHON_EXECUTABLE??"python",[path.join(scriptDir,"normalize_xlsx_package.py"),outputPath],{stdio:"inherit"});
const finalBlob=await FileBlob.load(outputPath); const finalWorkbook=await SpreadsheetFile.importXlsx(finalBlob);
console.log((await finalWorkbook.inspect({kind:"workbook,sheet,table",maxChars:5000,tableMaxRows:2,tableMaxCols:6})).ndjson);
console.log((await finalWorkbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:200},summary:"normalized v2 formula error scan"})).ndjson);
console.log(`EXPORTED ${outputPath}`);
