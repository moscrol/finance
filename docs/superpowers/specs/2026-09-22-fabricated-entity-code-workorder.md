# 2026-09-22 模型自造实体代码（`899050.BK`）工单（#80）

> 来源：#70 `2026-09-22-research-empty-delivery-gate-pr-workorder.md` §目标 4 之三；同单登记 #70 非目标里的诊断漏报（`evidence_claim_findings` 对 `endpoint_not_path` 类零发现）。现场 `run_20260922_191550_067475`，冻结夹具见 `intelligence/tests/fixtures/live_products/run_20260922_191550_067475/`。
> 前置：#70 合入。

## 问题

1. **自造实体代码**：冻结 `events[24].payload.arguments` 是 `entity_codes=["899050.BK"]`；`sample: 0` 是原件行号，并非样本总数。修前未知码与已知无区间行情都能返回全 NULL 的计算行，finance_query 则返回普通空集；缺少身份检查让模型把错码当成缺行情。该代码没有进入本次公开答案，但进入了「历史特征缺失」的 gap。
2. **诊断边界**：人工审读记录的 `endpoint_not_path` 另留 #75 复核。当前源码不存在原占位描述中的 `evidence_claim_findings` 接点；路径与终点收益的关系按 #78 的窗口/指标/期限证据判断。本单不改判官。

## 已实施合同（2026-09-27）

- 共用 `intelligence/services/entity_code_presence.py`；`HistoryQuery.run` 在已有只读事务内、计算前检查 `entity_codes`。`FinanceQuery.run` 在已有连接与截止时限内检查 `filters` 的 `sector_code/stock_code eq/in`，没有新增 `entity_codes` 参数；`contains`、排除筛选和代码后缀保持原语义。
- 存在性正证据复用真实查询编译器，保留各数据集的观察日期、采集日期与 information cutoff 语义，只放开观察窗下界及非身份筛选；不把截止日当天的下午记录排除。published 历史名单、可见 legacy/历史事实与有日期维表可以证明存在，不读取 candidate 作身份正证据。只有覆盖请求日的完整 published 目录才能支撑板块否定；旧日目录、缺失工作日/周末目录、无时点维表均不能被冒用成当日全集。
- 三种结果：已知代码继续查询（区间缺行情仍如实为空/NULL）；本地可核验板块目录缺席回 `unknown_entity_code` + `fabricated_entity`；目录无法核实回 `entity_catalog_unavailable`，不标虚构。混合请求整体拒绝并保留已知/未知/不可验证的精确集合，不悄悄删掉未知项继续算。
- 库内没有通用 `dim_stock` 或完整上市名册。股票 canonical 历史事实、已发布成员及同花顺历史记录只提供存在的正证据；缺席返回不可验证。`bridge_hithink_stock_daily.resolve_universe` 也明确只是当日供应商 bar 范围，不可冒作含停牌股的上市全集。同花顺独立板块目录不能被 canonical published 缺席证伪。
- Episode 工具诊断与 telemetry 保留结构化结果；正常结束、终局恢复、修复轮结束均保留上述两类 gap。身份错误不铸造成市场 evidence，不修改公开稿或完成状态规则。不做相似名推荐、实体消歧或后缀猜测。

## 验收

- [x] 冻结夹具请求在两个真实查询入口返回 `unknown_entity_code`，注册工具与无模型 Episode 循环中 `fabricated_entity` 传至最终 gap。
- [x] 真实库只读逐日期验证 published 全集：2026-07-27～2026-09-24，42 日、16,926 日期×代码、403 个不同代码，误拦 0；文件 inode/size/mtime 不变。结果：`~/.finance-runtime/reviews/8792-readiness-20260927/entity-presence-production-audit.json`。
- [x] 合成真实 schema 覆盖已知缺行情、混合代码、candidate 隔离、可见/被遮蔽 legacy、历史换码、缺失/不完整/无日期目录、股票非闭集、contains、deadline/取消；旧空区间测试改为已证身份、区间无行，保留空结果断言。
- [ ] `endpoint_not_path` 漏报登记在 #75 独立 QC 的复核清单里，有人认领后再开单。
- [ ] 分支级四叶与部署验收由 8792 总任务执行，本单定向结果不代替整仓门禁。只提交 pathspec；不在子任务 push/merge/deploy。

## 独立复审修正

`86360db6220d` 修复初审的三项根因（日期类型、观察/采集双时钟、旧目录负证据）。原14探针保持不改全部通过，新增47项边界与178项相关回归通过。生产42日/16,926组合/403码独立只读重扫零误拦，三日期入口结果与原基线一致；原坏码继续拒绝。规格/质量报告：`~/.finance-runtime/reviews/8792-readiness-20260927/entity-temporal-{spec,quality}-review.md`。初审FAIL原件保留。
