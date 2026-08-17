# Handoff：DRAM 靶重跑降桶探针——一手证明 superseded 证据进上下文

日期：2026-08-17 晚
roadmap_ref：L1-8792（决策队列 2026-08-17 更正行）
前序：#146（降桶标注机制）→ 长电靶探针（覆盖为零）→ #149（更正）
本单性质：live 验证，**不改代码、不改 prompt、不动 8792**

## 0. 一句话

用 DRAM 题重跑降桶探针，拿**一手证据**（trace 或落盘的 LLM 上下文，不是答案正文反推）证明 superseded 证据这次真的进了上下文，并如实记录模型处置。标注文案出不出**不是**本单验收项（见 §4 第 4 条）。

## 1. 背景（不了解 #146 的人从这读）

#146（已合，8792 现跑 `877e1f72`）给「事实 claim 只绑了已被取代/证伪证据」加了两件事：门禁 warning `llm_fact_only_superseded_evidence` + 正文行尾降桶标注 `STALE_EVIDENCE_TIER_NOTE = "（待核验：所据证据已被取代或证伪）"`（`intelligence/services/answer_model.py`，判据 `_claim_rests_only_on_stale_evidence`，单一真本源）。

这条路径至今只有单测覆盖。2026-08-17 晚用长电科技题打过一发 live，**覆盖为零**，两个原因（都有账，见 #149）：

1. **证据侧**：`collect_evidence_index`（`intelligence/services/evidence_providers.py:526`）只遍历 `knowledge.get_evidence(target, limit=options.max_evidence)` 的返回，`max_evidence` 默认 **8**，adapter 排序 active 优先。长电 34 条证据里 2 条 superseded 排在 top-8 外——模型压根没见过。
2. **标注侧**：`llm_refine.SYNTHESIS_PROMPT_TEACHES_CLAIM_MARKERS = ("claim_id=" in _SYNTHESIS_SYSTEM_PROMPT)` 现为 **False**——合成 prompt 不教 marker 语法，模型写不出合法 marker，`present_llm_answer` 无 claim 可标。这是 #146 的**设计内豁免**（prompt 教语法之日闸自动回来），不是 bug，**本单不许顺手修**。

所以本单只验**证据侧**：换一个 superseded 边能进 top-8 的靶，证明「证据在场」这半段是通的。

## 2. 靶子：DRAM（跑前必须重扫确认）

2026-08-17 时点实测：`get_evidence('DRAM', limit=8)` 返回 7 条，其中 **2 条 superseded 全进 top-8**（备选靶：mSAP、电子特气各 1 条；长电/MLCC/电子布等富证据宿主结构性够不着）。两条边内容（都是长鑫科技收入口径）：

- `[[晚间卖方研报20260518]]`：长鑫招股书细化，26Q1 收入 508 亿(+719%)、26H1 预计归母 500-570 亿 ← 被 07-24 华西深度取代
- `[[晚间卖方研报20260724]]`：华西长鑫深度，预计 26-28 年营收 2776.90/3917.94/5726.94 亿 ← 被 07-27 上市实况取代

KB 会演化，跑前重扫（也可换靶）：

```sh
set -a; . <(grep '^export ' /Users/a77/.local/bin/start-finance-workbench | sed 's/^export //') >/dev/null 2>&1; set +a
cd ~/finance-workspace-runtime   # 或任一 gitea/main 检出
PYTHONPATH=$PWD /Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
import os
from intelligence.adapters.knowledge import KnowledgeAdapter, evidence_status
ka = KnowledgeAdapter(os.environ['KNOWLEDGE_WIKI'])
items = ka.get_evidence('DRAM', limit=8).get('items') or []
print([(evidence_status(i), str(i.get('source'))[:30]) for i in items])
"
```

题目建议：**「长鑫科技的收入规模和 DRAM 国产替代进展怎么看」**——题面带「DRAM」保证 target 命中（`collect_evidence_index` 的 targets 列表 = anchor 实体 + matched_theme + query 原文 + 公司概念映射），收入口径正对两条 stale 边。

## 3. 跑法

优先级 A：若《2026-08-17-live-probe-traceability.md》的 trace 化探针已交付，用它（能拿 `trace.jsonl` / 落盘上下文，一手证据直接有）。

优先级 B（该单未交付时）：沿用 in-process 探针 + 确定性复核双管：

```sh
set -a; . <(grep '^export ' /Users/a77/.local/bin/start-finance-workbench | sed 's/^export //'); set +a
cd ~/finance-workspace-runtime
PYTHONPATH=$PWD WORKBENCH_REPO_ROOT=$PWD WORKBENCH_GROUNDED_PRESENTER=0 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  ~/.finance-runtime/claim-tiering-20260817/run_live.py "<题>" live-dram-superseded
```

in-process 探针不落逐步 trace（上一发就是栽在这），所以 B 路必须**另跑一发同题 `use_llm=False`** 并把 LLM 上下文装配段的证据行落盘核对（`AskResult.prepared_synthesis_messages` 在 `use_llm=False` 时为空——正确做法是复算 `collect_evidence_index` 的输出或在 `use_llm=True` 收据里把 `synthesis_messages` 全量写下来），确认「⚠️已被新证据取代」或两条边原文在场。**答案正文提到新证据 ≠ stale 边在场**（上次的错就这么犯的）。

## 4. 验收（可判定）

1. 一手证据证明上下文含 stale 边：trace/落盘消息里出现「⚠️已被新证据取代」标记或两条边文本。收据注明证据等级（trace 级 / 落盘上下文级），**不接受正文反推**。
2. 收据落 `~/.finance-runtime/claim-tiering-20260817/live-dram-superseded.json`，含 elapsed、warnings、telemetry（`structured_claim_count` / `unbound_claim_line_count` / `revision_trigger` / `tier_note_present`）。
3. 模型处置如实记录：复读旧数？用了新证据指针？报缺口？
4. `tier_note_present=false` 且 marker=0 是**预期**（prompt 门禁），as-is 记录，不修 prompt、不改 `max_evidence`。
5. 台账：`docs/handoffs/inflight/main.md` 补一行结果；有新事实再加 roadmap 决策队列行。薄账走 docs-only PR（先例 #148/#149）。

## 5. 纪律红线

- 基线从 `gitea/main` 开（本机旧 `main` 落后几百个提交）；`gh` 不可用，PR 走 Gitea API（token：`security find-generic-password -s gitea-local -a a77-token -w`）或网页 http://localhost:3300 。
- 不动 8792（launchd `com.a77.finance-workbench`，快照 `finance-workspace-877e1f721e05`）；探针是进程内/旁路，不经过它。跑前确认 `/tmp/finance-8792-live.lock` 不存在。
- 若跑 pytest：**umask 022**（077 下 16 个 ceiling 权限位审计假红，环境项非回归）。
- 密钥全在 Keychain，不落盘。
