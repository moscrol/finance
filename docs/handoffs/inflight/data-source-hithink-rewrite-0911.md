# data-source/hithink-rewrite-0911 · 09-11 主表修复（同花顺换源）

## 这个分支做什么

东财快照 2026-09-11 的 `fact_stock_daily` 用同花顺官方 dump 重建。方案/证据在
`~/.finance-runtime/db-repair/hithink-20260911/`（repair-plan.md、dryrun-report.json）；
QC 完整报告 `~/.finance-runtime/reviews/hithink-cd7f6fa9-20260913/review.md`，快照在
codex/qc-hithink-cd7f6fa9 分支 `docs/handoffs/2026-09-13-hithink-cd7f6fa9-qc.md`。

## 决策与被否方案

- 走 `run_daily_full_staged` child_argv 缝 + write_path 闸门 staging 换库；否直写生产。
- pct_chg 全链 DECIMAL 半进；否浮点 round（.xx5 边界错 0.01，5 行实测）。
- 302132.SZ=东财漏收非新股（dump 连续 10 根 bar），pre_close=dump 09-10 close 64.35；
  688801.SH 才按新股保留发行价口径。
- 北交所 3 只（920045/920161/920375）量额双差原因未核实，整行保留。

## 当前状态

- cd7f6fa9 已提交：修复模块 + CLI `repair-stock-daily-hithink` + 9 测试 + 干跑报告。
  **生产库未改。QC 结论：不能换库**，被下节 5 项阻断。
- QC 独立验证：27 条定向测试过、隔离克隆完整父进程换库成功、302132/18 除息/保留行
  对账成立。数字以 QC 为准：pct_chg 5,530/5,530；amount/volume 5,545/5,546 精确相等
  +1 条白名单漂移（600176 −0.0001 亿）。

## QC 阻断项（全修完才谈换库）

1. 规范 P1：直写闸门漏拦——独立 worktree 下主目录真生产库被识别为普通副本，
   `--child` 可达写入函数（替换写入函数探针实证，未写生产）。
2. P1：下游白名单不接受 hithink，修后重新拼接板块 403→0。
3. P1：派生计划漏 `feature_stock_window`；302132 历史不足窗口，technical 重算实际
   生成 0 行，「补一行」兑不了现。
4. P2：新增票断言缺口——合成现金事件探针下 302132 昨收/涨幅大幅变化仍报成功。
5. P1 前提：缺可验明的换库前旧库备份及恢复步骤（修后干跑副本不能充当）。

## 已验证

- QC：27 条收据 `~/.finance-runtime/test-receipts/20260912T181739Z-cd7f6fa9.json`。
- 施工方 9471 passed/ruff/pre-commit 取自提交前脏树（883e3d36），QC 拒认为
  cd7f6fa9 验收。

## 未验证 / 已知边界

- 换库未执行；`feature_stock_technical_daily`/`fact_market_daily`/并跑表均未动。
- cd7f6fa9 无 clean-tree 全量收据；最终修补 SHA 需重跑。

## 下一步

修 5 项阻断 → 最终 SHA 重取全量收据 → 复审 → 才回到拍板三件事（正式换库 /
technical 09-11 重算 + fact_market_daily 口径声明 / 并跑表按端点日期语义补齐、
快照类不回补历史）。勿因克隆换库成功绕过阻断项，勿扩大历史回填日期。

## 踩过的坑

- 全量收据必须对应 clean tree 的 commit，脏树的绿不算数。
- 「补一行」类承诺先验派生窗口历史是否够，否则重算产出 0 行。
