# 2026-09-22 行情恢复：五项字段/分母合同与离线审计

接手 `行情恢复`（blocked）缺的五项：**名称、换手率、历史范围、停牌分母、下游验收**。
本轮只做两件事：把五项从「口头未定」变成**可核验的合同 + 可复跑的离线审计**，以及把两处
下游消费口径改成与合同一致。**没有连网、没有写生产库、没有发布、没有合并**，候选仍固定
`production_ready=false` / `database_writes=false` / `publication_attempted=false`。

## 证据来源（只读封存件，未改动）

| 输入 | 内容 | 校验 |
|---|---|---|
| `tmp/recovery-20260921/tencent-full-scope/`（0921 工作树） | 70 批具名日期盘后行情，5556 个身份 | 逐批 sha256 + receipt 身份集比对（`audit_capture`） |
| `tmp/recovery-20260921/tencent-extra-suspensions.raw` | 全域批次外的 9 个停牌身份 | sha256 `efdd9bd2…5b2dc2`（`input-manifest.json` 内） |
| `tmp/recovery-20260921/sina-scope/*.raw` | 第二供应商**当前**名单 5564 行（70 页） | 汇总为 `tmp/recovery-contracts/sina-comparison.json`，sha256 `8c4b5628…c681b` |
| `resume-candidate/candidate-final.json` | 前序纯构造候选（5553 行 + 12 缺失处置） | 指纹见 `candidate-receipt-final.json` |

审计产物：`tmp/recovery-contracts/metadata-audit.json`（112 398 B，sha256 `abfa67b2…10fdae8`，rc=0）。
`tmp/` 已被 .gitignore，产物不入库；封存原件只读不覆盖。

## 五项合同与支撑证据

### 1. 名称：`dated_provider_display_name_not_legal_name_or_official_status`

**合同**：写进事实表的 `stock_name` 是「**某个具名时刻**的供应商展示名」，必须随 `name_source` +
`name_observed_at` 一起落；它**不是**法定名称，也**不构成** ST / 新股 / 除权的官方状态认定。
做口径判定（ST 排除、新股排除）时只能用**当日**名称，不能用更早或更晚的名单名。

**证据**：380 条两源名称差异 = 6 条纯空格（`万  科Ａ` vs `万 科Ａ`）+ 344 条简称/全称文本差异
（`华电新能` vs `华电新能源集团`）+ **30 条 XD/XR/DR 前缀差异**。关键在于这 30 条**方向相反**：
20 条是对照名单有前缀而 09-21 具名快照没有（9-22 才除息），10 条是 09-21 有而对照没有（除息日已过）。
即除权前缀是**随观察时刻变化的瞬时展示态**，任何「拿另一时刻的名字顶替」都会错。
反过来，ST/新股分类差异 = **0 条**：说明当前这批差异**不影响**下游 ST/新股过滤，但这是**观测结论、不是保证**——
所以合同管的是「必须用当日名」，而不是「两源名称可互换」。

**已修**：`sync_local_sector_members.py` 原先拼接时取 `fupanhui` 身份基线里的名字（可能是几个月前的），
现改为**优先当日行情名**、缺失才回落基线名（`tests/test_sync_local_sector_members.py` 两例锁定）。

### 2. 换手率：`null_not_zero_not_carried_not_inferred`

**合同**：`turnover` 在未绑定**官方流通股本**前保持 `NULL`；供应商给的数字只能进
`observed_turnover_pct`（带源与时刻）。消费方**不得**用 0 顶替 NULL、不得跨日结转、不得用
市值/价格反推后当真值写入。

**证据**：5553 条里 21 条两源换手率差 >0.011pp，最大 **3.74638pp**（不是舍入噪声）。
但 `internal_denominator_mismatches = 0`：**两边各自都内部自洽**——腾讯报价 = 成交股数 ÷ 字段 72，
新浪报价 = 成交股数 ÷（nmc×10⁴ ÷ 现价）。差异全部出在**分母口径/更新时点**：
21 条中腾讯分母更大 16 条、新浪更大 5 条（如 `002282.SZ` 509 536 318 vs 483 311 104）。
两个数都"算得对"，所以**算术一致性不能用来选真值**——这正是 `official_denominator_verified=false`
必须留在产物里的原因。东财 snapshot 的 f8 是候选官方口径，mootdx/hithink 路径不提供该列。

### 3. 历史范围：显式范围 ≠ 官方历史名册

**合同**：5565 是**声明核验范围**（5556 全域批次 + 9 条停牌原件），
`official_historical_universe_verified=false` 固定写死在产物里。

**证据（双向反例，这是本轮最硬的一条）**：
- `689009.SH` 在 09-21 有具名日期 bar，却**不在**第二供应商当前名单里 → 当前名单**漏**真实交易身份；
- `000016.SZ` 等 9 只在当前名单里，却**不在**全域批次中，要靠额外停牌原件才覆盖 → 单批采集**漏**停牌身份。

两个方向都有反例，所以「拿当前名单当历史名册」和「拿一次采集当全集」都被证伪；
补官方名册仍是**未关的门**（需交易所/官方名册来源，Chrome CDP 授权弹窗仍卡着，未重试）。

### 4. 停牌分母：身份分母，不是「取到值的行数」

**合同**：范围 = 有 bar 的身份 ⊎ 有具名日期证据的**不可交易身份**（严格划分，不许用容差缩小）；
停牌股**留在分母里**、**不造平盘 bar**、**不计入涨跌家数**。

**证据/口径**：`partition` 给出 declared 5565 = observed 5553 + nontrading 12，
`observed_bar_fraction=0.99784`，`disposition_coverage_fraction=1.0`（**处置覆盖率 ≠ bar 覆盖率**，
不能互相顶替）；涨跌家数 4536/936/81，停牌 12 单列为 `nontrading_not_flat`。

**已修**：`compute_local_stats.compute_limit_stats_local` 新增**可选** `recovery_members` /
`recovery_nontrading`。给了就用**冻结身份数**当涨停占比分母（`denominator_basis=frozen_identity`），
不给则行为与日更完全不变。原先的风险是：`sync_local_sector_members` 硬约束 2 会把当日无值成员
（停牌/退市）直接剔除，分母随之变小、涨停占比被抬高。测试锁的是 2/4=50% 而不是 2/3≈66.7%。
恢复路径**不借用**日更的缺额容差：未解释的成员缺失、成员多出、隐藏板块、给停牌股造 bar，
四类都在 **DELETE/写入之前**拒绝（`ValueError`），已落的行不被动。

### 5. 下游验收：门没关，改由产物显式列出

`remaining_gates` 固定输出 5 项：`official_historical_universe`、`adjustment_completeness`、
`official_turnover_denominator_if_required`、`downstream_same_day_cross_day_l2`、
`write_and_publish_authorization`。
下游读法（`fact_theme_limit_heat_daily.limit_up_count/total_count` →
`finance_query.limit_up_ratio/total_count`）没有改字段语义，只是让分母口径可被上面的合同解释。
same-day / cross-day / L2 三门最近仍 `rc=2`，**未复跑**。

## 代码与测试

| 文件 | 性质 |
|---|---|
| `market_feature_store/recovery_coverage.py`（新） | 纯函数：`partition_scope` / `market_breadth` / `sector_coverage`；无网络/文件/DB |
| `scripts/audit_recovery_metadata.py`（新） | 离线审计 `assess_metadata` + CLI；输出只写新文件（`open("x")`），失败 rc=2 |
| `market_feature_store/sync/compute_local_stats.py` | 新增可选恢复参数与 `denominator_basis`；默认路径不变 |
| `market_feature_store/sync/sync_local_sector_members.py` | 拼接优先当日具名名称 |
| `tests/test_recovery_coverage.py` / `test_audit_recovery_metadata.py`（新）+ 两个既有测试文件 | 反例为主：分区不得缩小、停牌不得算平盘、算术自洽不得当真值、纯函数不做 IO |

**变异验证**（4 处刻意改坏，均被测试抓到）：忽略冻结分母 → 1 failed；去掉「停牌股不得有 bar」前置拒绝 → 1 failed；
名称改回优先旧基线 → 1 failed；把精确分区放宽成子集 → 4 failed。
全仓：`2003 passed, 62 skipped`（7m08s）；Ruff 全绿。

## 复现命令

```bash
cd /Users/a77/fwp-wt-market-recovery-contracts-0922
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
SEAL=/Users/a77/fwp-wt-market-recovery-0921/tmp/recovery-20260921
$PY tmp/build_comparison_rows.py "$SEAL/sina-scope" tmp/recovery-contracts/sina-comparison.json
$PY -m scripts.audit_recovery_metadata \
  --capture-dir "$SEAL/tencent-full-scope" \
  --candidate "$SEAL/resume-candidate/candidate-final.json" \
  --comparison-json tmp/recovery-contracts/sina-comparison.json \
  --extra-raw "$SEAL/tencent-extra-suspensions.raw:efdd9bd2f1d3b8fc2fa0d755eb36b763da8985cd70fb9329cd38746f605b2dc2" \
  --trade-date 2026-09-21 --json tmp/recovery-contracts/metadata-audit.json
```

## 未验证 / 边界

- 官方历史上市名册、全量除权完备性、官方流通股本口径**仍未拿到**；审计产物里三个
  `*_verified` 标志固定为 false，不得被下游当成已核验。
- 第二供应商名单是**当前**名单（`comparison_has_target_date=false`），只能做差异对照，不能当 PIT 依据。
- 板块全目录 / 成员 generation / 派生表 / L2 仍未恢复；三门未复跑；全仓测试通过 ≠ 可写库。
- 写库、建 staging、原子换库、发布、合并、部署：**每一步都还需要用户显式授权**，本轮一个都没做。
