# 工单 #42：方法晋升认证——同身份、预声明阶段、顶层最终结论、失效开新轮次（OPT-04 第一刀）

> 日期：2026-09-08
> 上游：`2026-09-08-research-foundation-optimization-design.md` **OPT-04**（PR #680；认证规则与五种不得误晋升夹具原文）、§1.3「方法晋升」行的反例；`2026-09-04-methodology-backtest-structured-history-design.md` §5.1 / §7.1 / §7.10（生命周期与三段窗口门）；INDEX #21（`lifecycle.py` 与 `queue` 由 PR #607 落地）。
> 优先级：**P0**——A 阶段「先保护可信声明」里唯一没有在途单的方法线项目；当前代码路径能把三个不同版本各一次成功拼成 `personal_method`。
> 分支：`feat/methodology-promotion-certification`，树 `~/fwp-wt-opt04-promotion-cert`（基线 `gitea/main@f90af450`）。

## 0. 一句话

`lifecycle.derive_state` 只认**同一身份、预先声明阶段、顶层最终结论**的收据链；规则内容改了或被证伪，就从头开新轮次。状态仍从收据推导，不新增第二份 status。

## 1. 现状 [实测 @ `gitea/main` `f90af450`]

| 缺口 | 代码位置 | 后果 |
|---|---|---|
| 跨版本收集 | `lifecycle.py::load_steps` 用 `glob(f"{rule_id}@v*")`，`Step` 不带版本 | v1 / v2 / v3 各一次 supported → 三段链 → `personal_method` |
| 读内部结论 | `Step.verdict = stats.verdict`（`readout` 原始四态） | scan 模式下 BH 校正后的顶层 `verdict` 被忽略；内部 supported、最终 not_distinguishable 仍晋升 |
| 无角色声明 | 收据没有 `stage` 字段；`_advancing_chain` 贪心挑任意 supported 且窗口递进的三份 | 任意历史收据里事后挑三段成功窗口即晋升 |
| 失效不开轮次 | `latest.verdict == refuted` 时判 invalidated，但再来一份 supported 就回到 `len(chain) >= 3` | 失效后一个新成功即复活为 `personal_method` |
| 经验卡门 | `intelligence/cli.py` 经验卡 `--rule-id` 读 `latest_receipt` 顶层 verdict（跨版本最近一份） | 单份 supported 即放行常驻卡；**本单不改**，见 §4 |

## 2. 要做什么

### 2.1 收据加「预声明阶段」

- `receipts.build_receipt(..., declared_stage=None)` 顶层写 `declared_stage ∈ {discovery, validation, holdout} | null`（不叫 `stage`——收据里 `by_market_stage[].stage` 已是大盘阶段）；md 渲染带一行。
- CLI `run` / `scan` 加 `--stage`。不传 = 未声明：这份收据是探索或历史观察，**不作晋升证据**，但 refuted 仍生效（证伪不需要预注册）。

### 2.2 `lifecycle.py` 认证

- `Step` 加 `rule_version / rule_sha256 / label_version / declared_stage / verdict_internal`；`verdict` 改读顶层 `verdict`（最终结论），`stats.verdict` 只进解释文字。
- **身份** = `(rule_version, rule_sha256, label_version)`。`derive_state(rule, steps, *, human_approval, rule_sha256=None)`：规则有 `version` 就只看该版本收据；给了 `rule_sha256` 就只看该内容的收据；其余计入 `history_receipts`。
- **轮次**：按身份变化与 `refuted` 切段，只用最后一段推状态。上一段的成功不带进本段。
- **阶梯**：`discovery → validation → holdout` 逐级取证。每级只认声明为该级的收据；同级出现 ≥2 个不同窗口 = 事后挑窗，卡住并说明；同窗重跑取最新一份（数据修订后以新结论为准，不能挑好的那次）；窗口须整段晚于上一级。
- 五种不得误晋升 + 合法晋升，见 §3。共享层两档仍只能人签（不变）。

### 2.3 `queue`

`cmd_queue` 把规则文件 sha256 传给 `derive_state`；队列行显示轮次号与历史收据数。

## 3. 验收（逐条可打勾）

- [x] 跨版本三成功（v1/v2/v3 各一 supported）→ 不是 `personal_method`（`SameIdentityOnly`，含规则文档无 `version` 的退化路径）
- [x] 顶层 `not_distinguishable`、`stats.verdict = supported`（BH 校正降级）→ 不计 supported，blocked_by 说明「内部原始读数 supported，经多重校正后未通过」（`FinalVerdictWins`）
- [x] 三段过门后 refuted（`invalidated`），再来一份 supported → 不回 `personal_method`；新轮次自己走完三段门可再晋升（`InvalidationOpensANewCycle`）
- [x] 无 `declared_stage` 的三份递进 supported → 不晋升，标为历史观察并给出 `--stage` 重跑指引（`DeclaredStagesOnly`）
- [x] 同一 `validation` 级两个不同窗口（一次 not_distinguishable、一次 supported）→ 卡住，说明事后挑窗；同窗重跑取最新一份
- [x] 同一份 holdout 收据重复投递（两份文件、同内容）→ 状态与 evidence 数不变；`derive_state` 纯函数，两次调用相等（`Idempotence`）
- [x] 同身份、三级声明、窗口递进、顶层 supported → `personal_method`（`Ladder`）
- [x] 既有三条门（窗口递进 / 共享层人签 / refuted 掉档）全部保留通过；新夹具对旧 `lifecycle.py` 实测 17 红（stash 回旧文件跑过）
- [x] `build_receipt(declared_stage=...)` 顶层含 `declared_stage`；不传为 `null` 且 md 注明不作晋升证据；乱写拒绝（`test_receipt_carries_declared_stage`）
- [x] ruff 0；`test_methodology_lifecycle.py` + `test_methodology_backtest.py` 103 passed；`queue` 对真规则目录冒烟通过（本机 `methodology/receipts/` 无规则收据，无存量方法被降档）
- [ ] pre-commit 全过（提交时）

## 4. 非目标 / 红线

- 不改经验卡统计门（`experience_cards.gate_promotion` / `cli.py` 读 `latest_receipt`）：把它接到 lifecycle 认证是产品行为变化（常驻卡将要求三段门），需用户拍板后另开一刀。
- 不做 OPT-05（相关样本、块重采样、尝试账）；`stats.py` / `runner.py` 不动。
- 不引入 `experiment_id` / `validation_cycle_id` 持久化账本；轮次从收据推导。要落账时先登记台账地图。
- 拟合产物身份（`fit_artifact_hash`）当前规则无学习型变换，不适用，留待有学习型特征时随 OPT-09 加。
- 不改 `methodology/refuted/` 证伪库格式。

## 5. 交接要求

`docs/handoffs/inflight/feat-methodology-promotion-certification.md` ≤3K：反例转回归的对应关系、未改经验卡门的原因、真库 `methodology/receipts/` 存量收据全部无 `stage` 的后果（队列会显示为历史观察，需按阶段重跑）。
