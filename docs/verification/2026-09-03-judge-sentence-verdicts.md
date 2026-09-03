# P2 第一步：判官拒句结构化落盘（判据不改）（2026-09-03）

spec `2026-09-02-capability-amplification-output-gate-design.md` §3.3「先量后改」第 1 步。能力放大线交接「下一步 ④」。
分支 `feat/judge-sentence-verdicts`。

## 落点

- 写侧 `intelligence/services/episode_semantic_verifier.py`：
  - `SemanticEpisodeOutcome.sentence_verdicts: tuple[dict, ...]`，`to_dict()` 出 `"sentence_verdicts"`（进私有产物 `continuous-episode.json` 的 `semantic_verifier`）。
  - 两个决定点各记一次：**preflight**（判官之前的机械探测：新阈值数字 / 星期错配 / 路径趋势）与 **judge**（每轮
    `_plan_repair_indexes`：机械 → 删；语义且在必需槽内 → 降成 issue；语义且在槽外 → 删）。`verify()` 包一层统一挂账，
    内层十几条提前返回不用逐条改；账本为空时返回值逐字节不变。
  - 每条：`stage` / `judge_round` / `sentence_index` / `sentence` / `decision`（`deleted` | `demoted_to_issue`）/ `reasons`
    / `judge_issues`（`_ISSUE_SENTENCE_INDEX_RE` 点到该句的原话）/ `cited_evidence_ordinals` / `unresolved_evidence_ordinals`
    / `bound_evidence_hashes`（E 号经 `evidence_ordinal_table` 逆映射）/ `source_tiers`（`AgentEvidence.evidence_tier`）。
  - **不解析自由文本定出处**：只认句子里显式的 E 号；没引 E 的句子 `source_tiers=[]`，这本身是读侧要分开数的一类。
- 读侧 `scripts/offline_judge_verdict_census.py`：扫 run 目录，按 stage / decision / reason 汇总；`deleted` 拆成
  有出处 / 只引表外 E / 没引；给出 `with_source_share` 与来源档分布；历史 run 没字段**报「不可判」不进分母**。

## 被否的做法

- 在 `_drop_rejected_sentences` 里记——它只拿到索引，不知道是机械还是语义、也不知道是不是被降级（降级的句子根本不进它）。
- 让判官 prompt 回结构化 JSON 字段——那是改判官契约，第 1 步说好只记不改。
- 从 `issues` 自由文本反解出处——判官原话里的「第 N 句」只够定位句子，出处必须走 E 号表。

## 钉子与变异

`intelligence/tests/test_judge_sentence_verdicts.py` 6 条：机械拒句（表外 E99）记 deleted 且 `unresolved_evidence_ordinals=["E99"]`；
语义拒句在必需槽内记 demoted 且 `judge_issues` 精确对到「句2」「第3句」；preflight 数字阈值记 deleted、`judge_round=None`；
E1 反解到哈希与 `public_web` 档；干净通过时账本为空、产物形状稳定；读侧对「一新一旧」两个 run 的分母处理。
变异「降级误记为删除」→ 2 红。判官相关既有 233 条测试零回归（共 239 passed）。

## 首读

`offline_judge_verdict_census.py --runs-root ~/.local/share/finance-workbench/users`：814 个 run 全无字段 → **不可判**。
第 2 步的占比要等本分支合入并切 8792 后积累；spec §3.3 状态行已写明要数的两个数（`deleted` 有出处占比、`demoted` 低档来源条数）。

## 与今天 live 读数的关系

腾讯题参考臂（`2026-09-03-web-chain-two-arm-live.md` §3）：判官对 5 条 `public_web` 证据零删除、4 条 issue 全是降级标注。
按本账的枚举那是 4 条 `demoted_to_issue`；那次跑在没有本字段的快照上，所以只能人工读，不在普查里。这一例说明
P2 的原始担忧（「新来源整片删」）在 V8 语义降级之后形状已变，第 2 步的阈值要对着 `deleted` 那一半量。
