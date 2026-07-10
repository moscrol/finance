# Fidelity / Replay v1：10 日 Pilot 初审

> 执行日期：2026-07-10  
> 范围：2026-03-02 ～ 2026-07-03  
> 数据：a77 Mac 主 DuckDB + knowledge-base-private Git 历史  
> 状态：自动化与 PIT 可用性初审完成；人工金标准尚未裁定。

## 结论

目前还不能声称 Agent 已经做到“现状描述贴切、历史回溯准确”：

1. 现有 forecast ledger 的 12 份答卷全部是 schema 1.0，共抽出 221 条可审查声明；
2. schema 1.0 没有 `evidence_catalog`，因此证据覆盖率基线为 0%，数字一致率和截止违规率无法逐项核验；
3. 10 个分层历史截面中，5 个具备 DuckDB 基础快照和 as-of wiki commit，可以进入答题；
4. 另 5 个早期截面没有当时的知识库 commit，严格按规则标为 `pending`，没有用今天的 wiki 回填；
5. 真实 DuckDB 自测已证明：结构化数字声明可以逐项核对，并能同时检查证据覆盖和 cutoff。

这轮结果证明的是“评测器开始能区分可核验、不可核验与违规”，不是证明 Agent 已经准确。

## 10 日分层样本

| as-of | T+1 | 市场阶段 | 状态 | 主要缺口 |
|---|---|---|---|---|
| 2026-03-06 | 2026-03-09 | 横盘 | pending | 无 as-of wiki commit；多张增强表未覆盖 |
| 2026-03-25 | 2026-03-26 | 反弹 | pending | 无 as-of wiki commit；多张增强表未覆盖 |
| 2026-03-26 | 2026-03-27 | 探底 | pending | 无 as-of wiki commit；多张增强表未覆盖 |
| 2026-04-23 | 2026-04-24 | 主升 | pending | 无 as-of wiki commit；theme/stock 主线表未覆盖 |
| 2026-05-11 | 2026-05-12 | 主升 | pending | 无 as-of wiki commit；theme/stock 主线表未覆盖 |
| 2026-06-03 | 2026-06-04 | 顶部横盘 | ready | theme/stock 主线表未覆盖 |
| 2026-06-04 | 2026-06-05 | 顶部横盘阶段 | ready | theme/stock 主线表未覆盖 |
| 2026-06-17 | 2026-06-18 | 反弹阶段 | ready | theme/stock 主线表未覆盖 |
| 2026-06-25 | 2026-06-26 | 探底阶段 | ready | 无 |
| 2026-07-02 | 2026-07-03 | 底部横盘阶段 | ready | sector 主线表未覆盖 |

`optional gap` 不会触发后验补写；它只限制该 case 可回答的问题范围。没有 as-of wiki commit
则整个知识层回放不可证明，必须保留 `pending`。

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
- 本轮未生成 outcome 文件，因为 5 个 ready case 的答卷尚未冻结；
- wiki 只记录 `rev-list --before=<as_of>` 得到的不可变 commit。

## 下一道人审门

对 5 个 ready case：

1. 只用各自 `input.snapshot.json` 与对应 wiki commit 生成答卷；
2. 把回答拆成 observation / inference / prediction，并逐条绑定证据；
3. 人工裁定实体归类、事件顺序、因果证据和事实/推断类型；
4. 答卷冻结后再生成 T+1/T+3 outcome，完成历史重放评分。

在金标准完成前，所有结果继续保持 `decision_eligible=false`。
