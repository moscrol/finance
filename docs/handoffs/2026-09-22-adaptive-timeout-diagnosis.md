# 2026-09-22 判官超时归属诊断

## 背景

前次真实验收的末次判官收据只有 `timeout_asked=74.8955`、`TimeoutError` 和随后 0 秒拒发；这个数字是获批额度，不是实际调用墙钟。需要在不调用真实模型、不增加生产预算、不操作 8792 的前提下，区分 HTTP 空闲读取超时、整次请求绝对截止和语义判官共享窗拒发。

## 方法

新增 `scripts/review_probes/diagnose_llm_timeout.py`，只启动 `127.0.0.1` 本地 HTTP 服务，仍走生产 `llm_refine.complete`、`chat_with_tools`、`synthesize_messages_stream` 和 `SemanticEpisodeVerifier._run_judge_once`。新增 `intelligence/tests/test_llm_timeout_diagnostic.py`，钉住本机边界、零预算不发请求、共享窗第三槽零秒拒发、根期限与共享窗归因分离、收据不可覆盖和外部地址拒绝。

## 结果

收据：`/Users/a77/.finance-runtime/adaptive-timeout-diagnosis-20260922/transport-expanded.json`。

- 非流式 `complete()` 获批 0.8 秒时，响应体持续滴流约 2.93 秒仍成功；响应头/响应体停顿才在约 0.8 秒失败。说明 `urlopen(timeout=...)` 是 socket 空闲等待上限，不是绝对请求截止。
- 工具流式持续滴流约 2.95 秒成功；未形成完整 SSE 行时约 3.25 秒才交付，也未被总时限打断。
- 合成流式的定时器在滴流和半行场景分别约 1.45/1.45 秒结束，但都超过其 1.2 秒获批时间，现有定时器不能当作严格墙钟证明。
- 判官共享窗两次约 0.402 秒慢失败后，第三槽实际请求数为 0，`timeout_asked=0`，根期限仍剩约 8.79 秒，归因为 `semantic judge window exhausted by prior attempt`。
- 判官持续滴流约 2.93 秒后返回有效报告，状态为可用；这证明当前判官路径会接受越过 `timeout_asked` 的完整响应。
- 根期限为 0 时请求数和台账记录均为 0，归因仍为 `semantic judge deadline exhausted`。

严格探针故意以非零退出，因为当前代码存在上述超时越窗；`--assert-deadline` 是修复验收闸，不是本轮通过标准。定向测试：`14 passed`，pytest 收据由 conftest 生成于 `/Users/a77/.finance-runtime/test-receipts/20260921T183215Z-bcd48b2f.json`。

## 结论与边界

已定位为：共享预算分配和零秒拒发有效；在途 HTTP/流读取没有统一的绝对墙钟截止。尚不能从旧真实收据判断 GLM 当时卡在响应头、响应体停顿还是持续流式输出，因为旧产物没有请求级实际耗时与字节间隔。

本轮没有修改 `llm_refine`、判官预算、重试次数或生产服务，没有重跑旧自然模型题。后续若修复，应先让严格本地探针通过，再另行预注册真实样本；不要把本机慢服务结果当作供应商行为或内容正确性结论。
