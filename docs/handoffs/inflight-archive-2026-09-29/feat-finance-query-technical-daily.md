# feat/finance-query-technical-daily

## 这个分支做什么

把已入库但语义层够不着的表注册进 `finance_query._DATASETS`，并装棘轮门禁
（schema 每张 fact_/feature_ 要么注册要么写明豁免）。

## 当前状态

树 `/Users/a77/fwp-wt-technical-daily`，PR #396。**第五步已提交、未推。** 合 main 等用户确认。

第五步（三张都走 A）：
- `regulation_pool_daily`：`effective_date` 快照轴，`subset`，不开放涨幅/close
- `regulation_event_daily`：同上；`start`/`end` 只做维度
- `historical_mapping`：`as_of` → 物理列 `source_date`

门禁：**20 注册 + 20 豁免**（另 2 个 VIEW）。`_PUBLIC_DATASETS` 19 → 22。

## 未验证 / 已知边界

- 本步未重跑全仓 pytest（相关 64 + 审计 16 已绿）。
- 从未 live。合 main 未授权。
- `waiting` 库里 0 行；池涨幅是小数，要暴露得先改写入侧。

## 下一步

用户确认后才推 / 合 #396。

## 踩过的坑

- 空表 `fact_top_gainers` 只有 schema：数表名不查行数会注册成永久 0 行。
- 基线要认树：脏分支上量过 `_DATASETS=13`，`gitea/main` 是 16。
- 时间残缺 ≠ 结构子集：sw_l1 近端已 31/31，整表 subset 会改写成个股榜。用 `incomplete_before`。
- **同名不靠换列**：`mapping.source_date` 用别名 `as_of`；选 `similar_date` 当前视，选 `end_date` 整批被滤。
- 用 `LIMIT 5` 的结果当「表只有 5 行」会自己踩上要防的分母疤。

## 已验证（前四步）

- 门禁 + auction/sw_l1/technical 已推在 `b6ba3bc2`。
- 全仓 pytest 此前 6504P / 0F；本步数字待重跑。
