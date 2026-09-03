# 弃权率成为一等读数 + 08-27 四臂 38 题的回溯基线（2026-09-03，P1 第一步）

零 LLM。分类器：`intelligence/eval/abstention.py`；接线：`scripts/run_quality_ablation.py`（逐题
`abstained` / `abstain_reason` / `abstain_detector`，聚合 `abstention` 与 `abstention_by_arm`，报告
「均分 X / 弃权率 Y%」并列）；基线脚本：`scripts/offline_abstain_baseline.py`；数字：
`docs/verification/2026-09-03-abstain-rate-baseline-offline.json`。钉子 `intelligence/tests/test_abstention.py`
21 条（含 4 条用 08-27 真实答案原文校准的用例），变异两组见红（分类器永不弃权 → 12 红；弃权率折进边际贡献 → 1 红）。

**结论一句**：分类器独立地从 08-27 产物里复现了 spec §1.1 的头条——组件臂未见题 **10/10 弃权**；四臂对六道
期望拒答题**全部兑现**；生产臂（当时 8792 = `40fd5a84`）在该答的 32 题里弃权 8 道，其中 **7 道是判官不可用
时的扣稿话术（`judge_blocked`）**，模型自己弃的只有 1 道（D6）。弃权率与均分并列，一个都不折进分数。

## 为什么要做

spec §3.2：现有评测读的是通过率与五维 rubric 分，**一个 100% 弃权的系统零错误、分数不难看、产品价值为零**——
组件臂 11.1 分背后正是 10/10 弃权。改动三条：逐题记 `abstained` + `abstain_reason`（枚举
`evidence_gap / unsupported / judge_blocked / deadline_exhausted / other`）；聚合出 `abstain_rate` 与均分并列、
**不合并进总分**；报告模板两个数一起念。先拿基线，再谈 P0/P2/P3 有没有把它压下去。

## 判定怎么做 [代码路径]

- **结构层优先**：episode 终局事件（`finish.status` / `stop_reason` / `rejection_code`、证据数）、gate receipt
  的 `judge_status`、探针收据 `answer_stream.terminal_phase`（`evidence_gap_fallback` 是弃权信号；旧收据把 dict
  存成 repr 也认）。判官扣稿 = 弃权，哪怕正文写得再好——读者拿不到。
- **文本层兜底**（`classify_text`）：**首句定性**。首句含拒答标记即弃权、不看总长（react D8 783 字的诚实拒答
  首句就露底）；正文中段一句「未能取到 07-17 数据」不算（8792 D5 首句给了研判，「无法给出」只在第二段）；
  短答案（< 80 字）全文数标记，**无标记就是答了**（8792 C4 的 62 字快答、组件臂 A8 的 51 字都是回答）；
  < 12 字或空 = 弃权。标记表 = 08-27 机判脚本 `REFUSAL_MARKERS` + 同批产物里实际出现的句式（「结论未知」
  「不能给出」「没法回答」「无法评估」「未找到」「不可用」「为 0 行」）+ 判官扣稿固定话术（「未完成独立复核」
  「暂不对外引用」→ `judge_blocked`）。
- **弃权 ≠ 错**：`abstain_rate()` 按 `expect_refusal` 分开念——`abstain_rate`（全部）与
  `abstain_rate_where_answer_expected`（该答的题里弃了多少）、`refusals_honored`（该拒的兑现了多少）。冻结集
  六道期望拒答：C1 / C2 / C3 / C8 / D7 / D8。
- **消融壳**：ask 超时 = 没交卷 = `deadline_exhausted`，弃权率要数它（分数口径继续不送评）；旧收据没有字段按正文
  现算，`rejudge_quality_ablation.py` 复用同一份 `aggregate_components` 自动带上。

## 读数 [实测，08-27 四臂产物，38 题]

| 臂 | 弃权 / 全部 | **不该弃而弃**（该答的 32 题） | 该拒兑现（6 题） | 见过题 A/B/C 不该弃（24） | 未见题 D 不该弃（8） | 原因 |
|---|---:|---:|---:|---:|---:|---|
| react-claude（只跑了 12 题） | 2/12 | **0/10** | 2/2 | 0/2 | 0/8 | evidence_gap 2（皆该拒） |
| 组件臂 | 14/38 | **8/32** | 6/6 | 0/24 | **8/8** | other 10（「结论未知」）、evidence_gap 4 |
| 8792（`40fd5a84`） | 14/38 | **8/32** | 6/6 | 6/24 | 2/8 | **judge_blocked 7**、evidence_gap 7 |
| 8796（sidecar） | 10/38 | **4/32** | 6/6 | 3/24 | 1/8 | evidence_gap 6、deadline 1、unsupported 1、judge_blocked 1、other 1 |

怎么念：

- **spec §1.1 的读数复现**：组件臂见过题 0 弃权、未见题 10/10（8 道该答的全弃 + 2 道该拒的兑现），完全分离。
- **8792 的 8 道「不该弃而弃」里 7 道是 `judge_blocked`**（A7 / A10 / B1 / B4 / B8 / C7 / D2，全是「本次未完成
  独立复核（复核服务不可用）」）——08-27 正是 Grok 判官额度耗尽那天（08-28 台账）。模型自己弃的只有 D6
  （高标梯队「没法回答…查不到」）。**判官不可用把生产臂该答题的弃权率从 3%（1/32）抬到 25%（8/32）**，这是
  P2（判官判据）之外另一条独立的弃权来源，与 §3.2 说的「弃权是二值量、比连续分更抖」相互印证：一个基础设施事件
  能翻整批读数。
- react 的「85.7 均通过率」背面：它答了所有该答的题，也兑现了跑到的两道期望拒答（D7 / D8）。
- 8796 的 4 道里 B2 是 `repair_deadline_exhausted`、B4 是 `unsupported`（「现有证据不足…未完成核验绑定」）——
  这两类才是 P0 / P2 能动的弃权；`judge_blocked` 与 `evidence_gap`（库里真没有）不是。

## 对 P1 后续的含义

- 「改前」基线有了，但它是 **08-27 的四臂**（8792 当时 `40fd5a84`，判官不可用）。要量 P0 的效果得在含 #537 的
  快照上（现役 `ccf9343162d0`）**经会话链**重跑 38 题——注意 `run_quality_ablation.py` 走的是 `intelligence.cli ask`
  的 legacy 管线，**不经过 ContinuousAgentEpisode**（episode 链只在 `/api/conversations`，`ASK_CONTINUOUS_RUNTIME`
  在 `api/app.py:186` 读）；P0a / P0b / P2 / P3 改的都是 episode 链，所以 38 题重跑要用会话链探针
  （`smoke_workbench_self_use.py` 或 `finance-base-ab` 配方），产物用 `classify_episode` 判。消融壳里的弃权率量的是
  legacy 路径各组件的弃权，两条路径的数字不能混。
- **方差纪律**（§3.2 第三段）：二值量的门要从「两臂本该完全相同的样本」现算，本单只报数不判 Δ；`aggregate_components`
  的 `abstention` 块明写「不进 Δ、门另算」。
- 判官可用性要当协变量记：重跑那天先看 `judge_unavailable_count`，否则 `judge_blocked` 会再把读数翻一次。

## 没做

没烧配额（38 题会话链重跑 ≈ 38 × 70–110s、每题 3 万 + 输入 token，待用户点头）。没改任何生产行为、判官判据、
预算。没给弃权率 Δ 定显著性门。8792 / 8796 各有 12 道题没有 `continuous-episode.json`（走了 legacy 快路径），按探针
收据 `terminal_phase` + 正文判（JSON 逐行 `has_episode=false` 可查）。
