#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { parseArgs } = require("node:util");

const { values } = parseArgs({
  options: {
    runs: { type: "string" },
    webapp: { type: "string" },
    fixture: { type: "string" },
    mutation: { type: "string", default: "none" },
  },
});
assert(
  values.runs && values.webapp && values.fixture,
  "Required: --runs <archive> --webapp <webapp> --fixture <json>",
);
const resolveOptions = { paths: [values.webapp] };
const markedEntry = require.resolve("marked", resolveOptions);
const { marked } = require(markedEntry);
const markedVersion = require(require.resolve("marked/package.json", resolveOptions)).version;
const fixture = JSON.parse(fs.readFileSync(values.fixture, "utf8"));
assert.equal(markedVersion, fixture.marked_version, "Renderer version differs from fixture");
assert(["none", "wrong_pe", "collapsed_boundaries", "swapped_breadth"].includes(values.mutation));
const results = [];
let mutationApplied = false;

for (const item of fixture.cases) {
  const directory = path.join(values.runs, item.run);
  const original = fs.readFileSync(path.join(directory, "answer.md"), "utf8");
  let text = original;
  if (item.case === "arithmetic" && values.mutation === "wrong_pe") {
    const result = item.rows.at(-1)[2];
    text = text.replace(`| ${result} |`, `| ${result.replace("20", "22.5")} |`);
  } else if (item.case === "arithmetic" && values.mutation === "collapsed_boundaries") {
    text = text.replace(/\n{2,}/g, "\n");
  } else if (item.case === "market" && values.mutation === "swapped_breadth") {
    const fragment = item.required_fragments.find((value) => value.includes("4234") && value.includes("1151"));
    const swapped = fragment.replace(/4234|1151/g, (value) => value === "4234" ? "1151" : "4234");
    text = text.replace(fragment, swapped);
  }
  mutationApplied ||= text !== original;
  const episode = JSON.parse(
    fs.readFileSync(path.join(directory, "continuous-episode.json"), "utf8"),
  );
  const tables = marked.lexer(text, { gfm: true }).filter((token) => token.type === "table");
  const errors = [];
  try {
    if (item.rows) {
      assert.equal(tables.length, 1, "Expected exactly one owned table");
      assert.deepEqual(tables[0].header.map((cell) => cell.text), fixture.header);
      assert.deepEqual(
        tables[0].rows.map((row) => row.map((cell) => cell.text)),
        item.rows,
        "Table labels, formulas, units, results or boundaries changed",
      );
    }
    for (const fragment of item.required_fragments) {
      assert(text.includes(fragment), `Missing fixed fixture fragment: ${fragment}`);
    }
    for (const fragment of fixture.forbidden_fragments) {
      assert(!text.includes(fragment), `Internal marker leaked: ${fragment}`);
    }
  } catch (error) {
    errors.push(error.message);
  }
  results.push({
    case: item.case,
    run: item.run,
    passed: errors.length === 0,
    table_rows: tables.map((table) => table.rows.length),
    errors,
    semantic_status: episode.semantic_verifier?.status,
    judge_status: episode.semantic_verifier?.judge_status,
    semantic_issues: episode.semantic_verifier?.issues ?? [],
    unverified_numeric_fragments:
      episode.semantic_verifier?.premise_calculation_review?.unverified_numeric_fragments ?? [],
  });
}
assert(values.mutation === "none" || mutationApplied, "Requested mutation did not apply");
const passed = results.every((result) => result.passed);
console.log(JSON.stringify({
  scope: "fixed_fixture_fragments_and_exact_owned_table_rendering",
  does_not_verify: [
    "source revision or supplier truth",
    "all prose or financial interpretations",
    "absence of contradictory statements elsewhere",
    "other questions or model runs",
  ],
  fixture: path.resolve(values.fixture),
  renderer: { version: markedVersion, entry: markedEntry },
  process_local_mutation: values.mutation,
  mutation_applied: mutationApplied,
  passed,
  results,
}, null, 2));
process.exitCode = passed ? 0 : 1;
