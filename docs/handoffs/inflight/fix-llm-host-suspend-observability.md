# LLM 截止与主机睡眠：只补可观测

## 这个分支做什么
2026-09-27 生产「75 秒截止拖了 38 分钟」定性为 Mac 合盖睡眠（非连接卡死）；截止按 monotonic 在睡眠时暂停，语义不变，只让 `model_turn` 与 LLM 调用记录带 `host_suspended_seconds`。

## 当前状态
WIP PR #946（`http://127.0.0.1:3300/a77/finance-workspace-private/pulls/946`），代码 `cf09cae44` + 文档提交，基线 `gitea/main@85bcee6dc`。未合并、未部署、未碰 8792。合入须用户确认。

## 决策与被否方案
- 选只补可观测（用户 09-27 拍板，依据：预算字段只走 75.2s + pmset 睡 2253s）；否传输层单独计睡眠（DarkWake 2 秒就截断转收尾，短暂合盖也被迫降级）、否全部预算计睡眠（两钟本机差 61.6h，漏改一处即永不超时/立刻超时）、否醒后续跑（要设计重试计数，留作后续）。
- 钟：macOS `CLOCK_MONOTONIC_RAW`、Linux `CLOCK_BOOTTIME` 减 `time.monotonic()`；否墙钟相减（NTP 会跳）。
- 字段只进私有 `continuous-episode.json` 与调用记录；否公开 `gate_receipt`（schema v1 键钉死）。
- 详情：`docs/handoffs/2026-09-27-llm-deadline-host-sleep.md`。

## 未验证 / 已知边界
- 没跑全量 pytest 与前端叶子，合入前必须补并用 `check_test_receipt.py --require-full-scope` 审。
- 「所选钟睡眠时继续走」测试里验不到（不能让本机真睡）：把 darwin 钟换成 `CLOCK_UPTIME_RAW` 全部测试照绿。只由本次 pmset 实测支撑。
- Linux `CLOCK_BOOTTIME` 分支本机没跑。
- 生产尚无带新字段的真实合盖样本。

## 下一步
1. 用户确认后补全量四叶再合；部署后遇下一次合盖，核 `host_suspended_seconds` ≈ pmset 睡眠时长。
2. 若要做「醒后续跑」，先改掉主循环「一次截止错误就进收尾」这条前提。

## 踩过的坑
- 分诊时先拿 `remaining_seconds_at_entry` 相邻两轮差对墙钟；对不上就 `pmset -g log | grep -E "Sleep|Wake"`。
- `test_shared_window_zero_rejection_is_not_a_third_request` 在负载约 11、多 pytest 并跑时会红（亚秒窗口 spawn 赶不上，#868 已知），单跑绿，别当本改动回归。
- 边改注释边跑测试 = 混合读数；最终读数只认 `cf09cae4` 那张。

## 已验证
新测试 8 条；变异 7 杀 0 存活（含根预算改计睡眠必红）；定向 1143 passed @ `cf09cae4`；`test_llm_timeout_diagnostic` 停滞/滴流 35 passed；ruff 全仓与 pre-commit 13 道通过。
