/** Test-only scripted provider. No HTTP, paid model or financial-quality claim. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createAssistantMessageEventStream, getCurrentTools, type AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { historyTool, validatePayload } from "../market-history.ts";

function checkProtocol() {
  const detail = "只读 Unicode 镜头";
  const payload = {
    schema_version: "finance-history-context/v1", as_of: "2025-04-10", evidence_grade: "INFERRED",
    blocks: ["市场情绪环境类比 [D10]", "多维对照镜头 [D10]"].map(title => ({
      title, detail, sha256: createHash("sha256").update(detail).digest("hex"),
    })),
  };
  assert.equal(validatePayload(JSON.stringify(payload), payload.as_of).length, 2);
  for (const value of [null, {}, [], { ...payload, as_of: "2025-04-11" },
    { ...payload, evidence_grade: "VERIFIED" }, { ...payload, blocks: payload.blocks.slice(1) },
    { ...payload, blocks: payload.blocks.toReversed() }, { ...payload, blocks: [null, null] },
    { ...payload, blocks: payload.blocks.map(block => ({ ...block, detail: "tampered" })) }]) {
    assert.throws(() => validatePayload(JSON.stringify(value), payload.as_of));
  }
  assert.throws(() => validatePayload("secret /private/path is not JSON", payload.as_of), /^Error: History context is not valid JSON\.$/);
  assert.throws(() => validatePayload("中".repeat(16_001), payload.as_of), /atomic output budget/);
  assert.throws(() => validatePayload("\n".repeat(2001), payload.as_of), /atomic output budget/);
}

export default function (pi: ExtensionAPI) {
  checkProtocol();
  let cancellationChecked = false;
  pi.on("session_start", async (_event, ctx) => {
    const cancelled = new AbortController();
    cancelled.abort();
    await assert.rejects(
      historyTool.execute("pre-cancelled", { as_of: "2025-04-10" }, cancelled.signal, undefined, ctx),
      /History request cancelled/,
    );
    cancellationChecked = true;
  });
  // Any accidental fetch is a test failure. The scripted provider never uses IO.
  globalThis.fetch = async () => { throw new Error("offline test attempted fetch"); };
  let requests = 0;
  pi.registerProvider("finance-offline-test", {
    baseUrl: "http://127.0.0.1:1", apiKey: "offline-test-only", api: "finance-offline-test",
    models: [{ id: "scripted", name: "Scripted, not a model", reasoning: false, input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 200000, maxTokens: 1024 }],
    streamSimple(model, context, options) {
      const stream = createAssistantMessageEventStream();
      const output: AssistantMessage = {
        role: "assistant", content: [], api: model.api, provider: model.provider, model: model.id,
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "pending", timestamp: Date.now(),
      };
      void (async () => {
        try {
          assert.ok(cancellationChecked, "pre-cancellation guard was not verified");
          assert.ok(++requests <= 2, "unexpected extra provider request");
          assert.deepEqual(getCurrentTools(context.messages).map(tool => tool.name), ["finance_market_history"]);
          if (options?.signal?.aborted) throw new Error("cancelled");
          stream.push({ type: "start", partial: output });
          const result = context.messages.findLast(message => message.role === "toolResult");
          if (!result) {
            const call = { type: "toolCall" as const, id: "offline-history-1", name: "finance_market_history",
              arguments: { as_of: process.env.FINANCE_TEST_AS_OF ?? "2025-04-10" } };
            output.content.push(call);
            stream.push({ type: "toolcall_start", contentIndex: 0, partial: output });
            stream.push({ type: "toolcall_delta", contentIndex: 0, delta: JSON.stringify(call.arguments), partial: output });
            stream.push({ type: "toolcall_end", contentIndex: 0, toolCall: call, partial: output });
            output.stopReason = "toolUse";
          } else {
            const text = result.content.filter(block => block.type === "text").map(block => block.text).join("\n");
            if (process.env.FINANCE_TEST_EXPECT_ERROR === "1") {
              assert.equal(result.isError, true);
              assert.ok(!text.includes(process.env.FINANCE_HISTORY_DB!));
            } else {
              assert.equal(result.isError, false, text);
              validatePayload(text, "2025-04-10");
              assert.ok(text.includes("trade_date_only") && text.includes("不可嫁接"));
            }
            const receipt = JSON.stringify({ offline: true, provider_received_tool_result: true,
              result_sha256: createHash("sha256").update(text).digest("hex"), is_error: result.isError });
            output.content.push({ type: "text", text: receipt });
            stream.push({ type: "text_start", contentIndex: 0, partial: output });
            stream.push({ type: "text_delta", contentIndex: 0, delta: receipt, partial: output });
            stream.push({ type: "text_end", contentIndex: 0, content: receipt, partial: output });
            output.stopReason = "stop";
          }
          stream.push({ type: "done", reason: output.stopReason, message: output });
        } catch (error) {
          output.stopReason = "error";
          output.errorMessage = error instanceof Error ? error.message : "offline test failed";
          stream.push({ type: "error", reason: "error", error: output });
        } finally {
          stream.end();
        }
      })();
      return stream;
    },
  });
}
