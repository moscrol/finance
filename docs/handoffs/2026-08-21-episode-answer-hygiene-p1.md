# 2026-08-21 公开稿护栏 P1（#285）

已合 `gitea/main@4a1abf79`（head `309cec07`）。**2026-08-21 01:39 CST 已切 8792 → `dfc25221b07b`**（回滚 = `48369a313ff5`）。主检出脏树没动。切换与 live 读数见 `docs/handoffs/inflight/main.md` 顶部行。

规格：`docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md` §6.1 Q1、§6.3 Q3。Q2 / `R-20260820-11` 本单没做。

## 落地

新模块 `intelligence/services/episode_answer_hygiene.py`（纯函数，无 IO）。不要塞回 `episode_semantic_verifier.py`。

- **Q1 INV-5**：文案写「没查到」时 traces 必须有对应 **capability** 收据。四态：没调用 / 空结果 / `future_of_cutoff` / 截断。后三态允许写缺口。电网有收据 → 不得改口；锂矿窗口覆盖锚定日且截断 → 不得改口。无资讯 trace 才改口「本次未查询 {capability}{日期}」。调用点：判官**之前**扫 draft。
- **Q3 INV-7**：`repair_collapsed_to_stub` = 句数 < 2 **且** 字数 < max(80, 20%×修前) **且** 修前自身 ≥ 80 字 **且** `question_type` ∈ `ASKED_DATE_COVERAGE_TYPES`（含 `market_cause`，不含 `quick_fact`）。只在语义 repair **之后**触发。回退：`minus_flagged_sentences`；减完不够则 `whole_pre_repair`。C3 必填格全灭走整篇修前稿，不要和 Q3 减句混用。

账本 `R-20260820-09/10` 离线已绿。**live 已跑（2026-08-21，sidecar :8796 四跑），仍不得 `confirmed`**：四跑 `unattempted_claim_count` 全 `0`，只证了「有收据不改口」这半边；Q1 的改口路径与 Q3 的减句回退**一次都没触发**。`R-20260820-11` 按其自带判据改记 `deferred`。

## 已验证

定向：hygiene + `test_episode_semantic_verifier` + `test_judge_evidence_projection` = 190 passed。收据 `~/.finance-runtime/test-receipts/20260820T164557Z-48369a31.json`。合入前 ruff 绿。

## 下一步（接手默认）

8792 已切、live 已跑，两项都不用再做。Q2（`R-20260820-11`）仍 deferred。新代码从 `gitea/main` 开干净树，勿用 `/Users/a77/finance-workspace-private`。**跑 live 必须走 `POST /api/conversations/{id}/messages`**：`live_probe ask` 走 `/api/runs` 的中立泳道，产物没有 `continuous-episode.json`，P1 护栏一个字段都不产（整轮打空且看起来像"跑过了"）。

## 坑

Q3 挂 preflight 会把 Q1 改口稿当残稿交还；修前 <80 字会打爆既有 verifier 测试；对账用 `directional_news` 不是 `news_search`。
