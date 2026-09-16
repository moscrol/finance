# 能力集成阻塞与观察项（BLOCKED）

> 规则：同一外部阻塞重复三次仍无进展 → 停该批，记原件、恢复条件与续跑命令，转独立项（spec §6）。

## 阻塞项

（暂无）

## 观察项（未构成阻塞，接手会话先扫一眼）

- W1 · daily-full-review sync/finalize 今日（2026-09-09）launchd last-exit 均 =2 [实测 launchctl list]。影响 I5 的「数据成功依赖」与明日（09-10 协议起点）首捕获。处置：I5 开工时先读夜跑日志定位原因；未修复前方法捕获按「数据未完成，记录原因与下一次既有执行机会」处理，不硬跑。
- W2 · 00 baseline live 批次进行中（PID 30453 → 8813，user=cb00-baseline，21:39 起）。I1 改分类实现不影响运行中进程（模块已加载），但**不得改 00 原树工作区文件**；I1 在独立 worktree 上做，产出以提交交回。批次结束前不启动新的占模型池批次（spec §2.2-4 串行纪律）。
- W3 · 生产 8792=ac013255 落后 gitea/main 12 提交（缺 #697/#699 等）。J 系工作流若需在生产语义上验收，候选 sidecar 用集成分支起独立实例，不动生产；切流按 spec §1 只做可审核准备。
- W4 · kb 主检出脏且落后（他人 ingest 在途），已绕行 `kb-wt-cap03-runtime`；不修 kb 主树。
- W5 · **当前 cb00-baseline 批次链上带着 3 题假干净**（calc-01/material-01/material-02：终态改名 invalid_repair_finish 类漏判，被历次 --resume 当 completed 搬运；I1 重审已实锤，派生件 `~/.finance-runtime/capability-integration/i1/reclassify-20260909T125222Z-*.json`）。处置：不打断在跑批次；批次停下后，下一次 --resume 必须用 I1 代码（`feat/i1-availability-attribution`@01de7e94）跑——新判据不搬假干净题、按原条件重跑；最终基线件出来后再 reclassify 一次归档四类分布。00 的「干净 N/30」口径在切换新码前不可采信为能力读数。
- W6 · **夜跑 09-09 exit=2 根因**：finalize 守卫败在 `fact_theme_flow_daily` 缺 09-09（最新 09-02），其余 fact 表全到 09-09。这是**数据缺口不是接线问题**；每天 20:40 会持续跳守卫直到该表补齐。处置：该表由 L2/资金流抓取链负责（`run_l2_branch`），I4 顺带核（fact_theme_flow_daily 不在 07 的八个 `.TI` 缺口内，但属「数据未完成→方法日步写原因」的那类夜）。不影响本单断言——`run_method_flywheel` 只在守卫通过后跑，守卫失败夜写「原因+下一次机会」。
- W7 · **主检出不含 `method_validation.py`**（本单在集成树）：launchd 夜跑的 `WORKSPACE=/Users/a77/finance-workspace-private`（主检出）是旧的，`run_method_flywheel` 目前会对不存在的脚本 rc=2。**I5 的 `--export` plist 与 `run_method_flywheel` 在合一后真正生效**；此前不要宣称"生产日程已启用"。
