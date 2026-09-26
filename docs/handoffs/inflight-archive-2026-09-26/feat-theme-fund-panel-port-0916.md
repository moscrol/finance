# feat/theme-fund-panel-port-0916 · 题材资金面板搬进主干

## 这个分支做什么
把主检出树里的题材资金面板（东财主力净额补 `local:stitch` 成分行 `fund_flow_1d/5d`，按板块篮子聚合 `fact_theme_flow_daily`，river 三件按口径分组）从 `salvage/main-tree-20260916` 搬到主干。生产库已有四列与 09-11 / 09-15 数据（某 session 手动 `sync-fund-flow --direct`），代码从未进仓。原作者未知，本单是搬运 + 审读。全景见 `docs/handoffs/2026-09-16-main-tree-salvage-port.md`（在 L2 单分支上）。

## 决策与被否方案
- river.py 聚合以主干为底（DECIMAL 求和、`sector_recorded_at_sql("v")`）叠加 `v.source` 分组与 `n_with_fund` / 否取树版：树版基于 09-08 的 `with_ledger` 签名，主干已改。
- river_window 资金维按 (日, source) 分组且保留 `knowledge_cutoff` 过滤，`flow_upd` 取该日各口径最晚记录时刻 / 否丢掉截止过滤：那是主干 PIT 契约。
- `theme_net_flow` 退出比较（`SUSPENDED_FEATURES`）沿用作者设计 / 否恢复进签名：作者实测新口径进基准后两簇并成一簇，按口径标准化未定前宁缺。
- `test_river_recorded_at` 期望仍是主干的 08-27，只改 ref 认 `":agg:<口径>"` / 否树版 08-20：那是旧记录时刻语义。
- 契约测试假连接多给一列 source / 否改查询兼容三列：假连接就是在描述查询形状。
- `check_unread_fields.py` ALLOWED 加 `sock` / 否改代码：`http.client` 内部读它，是协议属性。

## 当前状态
已提交 28c11b99，已推 gitea，**PR #772**（http://127.0.0.1:3300/a77/finance-workspace-private/pulls/772）等用户审；`merge-tree` 对 main 干净，与 L2 单互相干净。全量：ruff 通过，pytest 11163 passed / 0 failed / 81 skipped / 2 xfailed，收据 `~/.finance-runtime/test-receipts/20260916T131231Z-28c11b99.json`（dirty=false）。

## 已验证
定向 144 通过 17 跳过（river 系列 / 契约 / 新模块两份测试 / consumption_registry / dataset 注册审计）；pre-commit 11 道全过；`schema.sql` 从零建库四列 + 留痕表 + Polymarket 表都在；`sync-fund-flow --help` 解析正常。

## 未验证 / 已知边界
- 没对生产库跑 `sync-fund-flow`（会外呼东财并写库；默认拒绝直写）。
- `sync-fund-flow` 未接进 daily-full / 夜跑，与树里一致；接线是另一件事。
- `theme-flow-akshare-fallback`（09-10 未合）改同一文件 `sync_fupanhui_theme_flow_daily.py` 做 AKShare 兜底，后合者 rebase。
- 前端 / e2e 叶未跑（未改 webapp）。

## 下一步
用户审 PR → 合入。随后可议：是否把 `sync-fund-flow` 编排进 daily-full staging；`theme_net_flow` 按口径标准化后解除 SUSPENDED。

## 踩过的坑
作者的测试文件夹带一条依赖 `scripts/moneyflow/process_l2_archive` 的测试，已迁到 L2 单；「字段契约」门禁把 stdlib 协议属性当成写了没人读。
