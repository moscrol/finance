# T-A 派单：兜底章法对照窗（**领域 Harness**）

- 日期：2026-08-17 ｜ 索引：`2026-08-17-dispatch-00-index.md`
- **层：领域 Harness**（spec §2.2「金融问题应该怎样研究」含金融输出契约）
- **dsh 接缝：无。** 按 §14 反推，「降级后金融回答必须保留什么」是**领域真源**，
  挂不上通用接缝——dsh 本来就不判「这数对不对」。挂不上是正常的，不是我们没拆好。
- 信源路由：**领域层 → knevo**（`agent-memory/10_knowledge/knevo-*.md`）＋本仓实测。
  **不要去 ai-agent-book 找**——它是通用 agent 著作。
- **状态：已执行。** 收据 `#135` `docs/verification/2026-08-17-degraded-floor-ab-readings.md`。
  用户裁定（2026-08-17）：**T-B 落地后派 T-A；读数直接贴最终形态，不用重跑。**
  执行树是 T-B #134 tip `67a067b9`（main 尚未含该 merge；用户口头授权「tb已经完成」）。
  **建议不翻默认。**

## 0. 一句话

兜底章法在生产上是**关着的**。本轨交付**贴出来的终稿原文**，不是掀开关，也不是新开 live 对照窗。

## 0.1 本轨词表（领域真源，先对齐再动手）

| 钦定词 | 是什么 | 勿用 |
|---|---|---|
| **落地** | T-B 合入 `gitea/main`。不要求切 8792。 | 「8792 已切」「生产已开」 |
| **最终形态** | T-B 把 3 条旁路并进同一条 `view()` 之后，再叠本开关，用户实际读到的整段公开文本 | 「会变成什么样」的转述、改前答卷、半截投影 |
| **读数** | 收据里贴上的就是终稿原文 | 摘要、评分、印象 |
| **对照窗（本轨）** | 同一份冻结终局事实，开关 off / on 各渲一段最终形态，原文并排贴上 | live on/off 重跑、新 canary、同题再发 N 次 |
| **不用重跑** | 不开新 live / canary，不烧 15 次配额。输入 = 已有冻结 run 的终局事实 + T-B 落地代码 | 「再跑一发确认」 |

旧稿写「同题 on/off 各 N 发」——那是长尾对照窗的章法，**本轨作废**。
本轨要量的是 T-B 并路之后的组合形态；T-B 落地前跑出来的是旧三出口，贴上去是错锚。

## 1. 现场（自包含）

- `intelligence/services/degraded_fallback.py`：`ENV_NAME="ASK_DEGRADED_FALLBACK"`，
  `enabled()` 读 `os.environ.get(ENV_NAME, "off")`——**代码默认 off**。
- `/Users/a77/.local/bin/start-finance-workbench`：**没有这个 env**（也没有 `ASK_LONGTAIL_BASELINE`），
  所以生产走代码默认 = 关。
- `skills/finance-degraded-fallback/SKILL.md`：在**运行时快照**里存在（2191 字节）。
  ⚠ 数据仓 `/Users/a77/finance-workspace-private` 当前分支上**没有**这个文件——
  查它必须查运行时快照 `/Users/a77/.finance-runtime/finance-workspace-31ee58ce6c45/`，别查数据仓工作树。
- 冻结 run：`run_20260817_094617_943922`，产物根
  `/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/<run_id>/`
- 该 run 的用户可见答卷（T-B **落地前**的旧形态，只作输入事实，**不得当 off 臂读数**）：

  > 结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成；以下仅为候选草稿，不视为最终核验结论：

## 2. 硬约束（docstring 明写，不得绕）

> 两侧共用一个开关，默认 off；**off 时既有输出逐字节不变**。
> **翻默认必须先走对照窗**（同 `ASK_LONGTAIL_BASELINE` 的纪律），不得因本文件默认打开。

**所以本轨的交付物是贴出来的读数，不是开关。** 没有对照读数就往启动器加
`ASK_DEGRADED_FALLBACK=on` = 违纪。

「off 时既有输出」的锚是 **T-B 落地树上、开关关着的 `view()` 出口**，
不是落地前那份旧答卷。T-B 改成因行是本职；本轨验的是**开关没在 off 时再改一笔**。

## 3. 这个开关管两侧（别只贴一侧）

1. **prompt 侧** `episode_rule`：把降级章法拼进 episode 指令——模型**还能写**时，
   按七项写有边界的降级回答，而不是被剥成裸边界句。
2. **输出侧** `gap_transparency`：挂在 T-B 落地后的那一条 `view()` 上，
   在结构性兜底上确定性补齐「尝试过什么 / 来源标注」两段。
   这条路径出现的场合正是 **LLM 已经失败**的场合，prompt 注入帮不上。

两侧都贴最终形态，不找模型再写。

## 4. 任务（T-B 落地后执行）

开工第一句：`git merge-base --is-ancestor <T-B-merge-sha> gitea/main` 必须成立。
T-B 还在 PR / 本地分支上 → **停**，不要用未合入的树冒充落地。

然后只做这件事：

1. 从冻结 run 抽出终局事实（`stop_reason` / `judge_status` / `usage` / 结构性 evidence
   的 `source`+`source_date` / 四个 output 槽 fulfilled）。draft 与证据 title/detail
   一个字不进——红线与 `_gap_answer` 相同。
2. 在 **T-B 已合入的树**上，同一份事实喂 `view()`：
   - **off 臂**：开关关。贴整段公开文本。
   - **on 臂**：开关开。贴整段公开文本。
3. 三类成因各做一遍（T-B 的完成定义已经要这三类夹具）：
   `transient_verifier_outage` / `evidence_gap` / `model_unavailable`。
   缺哪类夹具就向 T-B PR 取，**不新造 live 去补样本**。
4. prompt 侧：贴落地树上 `episode_rule` 打开时注入的 `【降级回答章法】` 全文
   （确定性文本，不是模型写出来的答卷）。
5. 对照 `REQUIRED_ANCHORS` 与七项：on 臂输出侧 + prompt 块各勾一张表。
6. 写出「该不该翻默认」——只根据这些贴出来的原文，写清翻默认会改哪些成因下的用户可见文本。

## 5. 完成定义

收据里能看到：

- T-B 合入 SHA（`gitea/main` 上的 merge commit）。
- 三类成因 × 开关 off/on = **六段公开文本原文**（输出侧）。
- prompt 块原文一段。
- 七项勾表（on 臂）。
- off 臂与 T-B 落地树上开关关着的夹具**逐字节一致**（验开关没污染）。
- 建议行：翻默认会改变哪些成因下的用户可见文本；**不直接翻**。

## 6. 边界

- T-B 未合入 `gitea/main` → 本轨不执行。
- 不开新 live / canary，不切 8792，不烧 LLM 配额。
- 不改 `_gap_answer` 与投影的**路径结构**（那是 T-B 的活；落地后只读它的出口）。
- 不动预算 / 核验路径 / `_CLAIM_POLICY`。
- 不动 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP` /
  生产档位 / `ASK_TOOL_BATCH_TIMEOUT`（R-20260816-07 绊线）。
- ⚠ 与 T-B 共文件。T-B 落地前**不要**为了本轨另开改代码的分支。
  本轨 PR 只含收据 / 账本读数，不含开关默认值。

## 7. 收据

已填：#135 `docs/verification/2026-08-17-degraded-floor-ab-readings.md`。
建议：**不翻默认。**

## 8. 环境

- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- ⚠ **在生产实例上做旁路测量会污染它自己的探针**：直调 `kb_rag.retrieve` 加载 BGE-m3 的
  39 秒里，8792 的 `/api/readiness` 会翻成 `not_ready`。本轨不重跑，这条只防手滑。
- Gitea PR：`git credential fill` + `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`
- 合 main 必须等用户确认
- ⚠ 不要从 `/Users/a77/finance-workspace-private` 工作树提交（落后 main 293 提交，
  其 `docs/prediction-ledger.md` 相对 main 是 -573/+159 的旧版本）
