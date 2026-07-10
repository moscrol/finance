# Fidelity / Replay v1：10 日 Pilot 初审

> 执行日期：2026-07-10  
> 范围：2026-03-02 ～ 2026-07-03  
> 数据：a77 Mac 主 DuckDB + knowledge-base-private Git 历史  
> 状态：自动化与 PIT 可用性初审完成；人工金标准尚未裁定。

## 结论

目前还不能声称 Agent 已经做到“现状描述贴切、历史回溯准确”：

1. 现有 forecast ledger 的 12 份答卷全部是 schema 1.0，共抽出 221 条可审查声明；
2. schema 1.0 没有 `evidence_catalog`，因此证据覆盖率基线为 0%，数字一致率和截止违规率无法逐项核验；
3. 进一步检查 `updated_at` 后，10 个历史截面全部缺少完整、可证明的 DuckDB PIT 快照；
4. 其中 5 个早期截面还没有当时的知识库 commit；全部严格标为 `pending`，没有用今天的数据或 wiki 回填；
5. 真实 DuckDB 自测已证明：结构化数字声明可以逐项核对，并能同时检查证据覆盖和 cutoff。

这轮结果证明的是“评测器开始能区分可核验、不可核验与违规”，不是证明 Agent 已经准确。

## 10 日分层样本

| as-of | T+1 | 市场阶段 | 状态 | 主要缺口 |
|---|---|---|---|---|
| 2026-03-06 | 2026-03-09 | 横盘 | pending | market/sector/stock 均在 D0 后写入；无 as-of wiki commit |
| 2026-03-25 | 2026-03-26 | 反弹 | pending | market/sector/stock 均在 D0 后写入；无 as-of wiki commit |
| 2026-03-26 | 2026-03-27 | 探底 | pending | market/sector/stock 均在 D0 后写入；无 as-of wiki commit |
| 2026-04-23 | 2026-04-24 | 主升 | pending | market/sector/stock 均在 D0 后写入；无 as-of wiki commit |
| 2026-05-11 | 2026-05-12 | 主升 | pending | market/sector/stock 均在 D0 后写入；无 as-of wiki commit |
| 2026-06-03 | 2026-06-04 | 顶部横盘 | pending | market/sector 在 D0 后写入；stock 仅 4008/5206 行可证明 |
| 2026-06-04 | 2026-06-05 | 顶部横盘阶段 | pending | sector 在 D0 后写入；stock 仅 4008/5206 行可证明 |
| 2026-06-17 | 2026-06-18 | 反弹阶段 | pending | market/sector 在 D0 后写入；stock 仅 4009/5206 行可证明 |
| 2026-06-25 | 2026-06-26 | 探底阶段 | pending | sector 224 行全部在 D0 后更新 |
| 2026-07-02 | 2026-07-03 | 底部横盘阶段 | pending | sector 224 行全部在 D0 后更新 |

`trade_date=历史日期` 不等于“当时已经可用”。本轮把 `updated_at < as_of + 1 day`
作为最小 PIT 证明；当前主库更接近 latest-state store，历史行可能在后续补齐或覆盖，因此不能直接承担
严格历史重放。没有 as-of wiki commit 时，知识层同样不可证明。

## 现状忠实度基线

| 指标 | 结果 | 解释 |
|---|---:|---|
| 数字一致率 | pending | schema 1.0 没有可定位到表/字段/实体/日期的证据 |
| 证据覆盖率 | 0 / 221 | 现有答卷声明没有有效 `evidence_catalog` 引用 |
| 截止违规率 | pending | 没有逐证据 `source_time`，无法证明未越界 |
| 事实/推断混淆率 | pending 221 | 尚未完成金标准类型裁定 |
| 实体归类准确率 | pending 221 | 尚未完成人工题材/角色裁定 |
| 事件时间线准确率 | pending 221 | 尚未完成人工历史顺序裁定 |
| 因果证据绑定率 | pending 221 | 尚未完成人工因果链裁定 |

## PIT 隔离检查

- `pilot` 命令只生成 `input.snapshot.json`；
- 输入快照递归扫描日期，拒绝任何 `max_embedded_date > as_of`；
- T+1/T+3 结果只能由独立的 `outcomes` 命令生成；
- 本轮没有生成 input 或 outcome 文件，因为 10 个 case 都没有通过完整 PIT 门槛；
- wiki 只记录 `rev-list --before=<as_of>` 得到的不可变 commit。

## 下一道人审门

本轮不能继续生成历史答卷，否则会把后补数据冒充当时信息。下一步必须先建立真正的快照来源：

1. 从现在起每日在 D0 收盘后冻结 DuckDB 输入快照和 wiki commit；
2. 只对有不可变原始材料或历史提交证明的旧日期开放回放；
3. 答卷拆成 observation / inference / prediction，并逐条绑定证据；
4. 人工裁定实体归类、事件顺序、因果证据和事实/推断类型；
5. 答卷冻结后再生成 T+1/T+3 outcome。

在金标准完成前，所有结果继续保持 `decision_eligible=false`。
