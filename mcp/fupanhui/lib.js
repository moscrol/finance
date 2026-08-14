/**
 * Pure helpers for the fupanhui MCP server, kept separate from index.js
 * so they can be unit-tested without starting the stdio server.
 */

// 证券/板块代码：数字或字母开头的代码 + "." + 交易所/类型后缀，如 885537.TI、600519.SH
const TS_CODE_RE = /^[0-9A-Za-z]{1,12}\.[A-Za-z]{1,8}$/;

export function assertTsCode(code) {
  if (typeof code !== "string" || !TS_CODE_RE.test(code)) {
    throw new Error(`Invalid ts_code: ${JSON.stringify(String(code)).substring(0, 60)}`);
  }
  return code;
}

export function encodePathSegment(segment) {
  return encodeURIComponent(String(segment));
}

export function buildQuery(params = {}) {
  return Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}

const PATH_RE = /^\/[A-Za-z0-9/_.%-]*$/;

export function buildUrl(apiPath, params = {}) {
  if (typeof apiPath !== "string" || !PATH_RE.test(apiPath)) {
    throw new Error(`Invalid API path: ${JSON.stringify(String(apiPath)).substring(0, 100)}`);
  }
  const query = buildQuery(params);
  return query ? `${apiPath}?${query}` : apiPath;
}

// 生成在浏览器里执行的同步 XHR 表达式；URL 以 JSON 字面量嵌入，杜绝 JS 字符串注入
export function buildXhrExpr(url) {
  return `(function(){
    var x = new XMLHttpRequest();
    x.open("GET", ${JSON.stringify(String(url))}, false);
    x.send();
    return x.responseText;
  })()`;
}
