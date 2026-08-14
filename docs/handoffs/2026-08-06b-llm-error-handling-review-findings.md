# Handoff — `fix/llm-error-handling` 质检发现（2026-08-06b·评审方视角）

> **本文是质检发现清单，不是当前状态。** 作者（agent A）已按本文修完 P0-1 / P0-2 / P1，
> 修复结果与证据见同目录 `2026-08-06b-llm-error-handling-review.md`（A 自己写的）。
> 本文保留下来是因为「已排除的疑点」那一节对后续改这块的人仍然有用——它记录的是
> **验证过程**，包括我自己走过的弯路。读顺序：先读 A 那份看现状，需要追溯为什么这么改
> 再回来读本文。
>
> 原文件名 `-review.md`，2026-08-06 改为 `-review-findings.md`：A 在它的分支上
> 用了同一个文件名写修复结果，两份内容不同、用途不同，重名会在合并时 add/add 冲突。

> 给该分支的作者（agent A）。两个 commit 的**方向是对的**——LLM 失败原因不透传、
> `general_finance_qa` 缺 fallback 都是真缺口，诊断也扎实。下面只列需要动手的部分，
> 以及**我已经替你排除掉的疑点**（别再花时间查那几项）。

## 0. 结论

| 项 | 结论 |
|---|---|
| 分支 | `fix/llm-error-handling`，2 commits（`fabc2046` / `03ab6b08`） |
| 与 main 合并 | ✅ `merge-tree` 干净（虽落后 3 个提交，两边都改了 `ask.py`） |
| 阻塞合并 | **P0-1 标签与内容不符**（用户可见的错误陈述）、**P0-2 零测试覆盖** |
| 可合并前提 | 修完两个 P0；P1 两项建议一并处理 |

---

## P0-1 · fallback 标签与内容不符（用户可见）

`fallback_assessment_used` 是 **5 条 fallback 共用的一个 bool**，而 `ask.py:2252`
的标签文案是当初为 `market_cause`（周内盘面数据）写死的：

```python
assessment_label = (
    "基于周内结构化数据的机制判断（外部触发因素仍待核验）："
    if fallback_assessment_used
    else "基于本轮已收集证据的判断："
)
```

新增的 general fallback 也设了这个标志（`ask.py:2011`），于是**实测输出**是：

```
基于周内结构化数据的机制判断（外部触发因素仍待核验）：针对「超纯应材合理估值是多少」，
本轮检索到以下可回查材料：超纯应材_逻辑卡：国内半导体湿电子化学品龙头，主营超净高纯试剂。。
以上证据为初步线索，模型的深度分析与条件化判断仍需后续补全。 [R1]
```

内容是**研报文本摘要**，标签却宣称是**「周内结构化数据的机制判断」**。用户问估值，
拿到一段公司简介，还被告知这是基于盘面数据的机制判断。

**这比空白更糟**——空白至少是诚实的降级，这是一句错误的自我描述。原改动想解决的正是
「降级原因对用户不可见」，这里却给了用户一个错误的降级原因。

**复现**（不需要起服务）：

```python
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.ask import _general_finance_fallback_assessment
ev = [AgentEvidence(tool="kb_search", title="超纯应材_逻辑卡",
                    detail="国内半导体湿电子化学品龙头，主营超净高纯试剂。", source="wiki")]
a = _general_finance_fallback_assessment(ev, query="超纯应材合理估值是多少")
print("基于周内结构化数据的机制判断（外部触发因素仍待核验）：" + a)
```

**建议修法**：把 `fallback_assessment_used` 从 `bool` 改成 `str | None`（存 fallback
种类，如 `"market_cause"` / `"general_finance"`），标签按种类取。general 这条的标签
应当如实说明它是什么，例如「基于本轮检索材料的初步线索（模型深度分析不可用）：」。

顺带：`。。` 双句号——`detail` 自带句号，模板又加了一个。

---

## P0-2 · 零测试覆盖

净改动 3 文件 100 行，**没有一行测试**。handoff 里的「351 passed」是已有测试，两个新
函数一条断言都没有。**这两个函数恰恰是最需要钉住的**——它们在 LLM 挂掉时才执行，正常
路径永远走不到，回归时不会有人发现它坏了。

建议至少补这几条（每条写完做**变异测试**：把被保护的那行改坏，确认测试真的变红；
不变红的测试是永远绿的假门禁）：

**`_llm_failure_brief`（`conversation_orchestrator.py`）**
- 全部调用失败 → 返回 `"timeout×1, http_502×2"` 这类摘要
- **有一次成功 → 返回 None**（这是该函数的核心不变量，"有一次成功就不多嘴"）
- ledger 为空 → 返回 None
- 计数与分组正确（同 reason 合并计数）

**`_general_finance_fallback_assessment`（`ask.py`）**
- 有证据 → 含 query、含证据摘要、含「仍需后续补全」标注
- `detail` 全空 → 走「未取得可直接引用的证据材料」分支
- **只取前 3 条**（现在传 5 条会静默丢 2 条，得有测试说明这是有意的）
- 触发条件：`QUESTION_GENERAL` + assessment 为空 + 有证据，三个条件各缺一个都不触发

**`fail_closed_answer_spec` 的 `llm_failure_summary`（`task_fulfillment.py`）**
- 传入时降级文案含失败原因；不传时保持原文案（向后兼容）

---

## P1-1 · assessment 长度失控

已有 4 条 fallback 的模式是**按前缀提取字段 → 填固定模板**：

```python
window     = next(line for line in details if line.startswith("窗口："))
index_line = next(line for line in details if line.startswith("上证指数："))
→ f"从{window}的盘面证据看…{index_line}；{pressure_line}。"     # 约 150 字，长度可控
```

新增这条是**原始文本直接拼接**，无提取、无模板、无长度上限：

```python
top = details[:3]
summary = "；".join(top)
```

**实测**：5 条 × 288 字 → assessment **938 字**。而 2026-08-06 真实 run 的 RAG 证据
预算是 **1200 字/条**（见输出里 `LLM证据预算=1200字/条，总4800字`），3 条可达
**3600+ 字**，比已有模板长 20 倍以上。这段会经 `ask.py:2251` 拼成 claim 进入用户
可见回答。

原 handoff 说「与其他 4 条 fallback 同模式」——**这一点不准确**，模式实质不同。
建议要么给每条证据截断（如 120 字），要么改成字段提取式。

---

## 已替你排除的疑点（别再查了）

| 我一度怀疑 | 实测结论 |
|---|---|
| 硬设 `loop.sufficient = True` 有语义污染风险 | 已有 4 条（`ask.py:1969/2030/2050/2074`）**也都这么做**，是同模式，不是新引入的问题 |
| 触发条件没检查 LLM 是否真失败，正常但空 assessment 也会误触发 | 已有 4 条同样只检查 `not assessment.strip()`，同模式 |
| `evidence_display_text` 可能泄漏 internal_locator | 只取 `title` + `detail`（`agent_research.py:534`），**无泄漏** |
| 证据门槛比已有 fallback 松（只要 `evidence` 非空，不要求特定工具） | 差异属实，但 `QUESTION_GENERAL` 本就不走 `market_data`/`mainline_context`，放宽合理，**不算缺陷** |

---

## 两处 handoff 与现状不符（会导致白做）

1. **「待办：`git stash pop` 恢复 fix/evidence-logic-lifecycle 的 4 个文件」**
   —— 那个 stash 我已经用掉了，内容经 `2731823a` 合入 `main@7129d01a`，分支已删。
   `git stash list` 现在是**空的**，照做会一无所获。**那条待办可以直接划掉。**

2. **「当前服务 PID 75743 跑 03ab6b08」** —— 8801 原本是我起的 canary（用于验证
   `fix/evidence-logic-lifecycle`），你重启后占用了同一端口，cwd 指向主树
   （现在在 `fix/llm-error-handling`）。这没问题，但要知道：**8801 现在跑的是你的
   分支代码，不是 main**。agent B 手上那份 handoff 里「重启 8801 验证 lifecycle」
   那条已因此失效，我已同步修正。

---

## 开工提示

- 主树当前在你的分支上，我全程用 worktree 作业，**没有动过主树**
- 解释器必须 `.venv-workbench/bin/python`
- 改文案前先 grep 谁在按文案做匹配——本仓有两处这样的耦合
  （`research_brief._L4_TERMS`、`eval/agent_eval.STALE_MARKS`），
  我今天在 lifecycle 改动里被前者咬过一次：一个纯文案改动穿过分层分类器改变了风险结论
