# 在途交接 · main

更新：2026-08-12 · Cursor Cloud（本轮无隧道 token，未触 Mac；改动在 PR 分支 cursor/repair-timeout-retry-d7ac）

## 这个分支做什么

修「自建 agent 效果差」：#287–295 全合并。数据链全绿。量具中文数字 bug 已修（#295），R3 真值 0/7→1/7（A1 首个 PASS）。

## 当前状态

- **repair 超时单次重试已实现待合并**（PR 分支同名）：`agent_episode.resume()` 瞬态错误（TimeoutError/断连/5xx）在 root 预算存活且残余 repair deadline 可再问价时重试一次，熔断上限 1；台账记 `repair_model_retry`。瞬态判据上移 `services.agent_runtime.is_transient_model_error`（与 provider 链共用单一真本源）。新增/改 4 条测试全绿；全量 4074 passed，26 条失败与 main 基线**逐条一致**（云端环境性：duckdb 数据缺、日期敏感），收据条件=云端 /usr/bin/python3 + FWP_ALLOW_ANY_PYTHON=1，非 canonical venv。
- 三轮对照口径：R1=5b7464be、R2=11da9707（污染，不可判 #293）、R3=ad743a64。

## 下一步

1. **合并 repair 重试 PR 后重跑 A 组**，看 A7/A9/A10 超时降级是否消失。
2. **tier 方差已归因到机制，待产物判决**（Mac 侧一条命令）：
   - `for_tier` 表确定性；生产 tier 赋值点仅 generic 合同关键词表（A1 恒 standard）、sub-research 固定 quick、mode_governor。
   - A1 题面带日期前缀**实测不命中** `_BROAD_MARKET_PATTERN.fullmatch`（turn_controller:116），落进 `is_dated_market_review`/envelope/controller LLM 判定链——路由是模型判定，同题可换车道。
   - 另一半嫌疑：`_clamp_to_root_deadline`（conversation_orchestrator:812）对 root 残余取 min 的预算侵蚀。
   - **判决**：R1/R2 的 A1 `continuous-episode.json` 里 `contract.research_tier`（continuous_turn_adapter:780 已落）+ `report.json` 的 turn_intent。tier 不同=路由方差；相同=侵蚀。
3. A5 日期错位（07-23 题拿 08-12 证据 + 被路由进 general_finance_qa）待立案。
4. knevo 后续：suggest_options 缺口镜像、report→track 接力。
5. TOOLKIT 待补：变异还原禁用 `git checkout <file>`。

## 踩过的坑

- 归因先翻 episode 产物再下结论；中途读数会骗人。
- 中转晚间超时会整轮污染对照；挑稳定时段跑。
- 隧道 530=Mac 侧 cloudflared 掉线；长命令 nohup+轮询（CF 100s 上限）。云端 agent 没有 CC_REMOTE_EXEC_TOKEN 时触不到 Mac。

## 已验证

- R2/R3 归因链走 continuous-episode.json 三层（outcome/semantic_verifier/model_error）。
- provider 链内瞬态重试受单次调用 timeout 窗口约束（烧穿后 remaining≈0 零重试）——这就是 harness 层重试必须存在的原因。
