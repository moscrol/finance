# 在途交接 · cursor/repair-timeout-retry-d7ac

更新：2026-08-12 · Cursor Cloud（审查修复后第二版）

## 这个分支做什么

修复轮 LLM 瞬态错误单次重试（熔断上限 1）——`agent_episode.resume()` 此前对超时一击终局，R2 四题、R3 A7 的死因。PR #296 已 ready for review。

## 当前状态

- 三个实现提交已推送（92599b00 首版 + 450933b2 审查修复），工作树干净。
- **首版有空操作，已自审查出并修掉**：修复授予常仅 8s（min(剩余,30,缺口×8)），单次 LLM 上限 75s，第一发 timeout=整笔授予，真实 TimeoutError 烧穿后「看余量再重试」恒不触发。第二版从 root hard-cap 未分配余量再铸单次 grant（`grant_for_transient_model_retry`，≤30s、0 工具槽、grant_id 幂等、fail closed），repair/repair_finalize 两跳共用熔断 1 次；异常路径收成 turn.error；瞬态名单补 HTTP 504 / model deadline exhausted。
- **卡在等用户审 #296**；合并 main 必须用户确认，未动。

## 已验证

- 4 条烧真实时钟的测试（monkeypatch monotonic）钉死空操作不复发；受影响 7 文件 262 passed；ruff 干净。
- 全量 4074 passed / 26 failed，失败集合与 main 基线逐条一致=环境性。**收据条件：云端 /usr/bin/python3 + FWP_ALLOW_ANY_PYTHON=1，非 canonical venv**。

## 未验证 / 已知边界

- 未在真实 provider 上验证（云端无 LLM key）；只有 ScriptedModel + 假时钟。
- 铸新 grant 动的是 synthesis reserve 段的 hard-cap 余量——设计上超时补救优先于保留段，quick 档（30s 硬顶）常铸不出，属预期 fail closed。
- 合并后需重跑 A 组看 A7/A9/A10 超时降级是否消失——测试绿≠效果达成。
- tier 方差只归因到机制未判决（见 inflight/main.md 第 2 条）；云端无 CC_REMOTE_EXEC_TOKEN 触不到 Mac。

## 下一步

1. 用户审 #296 → 确认后合并 → 部署 → 重跑 A 组验收。
2. Mac 侧会话执行 tier 判决命令（inflight/main.md）。
3. **工具沉淀待归位（云端触不到 Mac 的三件套文件）**：
   - 「失败集合对基线 worktree 逐条 diff」手法本轮用了两次，应进 TOOLKIT 低成本档；
   - 模式「重试放在能看到剩余预算的那一层，每层重试预算独立」候选 BUILD.md/10_knowledge。

## 踩过的坑

- 云端跑测试要先装 fastapi/uvicorn/duckdb/ruff/pyyaml/openai-agents，再带 FWP_ALLOW_ANY_PYTHON=1（test-environment.json 门禁按设计拦系统解释器）。
- 云端全量 26 条失败全是环境性（duckdb 数据缺、日期敏感），别当回归归因——先对基线 diff 再下结论。
- provider 链内重试受单次调用 timeout 窗口锁死（烧穿后 remaining≈0），「链内已有重试」不等于「超时有纠正层」。
