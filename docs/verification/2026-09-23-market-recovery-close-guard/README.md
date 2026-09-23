# 行情恢复：收盘价空壳保护与只读复核

状态：**HOLD**。本轮为作者侧边界复验，不是独立 QC，不是恢复发布验收。

## 身份

- 修复提交：`3abb7a4d320d2ba52e5c3cf35661b877123b17db`。
- 最新组合基线：`bbd53487f4cefdae97eae90f7322394d36e65462`。
- 干净组合预览：`45e752cfaf30929d15acbd0bcab0a667aef0e12e`，tree `3ea686889344ebbaaddeee2b3866bce9bd9a3733`；由 `git merge-tree` 构造，无冲突。两张 PR 的已核对头仍在祖先链中。
- `composition.txt` 记录父提交。新预览已完成验证并移除工作树，Git 对象由本地 `refs/verification/market-recovery-close-20260923` 保留；未推送该引用。
- 旧全仓预览 `d3abd670` 及收据原样保留；其已存在的锁未改动，另保留本地 `refs/verification/market-recovery-full-20260923`。

## 发现与修复

`compute_limit_stats_local(recovery_members=...)` 原先只检查 canonical 行是否存在。即使收盘价为 NULL、NaN、正负无穷、0 或负数，仍报告完整覆盖并改写派生表。

仅在显式恢复路径新增「所有当日消费行的收盘价必须有限且为正」检查；失败发生在四张派生表的 DELETE/INSERT 之前。检查包括板块外但参与全市场计数的股票。保留原有缺行及非交易身份冲突检查，不过滤掉坏行凑覆盖率，不改默认日更、不改冻结分母、不启用恢复 CLI。

这只是收盘价最低有效性约束，不认证历史全字段质量、其他数值字段或并发输入快照。

## 证据

| 文件 | 结论与边界 |
|---|---|
| `change.patch` | 两个正式源码/测试文件的补丁 |
| `red.txt`、`red-receipt.json` | 先加测试、未加保护：24 个 `DID NOT RAISE` 预期失败；23 项被筛去。作者迭代脏树，不是门禁 |
| `green-receipt.json` | 修后六个相关测试文件 158P；作者迭代脏树，不是干净组合门禁 |
| `probe_nullable_bar.py`、`probe-before.json`、`probe-after.json` | 复用本仓夹具的作者探针：六种坏值修前被接纳、覆盖率 1.0；修后逐项拒绝，四张派生表全部保持原样。仅内存 DuckDB，不开生产库 |
| `focused-receipt.json`、`focused-runner.txt`、`focused-exit.txt` | 干净组合 **2639P / 62S / 0F / 0E**，收集2701，658.35秒；runner rc0；整仓 Ruff 通过 |
| `focused-receipt-check.txt` | revision/解释器/依赖/干净状态/收执对账通过，基座漂移0，rc0 |
| `consumption-registry.txt`、`skills-registry.txt`、`skills-parseability.txt` | 消费注册表、技能注册表一致性与61份 frontmatter 解析均通过 |
| `k3-preflight.json`、`k3-request-admissions.jsonl` | 本轮只有一次 K3 最小请求预占，45秒超时（墙钟46.779秒）；没有新独审会话、独立探针、阳性对照或报告 |

正式新增测试为 6 种坏值 × 4 种股票角色：涨停、平盘、仅含 ST 股板块、板块外。每例比较四张派生表全部列，不只比行数。

### 收据不能移签或扩大范围

本轮 `target=tests`，**不含 `intelligence/tests/` 等其他收集路径，不是全仓测试**。

现有校验器把位置目标与过滤旋钮分开检查：`--require-full-scope` 单独仍返回0（`focused-full-scope-only-check.txt`），只说明在给定目标内没有 `-k`/`--ignore` 等收窄；增加仓根 `--require-target` 后返回1（`focused-root-target-check.txt`）。必须同时读 `target` 与 `scope`，不能只凭 rc0 当全仓绿。

旧14798P全仓收据对旧 `d3abd670` 仍通过，基座漂移1（`old-full-receipt-check.txt`）；指定新候选45e752c则被身份门拒绝（`old-full-not-for-new-revision.txt`，rc1）。旧全仓读数和本轮定向读数不拼接。

新组合相对最新 main 的 `intelligence/webapp` 零差异，本补丁前端/E2E不适用。新候选全仓门禁未重跑，任何合入前仍须补齐。

## 生产只读回读

`readback.json` 由既有 `docs/verification/2026-09-22-market-recovery/readback_before.py` 生成。`readback_values.py` 为本次日期窗口的复现附件，复用 `preview_stock_calculation` 解释缺行；运行需把固定候选放在 `PYTHONPATH`，只以 `duckdb.connect(..., read_only=True)` 打开指定数据库，无初始化/DDL/DML/外呼。

`readback-values-explained.json` 的读取时刻为2026-09-23 06:35 UTC；读取前后库文件 inode/大小/mtime 一致，此记录不是整个数据库字节哈希证明。

- 09-21/09-22 canonical 个股各5551行；这两天均没有发现无效收盘价，也没有 NULL 前收、涨幅、金额或名称；换手率各5551条 NULL 与现有桥政策一致。
- `fact_market_daily` 仍缺09-21；相关本地派生表仍停09-18。不能沿用旧决策页「个股已齐」作严格范围结论，也不能把封存候选5553条当生产行数。
- 09-18 canonical 5553行、无无效收盘价，但有1条 NULL 成交额；未将其改判成停牌或合成平盘。

| 日期 | 同花顺有行而 canonical 缺行的身份 | 现有只读预演的原因 |
|---|---|---|
| 09-21 | 600301.SH、600825.SH | 缺前一计划交易日 bar |
| 09-22 | 300803.SZ | 暂不支持的非现金公司行动 |
| 09-22 | 301686.SZ、920229.BJ | 缺前一计划交易日 bar |
| 09-18（参照日） | 302132.SZ | 单股预演能算通，但官方身份/供应商全集仍未验证，不构成补写授权 |

这些结果不证明股票停牌，不取代此前53只除权/送转问题全集，也不与000703.SZ、002255.SZ两家公司现金分红金额分歧混同。

## 后续边界

五问、三合同、5553/5565范围、53只处置仍等用户明确选择。K3只记录本次预检未过，不推断整个供应商永久不可用；沿用原模型，不因超时换模型。旧独审 runner 固定在d3abd670，恢复后须针对含3abb7a4d3及届时最新 main 的新候选重新封存输入、从 explore 开始，不能拿旧身份签新代码。

本轮未合并、推送、部署、创建数据库 staging、换库或写生产；历史09-22已授权换库记录不抹掉。测试进程已退出，新门禁临时目录自动清理。工具沉淀为正式保护及24个回归用例；复现附件只服务这次取证，不新增通用工具或平行注册表。
