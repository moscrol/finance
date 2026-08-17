# 派单索引：2026-08-17 四轨（按层分，不按模块分）

- 日期：2026-08-17
- 尺子：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` §2
  （通用底座 / 领域 Harness 两分）＋ `2026-08-17-followup-angle-composer-design.md` §14（dsh 反推法）
- 账本 SSOT：`docs/prediction-ledger.md`（gitea/main）
- 现场记录：`docs/handoffs/2026-08-17-degraded-floor-and-retrieval-budget.md`（PR #129）

## 0. 分层口令（每轨开工第一件事）

对手上的组件只问一句：**明天若必须做成 dsh 插件，它挂哪条已经写在架构图上的接缝？**

| 结果 | 含义 | 怎么长 |
|---|---|---|
| 挂得上、不用改 loop 图 | 形状能在 dsh 上跑 | Definition + Provider + Consumer；卸掉主循环仍在 |
| 只能塞进某个 tool 的 execute | dsh 只宿主流水线 | 保持 ToolSpec；对错仍由 Evidence / Verifier 判 |
| 找不到接缝、或必须改 agent-loop | 焊死了，或它就是领域真源 | 先拆焊点；真源留 Python 网关 |

⚠ **「能挂上」不等于生产改去跑 dsh。** DuckDB、截止日、绑定还在本仓。这句话只检验边界像不像插件。

## 1. 信源路由（2026-08-17 修正，别走错）

| 层 | 去哪找修法 | 为什么 |
|---|---|---|
| **通用底座** | dsh（量接缝）＋ ai-agent-book / 马书 / 官方文档（讲原理） | `~/harness-reference/INDEX.md` 是入口，先读它再读章节 |
| **领域 Harness** | **knevo**（`agent-memory/10_knowledge/knevo-*.md`）＋ 本仓账本与实测 | **ai-agent-book 是通用 agent 著作，领域的东西很少**；唯一同量纲的领域信源是 knevo（同为金融投研 agent） |

已验证的先例：`degraded_fallback.py` 的 docstring 写明它蒸馏自 knevo 逆向语料的
「降级后必须保留的七项」——这条领域路由已经被走对过一次。

## 2. 四轨

| 轨 | 层 | dsh 接缝 | 可并行 | 状态 |
|---|---|---|---|---|
| [T-A 兜底对照窗](2026-08-17-dispatch-a-degraded-floor-ab.md) | **领域** | 无（内容是领域真源） | ❌ 等 T-B 落地 | **已派**（#131）。执行 = T-B 合入 main 之后；读数贴最终形态，不重跑 |
| [T-B 投影一致性](2026-08-17-dispatch-b-projection-consistency.md) | **通用** | `ctx.sessionProjections` | ✅ | 待派 |
| [T-C 判据对齐](2026-08-17-dispatch-c-criterion-alignment.md) | 验收工具（既非产品通用也非领域） | 无 | ✅ | 待派 |
| [T-D 检索预算](2026-08-17-dispatch-d-retrieval-budget.md) | **通用** | `tools/pre-execute` | ❌ 立案不动手 | 触 R-07 绊线 |

⚠ **T-A 与 T-B 都碰 `degraded_fallback.py` 与 `episode_semantic_verifier.py`。**
2026-08-17 用户再裁：**T-B 落地后才执行 T-A**；T-A 读数直接贴最终形态，**不用重跑**。
旧安排「两轨各开分支、合并前对账」只覆盖 T-B 落地前的文件冲突——T-A 改为落地后只读出口、只贴原文，不再为对照窗另开改代码的分支。

## 3. 一处分层更正（本轮讨论产出）

原始归类把「输出层契约」整个划给领域层。按 §14 反推，**T-B 的缺陷本体是通用的**：

- 「区分基础设施故障与内容不足」不需要懂 A 股 → 通用；
- 那句降级文案是从终局事实（`judge_status` / `stop_reason`）折出用户可见文本 → 就是 `view()`；
- 缺陷是**两条并行投影路径对同一份终局事实给出不一致表达**，违反 dsh session-projection 的「必须同步」。

领域的部分只剩一处：**兜底七项吐什么内容**（假设 × 可验证时点 × 推翻条件、来源标注）。

**后果**：T-B 的修法不是「再加一句领域文案」，而是**把两条投影并成一条、成因当输入参数**。
前者会留下第三条路径，下次再漏。

## 4. 一处 spec 待更正（归 T-D 带）

`2026-08-15-agent-base-dsh-absorption-design.md` §4.1 把「root budget、deadline、**工具批次预算**、
repair cycle」列在**已有能力**，§4.2 五条待补里没有它。而 2026-08-17 实测：工具批次预算把一个
4~5 秒的工具饿死了。**机制存在 ≠ 分配策略对。** §4.1 那行该加限定，或 §4.2 补第 6 条。
