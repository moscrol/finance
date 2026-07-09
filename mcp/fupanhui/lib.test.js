import { test } from "node:test";
import assert from "node:assert/strict";
import { assertTsCode, buildQuery, buildUrl, buildXhrExpr, encodePathSegment } from "./lib.js";

test("assertTsCode accepts valid codes", () => {
  for (const code of ["885537.TI", "600519.SH", "000001.SZ", "BK0500.EM"]) {
    assert.equal(assertTsCode(code), code);
  }
});

test("assertTsCode rejects injection payloads and malformed codes", () => {
  const bad = [
    '600519.SH", false); alert(1); x.open("GET", "x',
    "../../../etc/passwd",
    "600519.SH/../admin",
    "600519",
    "",
    null,
    undefined,
    123,
    "600519.SH?x=1",
    "a b.SH",
  ];
  for (const code of bad) {
    assert.throws(() => assertTsCode(code), /Invalid ts_code/);
  }
});

test("encodePathSegment escapes path metacharacters", () => {
  assert.equal(encodePathSegment("a/b?c#d"), "a%2Fb%3Fc%23d");
  assert.equal(encodePathSegment('a"b'), "a%22b");
});

test("buildQuery encodes keys and values, skips null/undefined", () => {
  assert.equal(
    buildQuery({ a: "x y", b: 'q"&=', c: null, d: undefined, days: 20 }),
    "a=x%20y&b=q%22%26%3D&days=20"
  );
});

test("buildUrl rejects paths with unsafe characters", () => {
  assert.throws(() => buildUrl('/api/"x'), /Invalid API path/);
  assert.throws(() => buildUrl("/api/a?b=c"), /Invalid API path/);
  assert.throws(() => buildUrl("relative/path"), /Invalid API path/);
  assert.equal(buildUrl("/api/v1/x", { a: 1 }), "/api/v1/x?a=1");
  assert.equal(buildUrl("/api/v1/x"), "/api/v1/x");
});

test("buildXhrExpr embeds URL as a JSON string literal (no JS injection)", () => {
  const url = '/api/x?q=%22%3B%20alert(1)%3B%20%22';
  const expr = buildXhrExpr(url);
  assert.ok(expr.includes(`x.open("GET", ${JSON.stringify(url)}, false)`));
  // A quote in the (pre-encoded) URL must never appear unescaped in the expression
  const evil = 'quote " here';
  const expr2 = buildXhrExpr(evil);
  assert.ok(expr2.includes('"quote \\" here"'));
});
