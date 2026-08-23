# D1 关单：未分类判官 RuntimeError 不是漏标（2026-08-24）

- 规格：`docs/superpowers/specs/2026-08-24-harness-ceiling-and-8796-decouple-followup.md` §5
- 台账：`R-20260824-07` → **confirmed**（结案理由=「无漏标、保持 fail-closed」，**零产品 diff**）
- 现场：`~/.finance-runtime/trace-diff-spt-ysjs-20260823/workbench-8796/`
- run：`run_20260823_160445_064352`（8796 @ `76ee1e89`，不是 8792）
- 对照代码：`gitea/main` / 8792 `8688545b` 的 `llm_refine.complete` + `_stable_semantic_judge_error`

结论：**不改分类器，不新开第三扇放稿门。** 结构 completed + 1215 字 draft 不能当放稿条件。

---

## 1. 问的是哪句

v3：只有失败的 cause / HTTP / 文案**已经属于** timeout、429/5xx、Connection 那些已有标记，才许贴进 `_transient_failure_candidate`。贴不上就关单。

禁止：RuntimeError 整类加白；结构齐就放。

---

## 2. 8796 工件里实际有什么

| 字段 | 读数 | 是不是已有 transient 标记 |
|---|---|---|
| `judge_status` | `unavailable` | — |
| `exc_class` | `RuntimeError` | 否 |
| `http_status` | `null` | 否 |
| `issues` | `semantic judge provider error` | 否（这是分类器兜底句） |
| `timeout_asked` / `configured` | 50 / 50 | 窗够大 |
| `remaining_seconds_at_entry` | 233.9 | **不是** leftover / deadline 型 |
| `judge_attempt_index` | 0 | 第一发就挂 |
| 结构 / draft / bindings | `completed` / 1215 字 / 齐 | 桌上有菜，与分类无关 |
| `__cause__` / 原始错误串 | **工件里没有** | 无法回放内层 |

同 run 第 14 个 `model_turn` 的 `LLM 调用失败（TimeoutError）` 是**写手**，`timeout_asked=20`。判官进场还剩 233 秒，两件事不是同一刀。

---

## 3. 这条读数是怎么造出来的（不是漏标）

`llm_refine.complete()` **不抛给调用方**。它把一切 `Exception` 收成 reason 串再返回：

```text
LLM 调用失败（{type(exc).__name__}）
```

`_judge_failure_identity` 从括号里抠类名 → 落盘 `exc_class=RuntimeError`。  
`_stable_semantic_judge_error("LLM 调用失败（RuntimeError）")` 认不出 timeout / 5xx / Connection → 兜底 `semantic judge provider error`，`release_safe=False` → `_gap_answer`。

这和夹具 `test_unclassified_runtimeerror_holds_draft_without_evidence_lie`（#346 P0-B）是同一条路：reason 只是 `"RuntimeError"` 时**必须**扣稿，且不得写「证据不足 / 未绑定」。

内层 `str(exc)` 在包装时就被丢掉了。工件按设计不存原文（`_judge_failure_identity` 注释：messages discarded so public artifacts stay sanitized）。所以不能事后证明「其实是 TimeoutError 包成了 RuntimeError」。

独立判官路径里 `complete()` 的 `except` 只把 `type(exc).__name__` 送给分类器——那是另一条缝，但 `complete()` 自己不抛，8796 **没走这条缝**。本单不修它。

---

## 4. 三筛（为什么关单是减法）

| 问 | 答 |
|---|---|
| 拦输入还是输出？ | 拦输出（判官没报告就扣稿） |
| 模型变强会更惨吗？ | 不会：这是供应商/适配器未知失败，不是稿写错 |
| 保下限还是封上限？ | **保下限**：未知 RuntimeError 可能是格式坏、鉴权、空响应。#346 已否决整类加白 |

把「结构齐」写成放稿条件，是给端盘加第三扇门，v3 否决。

---

## 5. 复算

```bash
# 工件形状
.venv-workbench/bin/python -c "
import json
from pathlib import Path
p=Path.home()/'.finance-runtime/trace-diff-spt-ysjs-20260823/workbench-8796/continuous-episode.json'
sv=json.loads(p.read_text())['semantic_verifier']
print(sv['exc_class'], sv['http_status'], sv['issues'], sv['timeout_asked'], sv['remaining_seconds_at_entry'])
"

# 分类器：类名 RuntimeError 不得标 transient（已有夹具）
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_semantic_verifier.py::test_unclassified_runtimeerror_holds_draft_without_evidence_lie
```

---

## 6. 不做的替代

| 方案 | 为什么不做 |
|---|---|
| 结构 completed 就放 1215 字稿 | 输出侧加法，顶 #346 #7 |
| 把 `RuntimeError` 整类标 transient | 同上 |
| 改 `complete()` 把 `str(exc)` 写进 reason | 爆破面是全仓 LLM 调用，且会把原文送进可能外泄的串；本单取证不够开这刀 |
| 双 judge | 成本翻倍，不拆闸 |

若以后 live 落盘里出现 `LLM 调用失败（TimeoutError）` 却仍走 gap，那才是分类器漏标，另开单。
