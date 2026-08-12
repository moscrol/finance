# 在途交接 · cursor/repair-timeout-retry-d7ac

更新：2026-08-12 · Cursor Cloud

## 这个分支做什么

修复轮 LLM 瞬态错误单次重试（熔断上限 1）——`agent_episode.resume()` 此前对超时一击终局，R2 四题、R3 A7 的死因。PR #296 已 ready for review。

## 当前状态

- 全部已提交已推送（92599b00 实现 + 5c81e335 交接），工作树干净。
- **卡在等用户审 #296**；合并 main 必须用户确认，未动。
- 顺带更新了 `inflight/main.md`（tier 方差归因 + Mac 侧判决命令），随 PR 走。

## 已验证

- 受影响 6 测试文件 245 passed；改/新增 4 条重试测试全绿；ruff 干净。
- 全量 4074 passed / 26 failed，失败集合与 main 基线（e999c979，独立 worktree）逐条一致=环境性。**收据条件：云端 /usr/bin/python3 + FWP_ALLOW_ANY_PYTHON=1，非 canonical venv**。

## 未验证 / 已知边界

- 未在真实 provider 上验证重试路径（云端无 LLM key）；只有 ScriptedModel。
- 合并后需重跑 A 组看 A7/A9/A10 超时降级是否消失——这是效果判决，测试绿≠效果达成。
- tier 方差只归因到机制未判决：需 Mac 上对比 R1/R2 A1 的 continuous-episode.json `contract.research_tier`（细节见 inflight/main.md 第 2 条）。
- 云端无 CC_REMOTE_EXEC_TOKEN，触不到 Mac。

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
