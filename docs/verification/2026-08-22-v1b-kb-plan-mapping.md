# V1b：KB 通道计划引导落入 evidence_plan（2026-08-22）

> 规格：`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md` §V1
> 前置：`docs/verification/2026-08-22-v2-gap-proof-v1a-kb-plan.md`（题形提案 + 三档耗时）
> 证据：`docs/verification/2026-08-21-inputside-kb-dark-asset.md`（R-11 五案例）
> 台账：`R-20260821-13`（judged pending；live 等 V6 分臂结束由验收方回填，本单不得 confirmed）
> 分支：`feat/v1b-kb-plan-mapping` @ worktree `/Users/a77/fwp-wt-v1b-kb-mapping`

## 0. 一句话

已批题形的 `resolve_evidence_plan` 现在会带一条 **optional** `kb_search` requirement；`dated_market_review` / `market_review` 只在段级谓词命中时追加。不另建预算降档，检索耗时仍走既有 `select_mode_for_remaining`（<15s→BM25）。

## 1. 映射清单

入口：`intelligence/services/evidence_capabilities.py` 的 `should_guide_kb_channel` → `_with_kb_channel_guidance`。表达方式沿用已有 `EvidenceRequirement.mandatory`（`False` = optional），不重构 planner。

| 题形 | 落法 | 计划里的 KB |
|---|---|---|
| `theme_analysis` | 整题 | optional `kb_search` |
| `theme_track` | 整题 | optional `kb_search` |
| `stock_deep_dive` | 整题（补 requirement） | optional `kb_search` |
| `market_cause` | 整题 optional | optional `kb_search`；`episode_factory._episode_evidence_plan` 覆盖因果计划后把 resolve 里的 KB 行接回去（映射仍只在一处） |
| `valuation_estimate` | 整题 optional | optional `kb_search`（factory 估值锚点路径会保留 resolve 的非 `market_data` 行） |
| `dated_market_review` | **段级 overlay** | 仅当 `has_sector_theme_attribution_intent(query)` |
| `market_review` | 同上，**同一函数** | 不得各写一份 |

requirement 形状：`EvidenceRequirement("KB", "kb_search", False, "current", …)`。不把 `kb_search` 放进 `mandatory_capabilities`，避免修复轮追逐（与 R-05 公司主体题降级同一纪律）。

预算：本单不改 `kb_rag.select_mode_for_remaining`、不改 15s 阈值、不在映射函数里读 `remaining_seconds`。钉：`test_kb_mapping_does_not_invent_a_second_budget_ladder`。

## 2. 谓词定义（可修订）

**一句话**：问句同时出现层名词（`板块|题材|行业`）和归因动词（`为什么|原因|驱动|归因`）才算「板块/题材归因意向」。

调研后选这条，是路由层已有信号里**最保守**的一种：

| 候选 | 为何没选 |
|---|---|
| 单独「板块/题材」 | 「今天板块表现如何」会误开，整题复盘被 KB 挤槽 |
| `query_understanding._theme_aliases()` 题材别名命中 | 别名表误伤面大；`resolve_evidence_plan` 只有 query 文本，没有 TaskFrame.subject |
| 整份 `is_market_cause_query`（动词 ∧ 涨跌 ∧ 主语锚） | 过窄：复盘问「板块为什么这样」不一定带涨跌词 |
| 本谓词 = `_CAUSE_LAYER_TOKEN_RE` ∧ `_CAUSE_VERB_RE` | **采用**。词表与 `query_understanding` 对齐，不另发明 |

可修订点（改函数 + 改 `test_market_review_alias_shares_dated_overlay`，不要在两处各写词表）：

- 扩动词：如「催化」「带动」（V1a 提案提过催化，本单为保守未收）
- 收紧：再要求涨跌事件词（向 `is_market_cause_query` 靠）
- 放宽：加入题材别名，但必须先论证误伤（别名里有常见词）

命中 / 不命中夹具：

| 问句 | 谓词 | 复盘题形 plan 含 KB |
|---|---|---|
| `复盘7月16日半导体板块为什么走强` | True | 是 |
| `复盘7月16日的A股市场` | False | 否 |
| `今天板块表现如何` | False | 否 |

## 3. 非目标（本单不做）

- `general_finance_qa` 兜底不加 KB。R-11 减肥药 live 落到这里；正确修法是把发酵问句路由回 `theme_analysis`，另立路由债。夹具：同问句在兜底题形无 KB、在 `theme_analysis` 有 KB。
- `comparison` / `fact_check` / `kol_review` / `trade_advice` / `comparison_analog` 不动（V1a 提案未批或 overlay 未批）。
- `_repair` 不动。
- W2 satisfiability / `CHAIN_MAPPING_KB_GAP` / adapter 不动。
- 不改任何检索实现（`kb_rag.retrieve` / hybrid / BM25 / dense）与预算参数。
- 不绕过 evidence_plan 在 prompt 里硬塞「请调 kb_search」。
- 本单离线，不打 live 探针，不碰 8792/8803。

## 4. 离线验证读数

解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。cwd：本 worktree。基线 `c62beeab`。

### 红（实现前，仅新夹具）

收据：`~/.finance-runtime/test-receipts/20260821T182058Z-c62beeab.json`

`11 failed, 10 passed`。失败是「应含 KB requirement」与谓词函数不存在；10 绿是范围外题形本来就没有 KB。

### 绿（实现后）

收据：`~/.finance-runtime/test-receipts/20260821T182139Z-c62beeab.json`

邻域 `test_kb_plan_mapping` + `test_evidence_capabilities` + `test_episode_factory` + `test_mandatory_satisfiability` + `test_episode_seam_ladder`：**161 passed**。

还原后同夹具再跑：`20260821T182159Z-c62beeab.json`，`63 passed`（mapping + evidence_capabilities）。

### 变异（映射恒空）

把 `should_guide_kb_channel` 改成恒 `return False`（题形→KB 映射清空）。

收据：`~/.finance-runtime/test-receipts/20260821T182146Z-c62beeab.json`

`10 failed, 11 passed`。整题纳入、overlay 命中支、R-11 钙钛矿/皇氏、factory `market_cause` 接回全部红。范围外题形与「不另建降档」钉仍绿。还原后复绿见上。

### 全量

见交付回复里的最新全量收据（须 `dirty=false`、tip 与分支 HEAD 一致）。`ruff check .` 须 0。

## 5. R-11 五案例重放（离线 plan，不跑 live）

| 案例 | 问句 | 题形 | plan 含 KB |
|---|---|---|---|
| 钙钛矿 | `钙钛矿电池产业链怎么拆` | `theme_analysis` | ✅ optional |
| CXO | `CXO概念这波怎么看` | `theme_analysis` | ✅ optional |
| 皇氏 | 既有 R-05 走势复盘长问句 | `stock_deep_dive` | ✅ optional |
| 减肥药 | `减肥药这波从月初发酵到现在怎么看` | live=`general_finance_qa` | ❌（路由债） |
| 减肥药（应落） | 同上 | `theme_analysis` | ✅ optional |

钙钛矿题形 plan 含 KB requirement：满足 spec §V1 重放句。live 调用与 chain_mapping 有据可写仍待部署后验收。

## 6. live 验收待办（执行方不得自行标 confirmed）

等 V6 分臂结束、本分支合入并切生产后，由验收方：

1. 探针用户 `probe-v1b-<mmdd>`（字段是 `user`）。
2. 同题形（`theme_analysis` / `theme_track` / `stock_deep_dive`）trace 出现 `kb_search` 或 `evidence_search` 调用。
3. KB 有证据题材（钙钛矿）的 `chain_mapping` 格有据可写（R-11 预测①逐字）。
4. 对照：减肥药若仍路由到 `general_finance_qa`，本单不承诺会出现 KB 调用——那是路由债，不是映射漏。

## 7. 原理与选型（给下一手）

**evidence_plan 是什么**：合同上「这一题打算取哪些证据」的清单。`mandatory=True` 的缺了会记缺口、修复轮会追；`False` 只是引导模型「可以调」，预算不够可以不调。

**为什么 optional 而不是 mandatory**：V1a 量过 KB 检索——dense p50 5.9s / p95 7.6s，bm25 暖机 p50≈9.8 / p95≈13.3、全样本 p95 45s，hybrid p50 17.5s。成稿轮残值 median 13s。mandatory KB 会在残值不够时制造结构性不可满足（W2 刚修过的债）。optional + 既有 `<15s→BM25` 分档，是「引导但不逼死」。

**替代方案**：

| 方案 | 好处 | 代价 |
|---|---|---|
| 本单：requirement + optional | 计划可见、不改检索、不改 satisfiability | 模型仍可能不调（live 才验调用率） |
| prompt 硬塞「请调 kb_search」 | 实现快 | spec 禁区；预算账绕过 plan |
| 整题 mandatory KB | 调用率会上去 | 残值 13s 下必现缺证追逐 |
| 给 `general_finance_qa` 也加 | 盖住减肥药 miss-route | 所有没认出的题多一次 10–35s 检索 |

可迁移点：任何「授权了但计划不引导 → 模型零调用」的暗资产，都是「capability floor ≠ evidence_plan.requirements」；修的是计划，不是再扩授权。
