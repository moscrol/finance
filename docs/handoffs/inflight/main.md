# 在途交接 · main

更新：2026-08-12 · Cursor Cloud（Mac 隧道已通；A1 tier 已用产物判决；改动在 PR 分支 cursor/repair-timeout-retry-d7ac）

## 这个分支做什么

修「自建 agent 效果差」：#287–295 全合并。数据链全绿。量具中文数字 bug 已修（#295），R3 真值 0/7→1/7（A1 首个 PASS）。

## 当前状态

- **repair 超时单次重试已实现待合并**（PR 分支同名）：`agent_episode.resume()` 瞬态错误（TimeoutError/断连/5xx）在 root 预算存活且残余 repair deadline 可再问价时重试一次，熔断上限 1；台账记 `repair_model_retry`。瞬态判据上移 `services.agent_runtime.is_transient_model_error`（与 provider 链共用单一真本源）。新增/改 4 条测试全绿；全量 4074 passed，26 条失败与 main 基线**逐条一致**（云端环境性：duckdb 数据缺、日期敏感），收据条件=云端 /usr/bin/python3 + FWP_ALLOW_ANY_PYTHON=1，非 canonical venv。
- 三轮对照口径：R1=5b7464be、R2=11da9707（污染，不可判 #293）、R3=ad743a64。

## 下一步

1. **合并 repair 重试 PR 后重跑 A 组**，看 A7/A9/A10 的 repair TimeoutError 是否消失。不要用 A1-R2 当本 PR 验收题。
2. **A1 31s vs 103s 已判决：三轮 `research_tier` 全是 `standard`，不是路由方差。** 产物在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/`。~30s 是 standard 90s 被合成保留钳成的检索分配段（GLM `market_watch` 要 75s 保留，再被 2/3 上限钳成 60s，分配=30s）。R1=30s agent+judge；R2=PLAN 后第二跳超时、0 证据、repair 未入场；R3=有证据后 delivery repair 成功。R2 是另一条失败形状，本 PR 救不了。
3. A5 日期错位（07-23 题拿 08-12 证据 + 被路由进 general_finance_qa）待立案。
4. knevo 后续：suggest_options 缺口镜像、report→track 接力。
5. TOOLKIT 待补：变异还原禁用 `git checkout <file>`。

## 踩过的坑

- 归因先翻 episode 产物再下结论；中途读数会骗人。
- 中转晚间超时会整轮污染对照；挑稳定时段跑。
- 隧道 530=Mac 侧 cloudflared 掉线；长命令 nohup+轮询（CF 100s 上限）。
- 生产 run 在 `FORESIGHT_USERS_DIR`（8792 进程环境），不在仓内 `intelligence/users/`。远程复杂脚本用 stdin heredoc，不要 `python3 -c`。
- 不要把隧道 token 写进交接或 commit。

## 已验证

- R2/R3 归因链走 continuous-episode.json 三层（outcome/semantic_verifier/model_error）。
- provider 链内瞬态重试受单次调用 timeout 窗口约束（烧穿后 remaining≈0 零重试）——这就是 harness 层重试必须存在的原因。
- A1 三轮 `contract.research_tier=standard`（产物判决，不是机制推测）。A7/A9/A10 的 repair 授予实测 16s，第一发 TimeoutError 后无重试。
