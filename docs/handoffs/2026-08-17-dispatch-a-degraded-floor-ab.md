# T-A 派单：兜底章法对照窗（**领域 Harness**）

- 日期：2026-08-17 ｜ 索引：`2026-08-17-dispatch-00-index.md`
- **层：领域 Harness**（spec §2.2「金融问题应该怎样研究」含金融输出契约）
- **dsh 接缝：无。** 按 §14 反推，「降级后金融回答必须保留什么」是**领域真源**，
  挂不上通用接缝——dsh 本来就不判「这数对不对」。挂不上是正常的，不是我们没拆好。
- 信源路由：**领域层 → knevo**（`agent-memory/10_knowledge/knevo-*.md`）＋本仓实测。
  **不要去 ai-agent-book 找**——它是通用 agent 著作。

## 0. 一句话

兜底章法在生产上是**关着的**。任务是**出对照数据**，不是掀开关。

## 1. 现场（自包含）

- `intelligence/services/degraded_fallback.py`：`ENV_NAME="ASK_DEGRADED_FALLBACK"`，
  `enabled()` 读 `os.environ.get(ENV_NAME, "off")`——**代码默认 off**。
- `/Users/a77/.local/bin/start-finance-workbench`：**没有这个 env**（也没有 `ASK_LONGTAIL_BASELINE`），
  所以生产走代码默认 = 关。
- `skills/finance-degraded-fallback/SKILL.md`：在**运行时快照**里存在（2191 字节）。
  ⚠ 数据仓 `/Users/a77/finance-workspace-private` 当前分支上**没有**这个文件——
  查它必须查运行时快照 `/Users/a77/.finance-runtime/finance-workspace-31ee58ce6c45/`，别查数据仓工作树。
- 基准 run：`run_20260817_094617_943922`，产物根
  `/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/<run_id>/`

## 2. 硬约束（docstring 明写，不得绕）

> 两侧共用一个开关，默认 off；**off 时既有输出逐字节不变**。
> **翻默认必须先走对照窗**（同 `ASK_LONGTAIL_BASELINE` 的纪律），不得因本文件默认打开。

**所以本轨的交付物是数据，不是开关。** 没有对照数据就往启动器加
`ASK_DEGRADED_FALLBACK=on` = 违纪。

## 3. 这个开关管两侧（别只测一侧）

1. **prompt 侧** `episode_rule`：把降级章法拼进 episode 指令——模型**还能写**时，
   按七项写有边界的降级回答，而不是被剥成裸边界句。
2. **输出侧** `gap_transparency`：在 `_gap_answer` 的结构性兜底上确定性补齐
   「尝试过什么 / 来源标注」两段——这条路径出现的场合正是 **LLM 已经失败**的场合，
   prompt 注入帮不上，只能由运行时按章法渲染。

两侧的失败场景不同，对照窗要**分别取样**。

## 4. 任务

1. 同题、同 user、`skill_mode=auto`，`ASK_DEGRADED_FALLBACK` on / off 各 N 发
   （N 自定但须说明，且两臂 N 相等）。
2. 比公开答卷是否满足 `degraded_fallback.REQUIRED_ANCHORS` 与「七项」。
3. **必须覆盖两侧**：既要有「模型还能写」的降级样本（测 prompt 侧），
   也要有「LLM 已失败」的空稿样本（测输出侧）。
4. 产出「该不该翻默认」的建议＋数据，**不直接翻**。

## 5. 完成定义

- 对照数据入账本，两臂样本数相等且说明取样口径。
- off 臂输出与当前生产**逐字节一致**（这是 docstring 承诺的，验它就是验对照窗没被污染）。
- 建议行写明：翻默认会改变哪些成因下的用户可见文本。

## 6. 边界

- 不改 `_gap_answer` 与瞬时故障投影的**路径结构**（那是 T-B 的活）。
- 不动预算 / 核验路径 / `_CLAIM_POLICY`。
- 不切 8792。不动 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP` /
  生产档位 / `ASK_TOOL_BATCH_TIMEOUT`（R-20260816-07 绊线）。
- ⚠ 与 T-B 共文件（`degraded_fallback.py`、`episode_semantic_verifier.py`），
  **各开各的分支，不要互相 rebase**，合并前由主 agent 对账。

## 7. 配额与环境

- ⚠ **LLM 是 5 小时滚动上限，约 15 次 canary 跑光。** 对照窗要先算够不够，
  不够就分批并在账本里写明批次。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- ⚠ **在生产实例上做旁路测量会污染它自己的探针**：直调 `kb_rag.retrieve` 加载 BGE-m3 的
  39 秒里，8792 的 `/api/readiness` 会翻成 `not_ready`（`rag_query_protocol` 探测超时）。
  判据：`workers.rag.model_load_count` 没变就说明常驻 worker 没重载，红的是探针不是 worker。
  **别把自己的干扰读成生产缺陷。**
- Gitea PR：`git credential fill` + `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`
- 合 main 必须等用户确认
- ⚠ 不要从 `/Users/a77/finance-workspace-private` 工作树提交（落后 main 293 提交，
  其 `docs/prediction-ledger.md` 相对 main 是 -573/+159 的旧版本）
