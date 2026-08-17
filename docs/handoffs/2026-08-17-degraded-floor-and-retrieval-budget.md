# handoff: 降级下限没兜住 + 检索预算分配（四轨可并行）

- 日期：2026-08-17
- 前序：`docs/handoffs/2026-08-17-r22-r23-carry-draft.md`（T1 已完成，见 PR #128）
- 账本 SSOT：`docs/prediction-ledger.md`（gitea/main）
- 起因：用户裁定「**就算降级，也要按兜底章法来，这是下限**」。本轮实测该下限两处没兜住。

## 0. 一句话

R-20260817-01 的 T1 已同形 hit（PR #128，仍 pending）。本交接是**新开的四条**：
兜底下限（A）、瞬时故障归因（B）、判据口径洞（C）、检索预算（D）。
A/B/C 互不依赖可并行；**D 是立案不动手**（触 R-07 绊线）。

## 1. 现场（2026-08-17 09:46 实测）

| 项 | 值 |
|---|---|
| gitea/main | `cd09d48d`（#127 交接） |
| 8792 | `31ee58ce` / dirty=false / `code_matches_repo=true` / `workers.active=0` |
| 基准 run | `run_20260817_094617_943922`（156.6s，T1 同形 hit） |
| 产物根 | `/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/<run_id>/` |

该 run 的用户可见答卷顶着一句：

> 结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成；以下仅为候选草稿，不视为最终核验结论：

**触发它的不是答案有问题，是语义裁判 provider 超时**（`judge_status=unavailable`）。
同一 run 的 `structural_verifier` 四个 output 槽全部 `fulfilled`，
`factual_grounding` / `task_coverage` 均 fulfilled。

---

## 轨 A · 兜底下限：开关默认 off，生产没开

**实测**：

- `intelligence/services/degraded_fallback.py` — `ENV_NAME="ASK_DEGRADED_FALLBACK"`，
  `enabled()` 读 `os.environ.get(ENV_NAME, "off")`，**代码默认 off**。
- `/Users/a77/.local/bin/start-finance-workbench` **没有这个 env**（也没有 `ASK_LONGTAIL_BASELINE`），
  所以生产走代码默认 = 关。
- `skills/finance-degraded-fallback/SKILL.md` 在运行时快照里**存在**（2191 字节）。
  ⚠ 数据仓 `/Users/a77/finance-workspace-private` 当前在 `docs/dsh-absorption-spec` 分支上**没有**这个文件——
  查它必须查运行时快照，别查数据仓工作树。

**约束（docstring 明写，不得绕）**：

> 两侧共用一个开关，默认 off；off 时既有输出逐字节不变。
> **翻默认必须先走对照窗**（同 `ASK_LONGTAIL_BASELINE` 的纪律），不得因本文件默认打开。

**任务**：出对照窗数据，不是直接掀开关。同题同 user、on/off 各 N 发，
比公开答卷是否满足 `REQUIRED_ANCHORS` 与「七项」。带数据回来再谈翻默认。

**不要做**：不要在没有对照数据的情况下往启动器加 `ASK_DEGRADED_FALLBACK=on`。

---

## 轨 B · 瞬时故障投影绕开了兜底（下限真正漏的那处）

**实测**：`gap_opening` / `gap_transparency` 只挂在
`episode_semantic_verifier.py` 的 `_gap_answer` / `_generic_gap_answer`
（约 538 / 554 / 578 行）。而瞬时故障投影（约 1155–1190 行，
docstring `"Keep a safe candidate visible when a transient judge outage occurs."`）
自己拼一句硬编码 `notice` 后 `return`，**不经过 `_gap_answer`**。

即：**开关开了也管不到这条路径。** 轨 A 与轨 B 是两个独立缺口，别当成一个。

**这条路径的决策本身是对的**——裁判挂了时露出候选稿，比整份扣掉强，
docstring 也写明 `"This is deliberately not a semantic pass"`。**错的是归因与措辞**：
把「复核服务挂了」说成「这只是候选草稿，不视为最终核验结论」，
用户读到的是「答案不可信」，真相是「答案没人复核过」。

**任务**：让这条路径也落到兜底下限，并把两类原因分开表达——

| 成因 | 现在说什么 | 应该说什么（方向，措辞待定） |
|---|---|---|
| 复核服务瞬时故障 | 「仅为候选草稿，不视为最终核验结论」 | 「本次未完成独立复核（复核服务超时）；内容与证据绑定已通过校验」 |
| 真的证据不足 | 同上（同一句） | 「证据不足」＋兜底七项 |

**先例**：本文件 docstring 已有同形判例——
「成因行（『模型服务不可用』）不跟这个开关：`repair_model_unavailable` 或
`usage.llm_calls==0` 时首句必须说模型不可用，不能说『现有证据不足』。
**那是成因谎，不是章法开关。**」本轨要修的是同一类成因谎，照这条判例办。

**边界**：只改「降级之后怎么说话」，不改预算、不改核验路径、不改 `_CLAIM_POLICY`。

---

## 轨 C · 严判据与生效解析器不同口径

**实测**：同 run 的 repair 轮（seq19）`model_turn.content` **`json.loads` 失败**——
`draft` 字符串里 `"AI算力"`、`"7月中旬即为高点…"` 的双引号未转义。
但生效解析器把它捞了出来，`outcome.draft`(612 字符) 取自 seq19，
而非 seq14 那份**合法**的 732 字符稿。

**危害**：`docs/handoffs/2026-08-17-r22-r23-carry-draft.md` §3 写的判定标准是
「某条 `model_turn.content` 能 `json.loads` 出 `draft`」。照它判 repair 轮，
**会把明明出了稿的 run 记成空稿**。R-20260817-01 这类结转类预测全靠这个判据结案。

**任务**：判据与生效解析器对齐——要么判据放宽到与解析器同口径并写明，
要么生成侧把 draft 正确转义。**两者选一，不要两边各改一半。**

**注意**：本轮 T1 的 hit 结论只依赖 seq14+seq16（都过严判据），**不受本轨影响**。

---

## 轨 D · 检索预算分配（⚠ 立案不动手）

**实测**（同 run 的 `tool_error`）：

```
kb_search    batch_grant_asked=30.0  stage_timeout_granted=11.955  queued_ms=2.2  → tool_timeout
news_search  同一批                                                              → tool_budget_exhausted
finalization reason=retrieval_deadline_closed
```

`kb_rag` 本体实测：同进程冷调 **39.06s**，之后 **4.25s / 5.10s**（热态）。
8792 的常驻 worker 已在启动期 prewarm（`prewarm_latency_ms=38516`、
`lifecycle=startup_prewarm`、`model_load_count=1`），**冷启动不在请求路径里**。

所以这不是「检索慢」，是**一个 4~5 秒的工具排在 12 秒窗口的第四位**。

**已排除的两条路，别再走**：

1. **不是串行。** `episode_tool_batch.py` 用 `ThreadPoolExecutor` 同批并发提交
   （注释：「一个批次里的工具是并发提交的，**但共享一个 deadline**」）。
2. **subagent 化不解这题。** 按 ai-agent-book ch10 总判据「有没有新信息」，
   把同一批工具搬进子 Agent 没有新信息。knevo 之所以能靠 sub-agent 缓解，
   机理是**独立 `bg_task_id` 后台任务、不从父轮次窗口扣时间**（生命周期隔离），
   不是并行。且 knevo 是**分档**的：轻档主线程快答、
   中档主线程深检索（4–8 轮，**明确不派单**）、重档才派单——
   本 run 四工具一批正落在「中档＝不派单」。
   继承同一条 episode deadline 的子 Agent 是纯亏（多付 spawn ＋ 交接成本）。

**本窗不许动**：`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` /
`_REPAIR_SECONDS_CAP` / 生产档位 / `ASK_TOOL_BATCH_TIMEOUT`（R-20260816-07 绊线）。
本轨只记账，动手要用户另拍。

---

## 2. 并行安排

| 轨 | 可并行 | 依赖 | 产物 |
|---|---|---|---|
| A 对照窗 | ✅ | 无 | on/off 对照数据 + 是否翻默认的建议 |
| B 瞬时故障归因 | ✅ | 无（与 A 同文件但不同函数，注意冲突） | PR：投影落到兜底下限 + 成因分列 |
| C 判据对齐 | ✅ | 无 | PR 或账本修订 |
| D 预算 | ❌ | 用户另拍 | 仅账本立案 |

⚠ A 与 B 都碰 `degraded_fallback.py` / `episode_semantic_verifier.py`，
**分支要各开各的，合并前对一次**。

## 3. 共同边界

- 不切 8792；文档 tip 不追切。切的话：bootout → `ln -sfn` 新快照 → bootstrap，
  切后查 ready（`ready` 字段在 payload 里叫 `status`）。
- 杀进程只用 `ps -p`，不用 `pkill -f`。
- 跑测试用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，
  宿主 `python3` 缺依赖。
- Gitea PR 用 `git credential fill` + `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`；
  `gh` 打的是 github.com，403。
- 合 main 必须等用户确认。
- ⚠ **在生产实例上做旁路测量会污染它自己的探针**：本轮直调 `kb_rag.retrieve`
  加载 BGE-m3 的 39 秒里，8792 的 `/api/readiness` 翻成 `not_ready`
  （`rag_query_protocol` 探测超时）。判据：`workers.rag.model_load_count` 没变
  就说明常驻 worker 没重载，红的是探针不是 worker。别把自己的干扰读成生产缺陷。
