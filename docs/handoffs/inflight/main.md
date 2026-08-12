# 在途交接 · main

更新：2026-08-13 · Cursor Cloud（#296+#297 已合并部署，闭环快照见 `docs/handoffs/2026-08-13-repair-timeout-retry-loop.md`）

## 当前状态

- canonical 8792 = `a317f37f`（repair 超时重试 + headroom 修复均已上线），health/ready 全绿。
- R4/R5 验收产物：`eval/runs/20260813T0159Z-r4-*.json` / `20260813T0245Z-r5-*.json`。逐题修复收据用 `scripts/dump_episode_receipts.py`，别再手扒 episode JSON。
- 生产 run 目录在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`（8792 进程环境），不在仓内 `intelligence/users/`。

## 下一步

1. **白天稳定时段重跑全 A 组做公平对照**（R4/R5 都在凌晨中转最差时段，跨轮数字仅供参考；R5 的窗口尺寸收据 `asked=30.0` 是确定性的）。
2. **新形状立案**：①`repair_model_stop`/`invalid_repair_finish`——30s 窗内 provider 到货、模型没吐合法修复 FINISH（协议问题非超时，R5 五题）；②A3 `continuous_runtime_failed`（31s 无产物）；③A1-R2 主路径超时+零证据（`tools_open=False` 时 `admit_repair` 拒，属另一条失败链）。
3. A5 日期错位（07-23 题拿 08-12 证据 + 路由进 general_finance_qa）待立案。
4. knevo 后续：suggest_options 缺口镜像、report→track 接力。
5. 工具沉淀待归位（Mac `~/harness-reference`，隧道可达但本轮未动它避免盲改）：「纠正层写自己的收据」「重试窗口尺寸取当前权威不取旧字段」候选 BUILD.md；「失败集合对基线 worktree diff」候选 TOOLKIT。

## 踩过的坑

- 归因先翻 episode 产物再下结论；中途读数会骗人。
- 中转晚间超时会整轮污染对照；挑稳定时段跑。
- 远程复杂脚本用 stdin heredoc，不要 `python3 -c`（远程 sh 吃括号）；不写 token 进交接/commit。
- 验收跑长题用 nohup + 轮询日志（CF 隧道 100s 上限）。
- 切 8792 按 cutover 手册蓝绿：worktree detach → 停服务 → 切软链 → 起服务；RAG prewarm 约 60-90s 才 listen。

## 已验证

- R5 隔离端口（8794 @ fix 分支）：重试窗全部 30s，A4 走通 `repair_model_finish`，A6/A7 烧爆账本形状进闸门。
- A1 tier 判决：三轮均 `standard`，非路由方差；30s 是 standard 检索分配段（90 − 合成保留 60）。
- 测试：coordinator+episode 89 passed、邻接 5 文件 144 passed、ruff 干净（云端 `/usr/bin/python3` + `FWP_ALLOW_ANY_PYTHON=1`）。
