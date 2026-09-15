# fix/8792-integrate-routefix-tradingday：8792 版本对齐 + T2/T3 复验（已完结 → QC 收口在 fix/8792-qc-closeout-0913）

## 状态
本分支工作已于 2026-09-13 凌晨完结并合入 gitea/main（`5fb13a8c`）。同日下午独立质检
判「部分通过」，**收口工作转移到 `fix/8792-qc-closeout-0913`**：
- QC 报告：`docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/QC-2026-09-13.md`
- 更正后复验文档：同目录 `RESULTS-2026-09-13.md`（初版四处断言已更正）
- 决策快照更正附录：`docs/handoffs/2026-09-13-8792-integrate-deploy-recheck.md` 文末

## 本文旧断言中已作废的（以 QC 为准）
- 「弃权/失败同族（TimeoutError/502）= 自审不稳、50s 预算」→ QC E4：三次失败 =
  写手 75s 超时 / HTTP 502 / 材料合同拒判；判官预算 75s；unavailable=结构预检退出。
- 「L2 三段 complete 非空」→ 行数真、值口径错（QC E3：pct_change 末笔/首笔冒充
  当日涨幅）；已修+重算 12 天全绿（97eedb2a）。
- 「T2/T3 实质答卷」→ 补 QC E2 边界：真实行情注入虚构题、T3 Q8 备忘录未交付、
  编号题组被拆分吞并；材料边界修复立设计任务。

## 原始记录（保留溯源）
把材料路由修复（长度闸）+ 探针 ID 配对 + 交易日判定（#52）合进主干，验收后部署 8792
（快照 `2ee664fae9c4`），固定参赛版本，完成 T2→T3 揭盲后复验、补 09-11 L2 top100/quant。
决策表与过程细节见 `docs/handoffs/2026-09-13-8792-integrate-deploy-recheck.md`（含更正附录）。
