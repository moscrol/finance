# T-B 派单：降级投影一致性（**通用底座**）

- 日期：2026-08-17 ｜ 索引：`2026-08-17-dispatch-00-index.md`
- **层：通用底座**（spec §2.1「怎样运行 Agent」含 UI 投影）
- **dsh 接缝：`ctx.sessionProjections`**（framework 驱动、领域计算；可选、不属于 loop 主干；**必须同步**；卸载后客户端当能力缺失）
- 信源路由：**通用层 → dsh 量接缝**。不要去 ai-agent-book 找这条的修法。

## 0. 一句话

同一份终局事实，现在有**两条并行的投影路径**给出不一致的用户可见表达。
把它们并成一条，**成因当输入参数**，不要再加第三条。

## 1. 现场（自包含，不必读别的文件）

基准 run：`run_20260817_094617_943922`
产物根：`/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/<run_id>/`
8792：`31ee58ce` / dirty=false / `code_matches_repo=true`

该 run 交给用户的答卷顶着一句：

> 结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成；以下仅为候选草稿，不视为最终核验结论：

**触发它的不是答案有问题，是语义裁判 provider 超时**（`judge_status=unavailable`）。
同 run 的 `structural_verifier` 四个 output 槽**全部 `fulfilled`**，
`factual_grounding` / `task_coverage` 均 fulfilled。答卷本身 1901 字节，内容是好的。

## 2. 两条路径（这就是缺陷）

> ⚠ **2026-08-17 更正（T-E 静态形状对照的产出，见
> `docs/verification/2026-08-17-dsh-static-shape-audit.md` §3）：旁路不是 1 条，是 3 条。**
> 本节初版只点了瞬时故障投影那一条，**只并掉它，另外两条仍在。**

全仓 `public_answer=` 赋值点共 **16 处**（不含 tests），**全在
`intelligence/services/episode_semantic_verifier.py` 一个文件里**——文件是收敛的，
**出口不收敛**：

| 路径 | 数量 | 有没有兜底章法 |
|---|---|---|
| A 经 `_gap_answer(...)` / `_generic_gap_answer(...)` | **13 处** | ✅ 挂了 `gap_opening` / `gap_transparency`（`degraded_fallback.py` 第 30 行 import） |
| B 自己拼串绕过 | **3 处**：`f"{notice}\n\n{public}"`、`public`、`f"{public}\n{gap}"` | ❌ **全部不经过 A** |

自证命令（改完用它验出口收敛）：

```bash
grep -rn "public_answer=" intelligence/services/*.py intelligence/runtime/*.py | grep -v tests
```

其中 `f"{notice}\n\n{public}"` 那处就是瞬时故障投影
（docstring `"Keep a safe candidate visible when a transient judge outage occurs."`）。
另两处**未逐一分析成因，属本轨范围**。

即：**开关开了也管不到这 3 条。** 这与「开关默认 off」（T-A）是两个独立缺口，别当成一个。

## 3. 这条路径的决策是对的，错的是归因

docstring 自陈 `"This is deliberately not a semantic pass"`——裁判挂了时露出候选稿，
比整份扣掉强。**这个决策保留。** 错在措辞把成因说反了：

| 成因 | 现在说什么 | 应该说什么（方向，措辞待定） |
|---|---|---|
| 复核服务瞬时故障 | 「仅为候选草稿，不视为最终核验结论」 | 「本次未完成独立复核（复核服务超时）；内容与证据绑定已通过校验」 |
| 真的证据不足 | 同上（**同一句**） | 「证据不足」＋兜底七项 |

用户读到的是「答案不可信」，真相是「答案没人复核过」。**基础设施故障被归因到内容质量上。**

## 4. 已有判例，照它办

`degraded_fallback.py` 的 docstring 里有同形先例：

> 成因行（「模型服务不可用」）不跟这个开关：`repair_model_unavailable` 或
> `usage.llm_calls==0`（报告里的 `llm.used=false`）时，`_gap_answer` 首句必须说模型不可用，
> 不能说「现有证据不足」。**那是成因谎，不是章法开关。**

本轨要修的是**同一类成因谎**，按这条判例办：成因不跟开关走。

## 5. 任务

1. 让**全部 3 条**旁路落到同一条投影出口——**并成一条 `view()`，成因作为输入参数**。
   先把另两处（`public`、`f"{public}\n{gap}"`）的成因也判出来，别只修瞬时故障那条。
2. 成因至少分三类：`transient_verifier_outage` / `evidence_gap` / `model_unavailable`（第三类已有判例）。
3. 落到 dsh 接缝的形状：输入是**冻结的终局事实**，输出是整段公开文本，**无 IO、无模型调用、无订阅**。
   LLM 润色不得进这条函数——进了就撕掉「同步一致性」这个切面。

## 6. 完成定义

- 离线夹具：同一份终局事实，三类成因各自产出**不同**的首句；**变异**——把任意两类合并即须转红。
- 三类成因 × 开关 off 的终稿夹具留在测试里，供 T-A 原文引用（T-A 不重跑）。
- 不存在第二条绕过该出口的公开文本路径（用 grep 自证：`public_answer=` 的赋值点全部经过该出口）。
- 现有 `_gap_answer` 路径的输出**逐字节不变**（除非成因分类本身要求改），否则须在 PR 里列出差异。

## 7. 边界

- 只改「降级之后怎么说话」，**不改预算、不改核验路径、不改 `_CLAIM_POLICY`**。
- 不动 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP` / 生产档位 /
  `ASK_TOOL_BATCH_TIMEOUT`（R-20260816-07 绊线）。
- 不切 8792。不碰 `ASK_DEGRADED_FALLBACK` 开关默认值（那是 T-A 的活）。
- ⚠ T-A **等本轨合入 `gitea/main` 再执行**。落地 PR 把三类成因 × 开关 off 的终稿夹具留在测试里，
  让 T-A 只叠 on 臂、原文贴进收据，不重跑 live。
- ⚠ 与 T-A 共文件。T-A 不再为对照窗另开改代码的分支；本轨合入前不必跟 T-A rebase。

## 8. 环境

- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（宿主 `python3` 缺依赖）
- Gitea PR：`git credential fill` + `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`；
  `gh` 打的是 github.com，403
- 合 main 必须等用户确认
- ⚠ 不要从 `/Users/a77/finance-workspace-private` 工作树提交：其分支落后 main 293 个提交，
  工作树内 `docs/prediction-ledger.md` 相对 main 是 -573/+159 的旧版本
