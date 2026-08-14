# 在办登记 — 2026-08-06 三条并行线（改动面重叠，开工前必读）

> 建这份的原因：同一天里三条线同时改 `intelligence/services/ask.py`，而没有任何地方
> 能查到「谁在管哪块」。今天已经因此发生过一次实际损失——一条线把另一条线的未提交
> 改动 stash 掉并切走了分支。**开新线前先在这里加一行；本文过期比没有更糟，做完请划掉。**

## 当前三条线

| 线 | 分支 | 位置 | 基点 | 在改 | 状态 |
|---|---|---|---|---|---|
| A | `fix/llm-error-handling` | **主树** | `03ab6b08` | `ask.py`、`conversation_orchestrator.py`、`task_fulfillment.py` | LLM 失败透传 + general_finance fallback，已修完质检三项，**未 commit** |
| B-1 | `feat/logic-market-match` | `/Users/a77/fwp-wt-logic-match` | `fc7b00a4` | `ask.py`、`ask_types.py`、`agent.py`、`evidence_providers.py` 等 7 文件 | 接入 `logic_market_match` 四分类（lifecycle handoff 的 P0-1），**未 commit** |
| B-2 | `fix/evaluator-scoring` | `/Users/a77/fwp-wt-evaluator` | `fc7b00a4` | `eval/finance_answer_rubric.py` + 测试 | 修答案自评口径（lifecycle handoff 的 P0-2），**未 commit** |

## 已知冲突面

- **`ask.py` 三线都在改**（A 改 fallback 段、B-1 改证据渲染段）。A 的基点 `03ab6b08`
  **不含** `main@7129d01a` 的 lifecycle 改动，B-1 的基点含。**A 先合 main 会更省事**，
  否则 B-1 合入后 A 要解两轮。
- **`evidence_providers.py`**：B-1 在改，而 lifecycle 改动刚动过同一段（证据行 mark）。
  B-1 若要加中文分类描述，**先查 `research_brief._L4_TERMS`**——文案撞词表会穿过
  `classify_evidence_line` 改变风险结论，今天已被 golden 快照抓到过一次。

## 端口归属（别互相抢）

| 端口 | 归属 | 跑的代码 |
|---|---|---|
| 8792 | launchd（生产） | `.finance-runtime/finance-workspace-8ccca8ca` 旧快照。**不可手工 kill** |
| 8801 | A（原为 lifecycle canary，已被 A 重启接管） | 主树 = `fix/llm-error-handling` |
| 8802+ | 空闲 | 需要验证请另起，脚本模板 `/tmp/start-canary-8801.sh`，改端口与 cwd |

⚠️ **lifecycle handoff（`2026-08-06-evidence-lifecycle-and-open-items.md`）的 P1-1
原写「重启 8801 验证」，该条已在 `6b7fcf56` 修正为另起 8802。基点早于 `6b7fcf56`
的线看到的是旧版，照做会加载到 A 的分支代码、验错东西。**

## 合并建议顺序

1. **A**（`fix/llm-error-handling`）——改动面最小且已验完，先合减少后续解冲突轮次
2. **B-2**（`fix/evaluator-scoring`）——只碰 `eval/`，与其他两线无重叠
3. **B-1**（`feat/logic-market-match`）——改动面最大，最后合，只需解一轮

每条合并前跑全量 `intelligence/tests`：基线是 **13 failed**（宿主环境，
`test_userspace` 3 + `test_subconscious` 8 + `test_acceptance_board` 2），
多出任何一条都是新引入的。解释器必须 `.venv-workbench/bin/python`。
