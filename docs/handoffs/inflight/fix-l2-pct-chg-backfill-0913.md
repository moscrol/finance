# fix/l2-pct-chg-backfill-0913：E3 旧窗口 pct_change 回填（复审已通过+门禁齐，待用户授权合并）

## 结论（每步可追溯）
- 三轮 QC 三个 P2 已返修：① 库不存在开写前 FileNotFoundError（exit 2，不落空库）+
  零目标行记 noop；② 台账四字段 target_rows/distinct_codes/matched_rows/null_rows，
  行级与代码级分母拆开；③ 缺失代码 >20 条写明细文件（L2_REPAIR_DETAIL_DIR，
  默认 ~/.finance-runtime/db-repair/l2-pct-chg-missing/），台账带 full=<路径>。
- 复审（docs/qc-l2-e2-merge-0913@3af70caa 同轮）：代码层通过；合并门禁现已补齐（见下）。
- 生产第三遍（修复版工具，幂等）：值零变更（0 不符/0 反号/仅 688797@2026-06-24 两行
  登记 NULL），台账 message 换为正确分母口径；对账：capital_flow 9424 = 9423 匹配 +
  1 登记 NULL，quant 3293 = 3292 + 1；原始 9085 是去重 (date,code) 对，339 为跨榜重复行。
- 仍不是完整重算：逐笔同源、资金流各列无缺陷、重算反而有害（删不掉旧阈值行/
  污染历史评分明细）。688797@2026-06-24 两行 NULL 是正确结果。

## 机器证据（全部可核）
- Python 全量：`~/.finance-runtime/test-receipts/20260913T114331Z-3458a7f0.json`
  9554 passed/0 failed/77 skipped/2 xfailed，exit 0，dirty=false，py 3.12.13，
  dep_fp 3328bed61f3e21ea。Ruff 干净；registry 一致。
- 前端+E2E：`~/.finance-runtime/test-receipts/20260913T133923Z-3458a7f0-frontend-e2e.json`
  lint / typecheck / 单测 76/76 / build / playwright 15/15 全绿（同一棵树、同一候选）。
- 回填：备份 `~/.finance-runtime/db-repair/l2-pct-chg-20260913/pct_change_pre_repair_backup.csv`
  （12,717 行，sha256 1ef1c668…）；`repair-receipt.json`（原始）+
  `repair-receipt-supplement.json`（第三遍对账，不改写原始）。

## 交接文件丢失说明
本分支早期的两份交接提交（9776416f / ebb9a713）在分支重写中丢失，未进入当前链
（734e6613→ecc404da→54248fa3→3458a7f0）。本文件为重建版，内容覆盖原两份并更新到最新。

## 合并边界
- 运行时服务不加载该工具（一次性的），合 main 无需重新部署。
- 生产台账 message 已反映修复后口径；详细审计轨迹在收据。
- 待用户授权后：合 main（--no-ff）→ 推送。E2 设计分支（feat/e2-material-contract-design）
  独立评审，不与本分支互相阻塞。
