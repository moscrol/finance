/** Explicit opt-in bridge; no model, database path, SQL or shell chosen by the model. */
import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { resolve, isAbsolute } from "node:path";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const schemaVersion = "finance-history-context/v1";
const maxBytes = 48_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function validatePayload(text: string, asOf: string) {
  if (Buffer.byteLength(text, "utf8") > maxBytes || text.split("\n").length > 2000) {
    throw new Error("History context exceeds atomic output budget; no partial table delivered.");
  }
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error("History context is not valid JSON.");
  }
  if (!isRecord(payload) || payload.schema_version !== schemaVersion || payload.as_of !== asOf ||
      payload.evidence_grade !== "INFERRED" || !Array.isArray(payload.blocks) || payload.blocks.length !== 2) {
    throw new Error("History context protocol mismatch.");
  }
  const titles = ["市场情绪环境类比 [D10]", "多维对照镜头 [D10]"];
  return payload.blocks.map((block: unknown, index: number) => {
    if (!isRecord(block) || block.title !== titles[index] || typeof block.detail !== "string" ||
        !block.detail.trim() || block.sha256 !== createHash("sha256").update(block.detail, "utf8").digest("hex")) {
      throw new Error("History context content identity mismatch.");
    }
    return createHash("sha256").update(block.detail, "utf8").digest("hex");
  });
}

export function childEnvironment(root: string): NodeJS.ProcessEnv {
  // The calculator needs no provider credentials or operator profile variables.
  // This reduces accidental exposure; it is not an OS sandbox.
  const env: NodeJS.ProcessEnv = {
    PYTHONPATH: root, PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1",
  };
  for (const key of ["PATH", "LANG", "LC_ALL", "TZ", "TMPDIR", "SYSTEMROOT", "WINDIR"]) {
    if (process.env[key] !== undefined) env[key] = process.env[key];
  }
  return env;
}

export function createHistoryTool(reviewReadouts = false) {
  return defineTool({
    name: "finance_market_history",
    label: "Market history (read only)",
    description: "按明确截止日读取本地市场历史比较。返回旧D10后续事实与river多维镜头、来源、缺口和时间限制；两组候选独立，不能按名次嫁接收益。仅INFERRED研究线索，不是预测概率或已验证环境剧本。不联网、不写库、不读画像、不调用其他模型。整块超预算则拒绝，不交付残表。",
    parameters: Type.Object({
      as_of: Type.String({ description: "用户指定的截止日 YYYY-MM-DD；不得擅自改成今天", pattern: "^\\d{4}-\\d{2}-\\d{2}$" }),
    }, { additionalProperties: false }),
    async execute(_id, params, signal) {
      if (signal?.aborted) throw new Error("History request cancelled.");
      // Operator configuration is intentionally outside the model's tool arguments.
      const root = process.env.FINANCE_HISTORY_CODE_ROOT;
      const python = process.env.FINANCE_HISTORY_PYTHON;
      const db = process.env.FINANCE_HISTORY_DB;
      if (!root || !python || !db || ![root, python, db].every(isAbsolute)) {
        throw new Error("Configure absolute FINANCE_HISTORY_CODE_ROOT, FINANCE_HISTORY_PYTHON and FINANCE_HISTORY_DB first.");
      }
      const text = await new Promise<string>((accept, reject) => {
        const fail = () => reject(new Error("History tool failed, cancelled, timed out or exceeded its output budget; no partial result delivered."));
        try {
          execFile(python, ["-m", "intelligence.history_context_cli", "--db", db, "--as-of", params.as_of, "--timeout", "30",
            ...(reviewReadouts ? ["--review-readouts"] : [])], {
            cwd: resolve(root), signal, timeout: 35_000, maxBuffer: maxBytes + 1,
            encoding: "utf8", env: childEnvironment(resolve(root)),
          }, (error, stdout) => {
            // execFile errors contain the private command/path; never pass them through.
            if (error) fail();
            else accept(stdout.trim());
          });
        } catch {
          fail();
        }
      });
      let publicText = text;
      let reviewSource: Record<string, unknown> | undefined;
      if (reviewReadouts) {
        let value: unknown;
        try { value = JSON.parse(text); } catch { throw new Error("History review source protocol mismatch."); }
        if (!isRecord(value) || value.schema_version !== "finance-history-review-source/v1" ||
            typeof value.public_text !== "string" || !Array.isArray(value.readouts) || value.readouts.length !== 2) {
          throw new Error("History review source protocol mismatch.");
        }
        publicText = value.public_text;
        reviewSource = value;
      }
      const blockHashes = validatePayload(publicText, params.as_of);
      return {
        content: [{ type: "text", text: publicText }],
        details: { schema_version: schemaVersion, as_of: params.as_of, block_hashes: blockHashes,
          ...(reviewSource ? { review_source: reviewSource } : {}) },
      };
    },
  });
}

export const historyTool = createHistoryTool();

export default function (pi: ExtensionAPI) {
  pi.registerTool(historyTool);
}
