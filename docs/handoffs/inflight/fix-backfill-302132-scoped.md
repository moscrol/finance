# 在途交接：fix/backfill-302132-scoped（302132 历史回填执行实现，第六轮交审）

## 状态（2026-09-14 深夜）
- **第六轮：1 P1 + 2 P2 全修**。tip `00d64e37`（代码）。验收脚本：oracle 源与 `parallel_source_md5` 重算改读基线（`prod.`）；`fact_stock_daily_hithink`/`fact_stock_adjustment_hithink` 整表禁止变更；收据递归深 schema（格式/成员/有限性/子报告 `ok is True`/跨字段一致）；parquet 三向**逐轮** + 两轮授权 spec 深比较（无白名单）；数据段异常归 `data_checks_error` 结构化 FAIL rc=2。
- 干净重演练：run11=`3925f59c0281`、run12=`9b2b60f7278c`；验收 v6 **49/49 PASS**（`dryrun-acceptance-v6.json`；12 份旧收据逐份哈希核验）。
- 单测 89/89（+63：E2E 必绿 + 52 收据逐字段变异 + 5 库层变异 + 3 绑定专项，坏产物全必红）；全量 pytest **9,706/0/77**（收据 `20260914T080259Z-00d64e37.json`，dirty=false）；ruff 全仓过。
- 审查探针 `--expect-fixed` 两模式包装器 rc=0（证据 `round6-fixcheck-*-summary.json`）。
- **未写生产、未合并、未 push**。生产授权前提见交审文档末节。

## 关键背景
- 冻结纪律升级：`receipts-manifest-20260914-v6.json` 冻结时落盘完整 sha256 清单（12 旧收据+历史验收 JSON+run9/10 备份收据+post-run10 库 `03f50c9f…`）；post-run10 状态存 CoW 快照 `fake-prod.duckdb.post-run10-snapshot`。
- 教训（六轮审查原话，可迁移）：公式独立还不够，**验收输入也必须独立**；schema 校验要递归到成员类型与成功终态；逐轮绑定不能靠「另一轮已绑」传递。
- 旧收据分层：`receipts-run5-run6/`、`receipts-run7-run8/`、`receipts-run9-run10/`。
- 合同链：prep-review → execution-review → 三轮（证据绑定）→ 四轮（验收链）→ 五轮（异常路径+角色）→ 六轮（oracle 输入独立+深 schema+跨轮绑定）。QC 分支 docs/qc-backfill-302132-5b0cd87e。
- 磁盘 ~70Gi。演练库已恢复至 pre-run9 基线内容（sha `76a32fac…`）并完成 run11/12。

## 下一步
1. 代码复审（第七轮）→ 合 main（须用户确认）。
2. 生产执行授权后：干净检出跑 `repair-backfill-302132 --parquet <冻结 parquet>`；当场验收：`--production <执行收据 backup 路径> --clone <canonical> --expected-production-sha256 <收据 backup sha> --expected-old-receipt …`（v6 形态，旧收据链 12 份起）。
3. 事项 3（并跑表补齐）：授权后先交端点×日期×额外表清单。
