# 2026-09-29 名称来源验收：接受「收盘后封存的腾讯报价」（name_source_acceptance）

写完不改；更正走 `record-correction`。

## 用户原话（2026-09-29 约 11:45 CST，Arena Agent 会话）

问题：「是否接受『收盘后封存的腾讯报价』作为新股名称来源（合同 1 / `name_source_acceptance`）？」
用户答：「接受。」

## 接受的范围

- 名称来源 = `tencent:captured-dated-quote`：经 `scripts/audit_dated_quote_capture.py` 验过的封存捕获
  （receipt 覆盖面、逐批 sha256、每条报价时间戳落在**目标交易日 15:00 之后**）。
- 执行件 = `skills/duckdb-backfill/scripts/attach_capture_names.py`（main 已含 `9f5fc05e4` / `5b515777c`）的现有硬约束全部保留：
  只在非 canonical 库（staging）上跑；只填 `source LIKE 'hithink:%'` 且空名的行；逐行钉 close / pre_close / pct_chg / amount；
  收据只新建不覆盖；发布走正式换库链并另取发布授权。
- 这解除 `hithink_recovery_candidate` 的 `name_source_acceptance` blocker，也覆盖 2026-09-26
  `fix-local-backfill-0923-0924` 交接里「待用户拍板」的那一项（09-23/24 那 5 行补名的来源）。

## 不在本次接受范围内

- 用「当前」快照（非目标日收盘后时间戳）给历史日补名——仍不接受。09-29 11:17 查到的 `920201.BJ → 百瑞吉`
  只能用于身份确认，不能作为 09-28 名称证据。
- 放宽 `InvalidStockName` 校验、跳过缺名股票、伪造名称——仍不接受。
- 09-23 决策页合同 1 的「B 过渡 → 目标态 D」口径不变；本条是 B/D 之外补充的一条合规来源。

## 直接影响与后续

1. 09-28：失败 staging 已保全于 `db/incident-20260928/`（sha256 `c1bbbd21…c12395a0`）。能否补名取决于
   09-28 收盘后是否有封存腾讯捕获（项目目录内未找到；`~/.finance-runtime` 待查）。没有就不能用本来源补 09-28。
2. 09-29 起：需在每个交易日 15:00 后采一份全市场腾讯报价并封存，夜跑桥之后、`compute-limit-stats-local` 之前
   对 staging 调用 attach；否则新股（如 920201.BJ）在同花顺兜底路径下仍会被 `InvalidStockName` 拦下。
   接入需改夜跑编排并更新夜跑冻结代码根（当前 `~/.finance-runtime/finance-sync-fe9fdbfd70a6`），另走评审。
