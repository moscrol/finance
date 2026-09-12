# hithink-rewrite-0911：同花顺重建 09-11 日线（QC 阻断中）

## 不能换库（QC 阻断，先读这节）

修复已提交（cd7f6fa9），生产库未动。QC 裁定 5 项阻断，全修完+复审才谈换库：
1. 直写闸门漏拦：独立 worktree 下真生产库被当普通副本，`--child` 可达写入函数（探针实证未写生产）。
2. 下游白名单不接受 hithink，修后重新拼接板块 403→0。
3. 派生计划漏 `feature_stock_window`；302132 历史不足窗口，technical 重算生成 0 行。
4.（P2）新增票断言缺口：合成现金事件下 302132 昨收/涨幅大变仍报成功。
5. 缺可验明的换库前旧库备份与恢复步骤（修后干跑副本不算）。
顺序：修 5 项 → 最终 SHA 重取全量收据 → 复审 → 再议换库/technical 09-11 重算/并跑表补齐。
禁令：勿凭克隆换库成功绕过阻断；勿扩大回填日期范围。

## 这个分支做什么

东财 2026-09-11 `fact_stock_daily` 用同花顺 dump 重建。方案/命令 `~/.finance-runtime/db-repair/hithink-20260911/repair-plan.md`；
QC 报告 `~/.finance-runtime/reviews/hithink-cd7f6fa9-20260913/review.md`（含复跑入口），快照见 QC 分支 codex/qc-hithink-cd7f6fa9。

## 关键口径（改代码前必读）

- 走 staging 原子换库（`run_daily_full_staged` child_argv 缝 + write_path 闸门）；否直写生产。
- pct_chg 转回 DECIMAL 后舍入（中间除法为 DOUBLE，非全链 DECIMAL），固定数据结果已独立核验；否浮点 round（.xx5 错 0.01，5 行实测）。
- 302132.SZ=东财漏收非新股（dump 连续 10 根 bar），pre_close=dump 09-10 close 64.35；688801.SH 才按新股。
- 北交所 3 只（920045/920161/920375）量额双差原因未核实，整行保留。

## 对账数字（QC 为准）

- pct_chg 5,530/5,530 精确相等。
- volume 5,546/5,546 精确相等，无漂移。
- amount 5,545/5,546 精确相等，+1 条白名单漂移（600176 −0.0001 亿）。

## 未验证 / 已知边界

- 换库未执行，technical/fact_market_daily/并跑表均未动；cd7f6fa9 无 clean-tree 全量收据，最终 SHA 需重跑。

## 已验证

- QC 27 条定向过、隔离克隆完整父进程换库成功、302132/18 除息/保留行对账成立；收据 `~/.finance-runtime/test-receipts/20260912T181739Z-cd7f6fa9.json`。
- 施工方 9471 passed 取自提交前脏树 883e3d36，QC 拒认为 cd7f6fa9 验收。

## 踩过的坑

- 全量收据必须对应 clean tree 的 commit，脏树的绿不算数。
- 「补一行」承诺先验派生窗口历史够不够，否则重算产出 0 行。
- 交接 ≤3K 字节 ≠ 关键内容能注入；以实跑 scripts/session_facts.sh 为准。
