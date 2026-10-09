/** Native Pi test provider: controlled author and reviewer, never a financial model. */
import assert from "node:assert/strict";
import { createAssistantMessageEventStream, getCurrentTools, type AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const text = (value: unknown): string => typeof value === "string" ? value : Array.isArray(value)
  ? value.filter(part => part.type === "text").map(part => part.text).join("\n") : "";

export default function (pi: ExtensionAPI) {
  globalThis.fetch = async () => { throw new Error("review test attempted network"); };
  let authors = 0;
  let reviewers = 0;
  const scenario = process.env.FINANCE_REVIEW_SCENARIO ?? "repair";
  let abort = () => {};
  let followed = false;
  pi.on("session_start", (_event, ctx) => { abort = () => ctx.abort(); });
  pi.on("turn_end", () => {
    if (scenario === "fresh_turn" && authors === 3 && !followed) {
      followed = true;
      pi.sendUserMessage("现在改为截至2025-04-11的历史比较。", { deliverAs: "followUp" });
    }
  });
  pi.registerProvider("history-review-offline", {
    baseUrl: "http://127.0.0.1:1", apiKey: "offline", api: "history-review-offline",
    models: [{ id: "scripted", name: "Offline author/reviewer", reasoning: false, input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 200000, maxTokens: 20000 }],
    streamSimple(model, context, options) {
      const stream = createAssistantMessageEventStream();
      const output: AssistantMessage = { role: "assistant", content: [], api: model.api, provider: model.provider, model: model.id,
        usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } }, stopReason: "pending", timestamp: Date.now() };
      void (async () => {
        try {
          assert.ok(!options?.signal?.aborted);
          const tools = getCurrentTools(context.messages);
          const isAuthor = tools.length > 0;
          if (isAuthor) assert.deepEqual(tools.map(tool => tool.name), ["finance_market_history"]);
          const toolResult = context.messages.findLast(message => message.role === "toolResult");
          await options?.onPayload?.({ model: model.id, messages: context.messages.map(message => message.role === "toolResult"
            ? { role: "tool", content: scenario === "tampered_ack" ? "not delivered" : text(message.content) }
            : message) }, model);
          stream.push({ type: "start", partial: output });
          let body: string;
          if (isAuthor) {
            assert.ok(++authors <= (scenario === "fresh_turn" ? 4 : 3), "unbounded author continuation");
            if (!toolResult) {
              const call = { type: "toolCall" as const, id: "history-1", name: "finance_market_history", arguments: { as_of: "2025-04-10" } };
              output.content = [call];
              output.stopReason = "toolUse";
              stream.push({ type: "toolcall_start", contentIndex: 0, partial: output });
              stream.push({ type: "toolcall_end", contentIndex: 0, toolCall: call, partial: output });
              stream.push({ type: "done", reason: "toolUse", message: output });
              return;
            }
            if (scenario === "nonfactual_laundering") body = authors < 3
              ? "市场成交额均值9875亿元。\n研报有0条。" : "市场成交额均值9875亿元。\n研报指标未知，0个非空观测不等于0条研报。";
            else body = authors < 3 || ["always_reject", "judge_flip"].includes(scenario) ? "涨家数动能相反。" : "涨家数方向为一方近零。";
          } else {
            assert.ok(++reviewers <= 4, "unbounded nested review");
            assert.equal(options?.reasoning, "low");
            assert.equal(options?.maxRetries, 0);
            const user = context.messages.findLast(message => message.role === "user");
            assert.ok(user?.role === "user");
            const request = JSON.parse(text(user.content));
            assert.equal(request.schema_version, "history-answer-review/v1");
            if (scenario === "unavailable") throw new Error("synthetic reviewer outage");
            if (scenario === "cancelled") { abort(); throw new Error("synthetic review cancellation"); }
            const checks = request.claims.map((claim: { claim_id: string; text: string }) => {
              const wrong = claim.text.includes("动能相反") && !(scenario === "judge_flip" && reviewers > 1);
              const laundered = claim.text === "研报有0条。";
              if (request.nonfactual_audit) return { claim_id: claim.claim_id, supported: !laundered,
                reason: laundered ? "0条是事实断言，不是非事实豁免。" : "纯格式。", support_kind: laundered ? "unsupported" : "nonfactual", anchor_indexes: [] };
              return { claim_id: claim.claim_id, supported: !wrong, reason: wrong ? "方向读数是一方近零，不能写反向。" : "已绑定具名读数。",
                support_kind: wrong ? "contradicted" : laundered ? "nonfactual" : "bound_material", anchor_indexes: laundered ? [] : [1] };
            });
            const rejected = request.claims.filter((_claim: unknown, i: number) => !checks[i].supported).map((claim: { sentence_index: number }) => claim.sentence_index);
            const report = { request_id: request.request_id, passed: rejected.length === 0, rejected_sentence_indexes: rejected, issues: [],
              material_claim_checks: scenario === "missing_receipt" ? [] : checks,
              ...(request.nonfactual_audit ? {} : { material_output_checks: [{ output_id: "history_answer", answered: true,
                answer_sentence_indexes: [1], reason: "合成完整性证人，不代表真实金融质量。" }] }) };
            body = scenario === "malformed" ? "not JSON" : scenario === "fenced" ? `\`\`\`json\n${JSON.stringify(report)}\n\`\`\`` : JSON.stringify(report);
          }
          output.content = [{ type: "text", text: body }];
          output.stopReason = !isAuthor && scenario === "truncated" ? "length" : "stop";
          stream.push({ type: "text_start", contentIndex: 0, partial: output });
          stream.push({ type: "text_delta", contentIndex: 0, delta: body, partial: output });
          stream.push({ type: "text_end", contentIndex: 0, content: body, partial: output });
          stream.push({ type: "done", reason: output.stopReason, message: output });
        } catch (error) {
          output.stopReason = "error";
          output.errorMessage = error instanceof Error ? error.message : "offline review test failed";
          stream.push({ type: "error", reason: "error", error: output });
        } finally { stream.end(); }
      })();
      return stream;
    },
  });
}
