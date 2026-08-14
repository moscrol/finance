#!/usr/bin/env node

/**
 * Fupanhui MCP Server
 *
 * Wraps fupanhui.com (复盘会) API endpoints as MCP tools.
 * Uses CDP proxy (localhost:3456) to execute fetch() in the user's Chrome
 * browser context, inheriting the logged-in session automatically.
 *
 * Usage: node index.js
 * Config: add to .mcp.json as stdio server
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { assertTsCode, buildUrl, buildXhrExpr, encodePathSegment } from "./lib.js";

const CDP_HOST = process.env.CDP_HOST || "http://localhost:3456";
const FUPANHUI_BASE = "https://fupanhui.com";

// ─── CDP helpers ───────────────────────────────────────────────

let _targetId = null;
let _targetCheckedAt = 0;
const TARGET_TTL = 5 * 60 * 1000; // re-check target every 5 min

async function getTarget() {
  const now = Date.now();
  if (_targetId && now - _targetCheckedAt < TARGET_TTL) return _targetId;

  // Check existing targets
  const res = await fetch(`${CDP_HOST}/targets`);
  const targets = await res.json();
  if (Array.isArray(targets) && targets.length > 0) {
    // Prefer a fupanhui tab
    const fph = targets.find(t => (t.url || "").includes("fupanhui.com"));
    _targetId = (fph || targets[0]).id || (fph || targets[0]).targetId;
    _targetCheckedAt = now;
    return _targetId;
  }

  // No tab — open one
  const r = await fetch(`${CDP_HOST}/new?url=${encodeURIComponent(FUPANHUI_BASE + "/workspace")}`);
  const d = await r.json();
  _targetId = d.targetId;
  _targetCheckedAt = now;
  return _targetId;
}

async function cdpFetch(apiPath, params = {}) {
  const target = await getTarget();
  const url = buildUrl(apiPath, params);

  // Use synchronous XHR inside browser to get response immediately
  const js = buildXhrExpr(url);

  // CDP proxy /eval does NOT URL-decode the body — send raw expr
  const res = await fetch(`${CDP_HOST}/eval?target=${target}`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `expr=${js}`,
  });

  const result = await res.json();
  if (result.error) throw new Error(`CDP error: ${result.error}`);

  const value = result.value || result.result?.value;
  if (!value) throw new Error("CDP returned empty response");

  try {
    const parsed = JSON.parse(value);
    if (parsed.code !== undefined && parsed.code !== 0 && parsed.code !== 200) {
      throw new Error(`API error ${parsed.code}: ${parsed.message || "unknown"}`);
    }
    return parsed.data !== undefined ? parsed.data : parsed;
  } catch (e) {
    if (e.message.startsWith("API error")) throw e;
    throw new Error(`Failed to parse API response: ${value.substring(0, 200)}`);
  }
}

// ─── Formatting helpers ────────────────────────────────────────

function fmtPct(v) {
  if (v == null || isNaN(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function fmtAmt(v) {
  if (v == null || isNaN(v)) return "—";
  return `${v.toFixed(2)}亿`;
}

function fmtPrice(v) {
  if (v == null || isNaN(v)) return "—";
  return v.toFixed(2);
}

// ─── MCP Server ────────────────────────────────────────────────

const server = new McpServer({
  name: "fupanhui",
  version: "1.0.0",
});

server.tool("ping", "检查 CDP proxy 和复盘会连接是否正常", {}, async () => {
  try {
    const target = await getTarget();
    const data = await cdpFetch("/api/v1/client/reviews/latest-date", { mode: "auto" });
    return {
      content: [{
        type: "text",
        text: `✅ CDP proxy 连接正常 (target: ${target.substring(0, 12)}...)\n📊 复盘会最新交易日: ${data.latest_date || data.trade_date || JSON.stringify(data)}`,
      }],
    };
  } catch (e) {
    return {
      content: [{ type: "text", text: `❌ 连接失败: ${e.message}` }],
      isError: true,
    };
  }
});

server.tool(
  "get_latest_date",
  "获取复盘会最新交易日期",
  {},
  async () => {
    const data = await cdpFetch("/api/v1/client/reviews/latest-date", { mode: "auto" });
    return {
      content: [{ type: "text", text: `最新交易日: ${data.latest_date || data.trade_date || JSON.stringify(data)}` }],
    };
  }
);

server.tool(
  "get_market_overview",
  "获取市场总览数据（上证/深证/创业板指数、涨跌家数、成交额等）。可指定日期，默认最新。",
  { trade_date: z.string().optional().describe("交易日期 YYYY-MM-DD，留空取最新") },
  async ({ trade_date }) => {
    const params = { mode: "auto" };
    if (trade_date) params.trade_date = trade_date;

    const [latest, market] = await Promise.all([
      cdpFetch("/api/v1/client/reviews/latest-date", { mode: "auto" }),
      cdpFetch("/api/v1/client/reviews/market", { ...params, days: 1 }),
    ]);

    const date = trade_date || latest.latest_date || latest.trade_date;
    const lines = [`📊 ${date} 市场总览\n`];

    if (market.market_summary || market.summary) {
      const s = market.market_summary || market.summary;
      lines.push(`上证指数: ${fmtPrice(s.sh_close || s.close)} ${fmtPct(s.sh_pct_chg || s.pct_chg)}`);
      lines.push(`涨/跌家数: ${s.adv_count || "?"} / ${s.dec_count || "?"}`);
      lines.push(`成交额: ${fmtAmt(s.total_amount || s.amount)}`);
    } else {
      // Fallback: try to extract from raw data
      lines.push(JSON.stringify(market, null, 2).substring(0, 1500));
    }

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

server.tool(
  "get_daily_summary",
  "获取每日复盘摘要（板块强度、涨停梯队、情绪指标等）",
  { trade_date: z.string().optional().describe("交易日期 YYYY-MM-DD") },
  async ({ trade_date }) => {
    const params = {};
    if (trade_date) params.trade_date = trade_date;

    const data = await cdpFetch("/api/v1/client/reviews/summary", params);
    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2).substring(0, 4000) }],
    };
  }
);

server.tool(
  "list_sectors",
  "列出复盘会所有题材板块（227个），支持按涨幅/成交额/强度排序。返回板块代码、名称、类型、涨跌幅、涨停数、成交额、强度。",
  {
    trade_date: z.string().optional().describe("交易日期 YYYY-MM-DD"),
    sort_by: z.enum(["pct_chg", "amount", "strength", "name"]).optional().describe("排序字段，默认 strength"),
    sort_order: z.enum(["desc", "asc"]).optional().describe("排序方向，默认 desc"),
    top: z.number().optional().describe("只返回前 N 个，默认全部"),
    keyword: z.string().optional().describe("按关键词过滤板块名"),
  },
  async ({ trade_date, sort_by = "strength", sort_order = "desc", top, keyword }) => {
    const params = { mode: "auto" };
    if (trade_date) params.trade_date = trade_date;

    const data = await cdpFetch("/api/v1/client/reviews/sectors/search", params);
    let sectors = data.sectors || data.data || data || [];
    if (!Array.isArray(sectors)) sectors = [];

    if (keyword) {
      sectors = sectors.filter(s => (s.name || "").includes(keyword));
    }

    const field = sort_by;
    sectors.sort((a, b) => {
      const va = a[field] ?? -Infinity;
      const vb = b[field] ?? -Infinity;
      return sort_order === "desc" ? vb - va : va - vb;
    });

    if (top) sectors = sectors.slice(0, top);

    const lines = [`📋 板块列表 (${sectors.length}个)\n`];
    lines.push("名称 | 类型 | 涨跌幅 | 涨停数 | 强度 | 成交额");
    lines.push("---|---|---|---|---|---");

    for (const s of sectors) {
      lines.push(
        `${s.name || "?"} | ${s.type_label || s.type || "?"} | ${fmtPct(s.pct_chg)} | ${s.limit_up_count ?? "—"} | ${s.strength ?? "—"} | ${fmtAmt(s.relative_amount_ratio)}`
      );
    }

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

server.tool(
  "get_sector_kline",
  "获取板块K线数据（边际量、成交额、涨幅的N日走势）",
  {
    ts_code: z.string().describe("板块代码，如 885537.TI"),
    trade_date: z.string().optional().describe("截止日期 YYYY-MM-DD"),
    days: z.number().optional().describe("天数，默认20"),
  },
  async ({ ts_code, trade_date, days = 20 }) => {
    const params = { days, period: "daily" };
    if (trade_date) params.trade_date = trade_date;

    const data = await cdpFetch(`/api/v1/client/reviews/sector-cycle/${encodePathSegment(assertTsCode(ts_code))}/kline`, params);
    const kline = data.kline || [];
    const name = data.name || ts_code;

    const lines = [`📈 ${name} (${ts_code}) K线数据 (${kline.length}日)\n`];
    lines.push("日期 | 涨幅% | 边际量% | 成交额(亿)");
    lines.push("---|---|---|---");

    for (const k of kline) {
      lines.push(`${k.trade_date || "?"} | ${fmtPct(k.pct_chg)} | ${fmtPct(k.diff_ratio)} | ${fmtAmt(k.amount)}`);
    }

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

server.tool(
  "get_sector_stocks",
  "获取板块成分股列表，包含个股涨跌幅、成交额、申万行业、资金流向、龙头标签等丰富字段",
  {
    ts_code: z.string().describe("板块代码，如 885537.TI"),
    trade_date: z.string().optional().describe("交易日期 YYYY-MM-DD"),
    sort_by: z.enum(["pct_chg", "amount", "fund_flow_1d", "fund_flow_5d", "pct_chg_5d", "pct_chg_10d", "pct_chg_20d"]).optional().describe("排序字段"),
    sort_order: z.enum(["desc", "asc"]).optional().describe("排序方向"),
    top: z.number().optional().describe("只返回前 N 只"),
    min_amount: z.number().optional().describe("最低成交额(亿)过滤"),
  },
  async ({ ts_code, trade_date, sort_by = "amount", sort_order = "desc", top, min_amount }) => {
    const params = {};
    if (trade_date) params.trade_date = trade_date;

    const data = await cdpFetch(`/api/v1/client/reviews/sector-cycle/${encodePathSegment(assertTsCode(ts_code))}/stocks`, params);
    let stocks = data.stocks || [];
    const sectorName = data.name || ts_code;

    if (min_amount) {
      stocks = stocks.filter(s => (s.amount || 0) >= min_amount);
    }

    if (sort_by) {
      stocks.sort((a, b) => {
        const va = a[sort_by] ?? -Infinity;
        const vb = b[sort_by] ?? -Infinity;
        return sort_order === "desc" ? vb - va : va - vb;
      });
    }

    if (top) stocks = stocks.slice(0, top);

    const lines = [`🧩 ${sectorName} (${ts_code}) 成分股 (${data.trade_date})`];
    lines.push(`共 ${data.stock_count || stocks.length} 只，当前显示 ${stocks.length} 只\n`);
    lines.push("代码 | 名称 | 现价 | 日涨% | 5日% | 20日% | 成交额 | 申万行业 | 龙头标签 | 资金1日 | 资金5日");
    lines.push("---|---|---|---|---|---|---|---|---|---|---");

    for (const s of stocks) {
      const leader = s.leader_plate || "";
      const sw = (s.sw_industry || "").replace(/-/g, "/");
      lines.push(
        `${s.ts_code || "?"} | ${s.name || "?"} | ${fmtPrice(s.price)} | ${fmtPct(s.pct_chg)} | ${fmtPct(s.pct_chg_5d)} | ${fmtPct(s.pct_chg_20d)} | ${fmtAmt(s.amount)} | ${sw} | ${leader} | ${fmtAmt(s.fund_flow_1d)} | ${fmtAmt(s.fund_flow_5d)}`
      );
    }

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

server.tool(
  "get_stock_detail",
  "获取个股详情：最新价、多日涨幅、成交额、申万行业、龙头板块、资金流向",
  {
    ts_code: z.string().describe("股票代码，如 600519.SH"),
    trade_date: z.string().optional().describe("交易日期 YYYY-MM-DD"),
  },
  async ({ ts_code, trade_date }) => {
    const params = {};
    if (trade_date) params.trade_date = trade_date;

    // Get stock kline for latest data
    const data = await cdpFetch(`/api/v1/client/stock-kline/${encodePathSegment(assertTsCode(ts_code))}/kline`, {
      period: "daily",
      limit: 1,
      offset: 0,
    });

    const kline = data?.kline || [];
    const quote = data?.quote || {};
    const last = kline[kline.length - 1] || {};

    const lines = [`📈 ${data.name || ts_code} (${ts_code})\n`];
    lines.push(`日期: ${last.trade_date || trade_date || "?"}`);
    lines.push(`收盘: ${fmtPrice(last.close || quote.price)}`);
    lines.push(`涨跌幅: ${fmtPct(last.pct_chg || quote.pct_chg)}`);
    lines.push(`成交额: ${fmtAmt(last.amount || quote.amount)}`);
    if (last.high) lines.push(`最高: ${fmtPrice(last.high)}  最低: ${fmtPrice(last.low)}  开盘: ${fmtPrice(last.open)}`);
    if (data.sw_industry) lines.push(`申万行业: ${data.sw_industry}`);
    if (data.leader_plate) lines.push(`龙头板块: ${data.leader_plate}`);

    if (kline.length > 1) {
      lines.push(`\n最近 ${kline.length} 日走势:`);
      lines.push("日期 | 收盘 | 涨幅% | 成交额");
      lines.push("---|---|---|---");
      for (const k of kline.slice(-10)) {
        lines.push(`${k.trade_date || "?"} | ${fmtPrice(k.close)} | ${fmtPct(k.pct_chg)} | ${fmtAmt(k.amount)}`);
      }
    }

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

server.tool(
  "search_sectors",
  "按关键词搜索板块，返回匹配的板块代码和名称",
  { keyword: z.string().describe("搜索关键词，如 '半导体'、'AI'、'光伏'") },
  async ({ keyword }) => {
    const data = await cdpFetch("/api/v1/client/reviews/sectors/search", { mode: "auto" });
    let sectors = data.sectors || data.data || data || [];
    if (!Array.isArray(sectors)) sectors = [];

    const matches = sectors.filter(s => (s.name || "").includes(keyword));

    if (matches.length === 0) {
      return {
        content: [{ type: "text", text: `未找到包含 "${keyword}" 的板块` }],
      };
    }

    const lines = [`🔍 搜索 "${keyword}" 匹配 ${matches.length} 个板块\n`];
    for (const s of matches) {
      lines.push(`${s.ts_code} | ${s.name} | ${s.type_label || ""} | ${fmtPct(s.pct_chg)} | 强度:${s.strength ?? "—"}`);
    }
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

server.tool(
  "get_calendar",
  "获取交易月历",
  {
    year: z.number().optional().describe("年份，如 2026"),
    month: z.number().optional().describe("月份 1-12"),
  },
  async ({ year, month }) => {
    const now = new Date();
    const y = year || now.getFullYear();
    const m = month || now.getMonth() + 1;

    const data = await cdpFetch("/api/v1/client/calendar/month", { year: y, month: m });
    const dates = data.dates || data.trade_dates || data;

    return {
      content: [{ type: "text", text: `${y}年${m}月交易日:\n${JSON.stringify(dates, null, 2).substring(0, 2000)}` }],
    };
  }
);

server.tool(
  "get_trade_dates",
  "获取最近 N 个交易日期列表",
  { days: z.number().optional().describe("天数，默认10") },
  async ({ days = 10 }) => {
    const data = await cdpFetch("/api/v1/client/data/auction/trade-dates", { days });
    return {
      content: [{ type: "text", text: `最近交易日: ${(data.dates || []).join(", ")}\n最新: ${data.latest || "?"}` }],
    };
  }
);

server.tool(
  "get_limit_ladder",
  "获取连板晋级数据（涨停梯队）",
  { trade_date: z.string().optional().describe("交易日期 YYYY-MM-DD") },
  async ({ trade_date }) => {
    const params = {};
    if (trade_date) params.trade_date = trade_date;

    const data = await cdpFetch("/api/v1/client/limit/ladder", params);
    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2).substring(0, 5000) }],
    };
  }
);

server.tool(
  "get_sector_rotation",
  "获取板块轮动视图数据",
  { trade_date: z.string().optional().describe("交易日期 YYYY-MM-DD") },
  async ({ trade_date }) => {
    const params = { mode: "auto" };
    if (trade_date) params.trade_date = trade_date;

    const data = await cdpFetch("/api/v1/client/reviews/sector-rotation-view", params);
    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2).substring(0, 5000) }],
    };
  }
);

// ─── Start ─────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("[fupanhui-mcp] Server started on stdio");
