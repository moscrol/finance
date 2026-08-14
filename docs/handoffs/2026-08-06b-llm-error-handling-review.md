# fix/llm-error-handling 质检与整改记录（2026-08-06b）

**方向是对的。** 被诊断出的两个缺口都是真的，trace 归因扎实：Run 1 是 OpenAI 全挂
（3 次调用 timeout + http_502×2），Run 2 是 agent loop 首次 LLM 超时导致
`sufficient=None` / `assessment=""`，而 `general_finance_qa` 是唯一没有 fallback
assessment 的常见题型——有 5 条 kb_search 证据却出空白，根因不在 error handling 而在
门禁链第一层。这两个判断我复核过，成立。

本文件记录质检发现的问题**以及已完成的整改**。质检时提出 2 个 P0 + 1 个 P1，均已修完
并验证；文末列出剩余未完成项。

---

## 分支状态

```
分支      fix/llm-error-handling（主检出树 /Users/a77/finance-workspace-private）
已提交    fabc2046  LLM 全挂时降级文案加入失败原因
          03ab6b08  通用金融问题 LLM 不可用时用证据摘要生成 fallback assessment
未提交    intelligence/services/ask.py            +27 / -10   （P0-1 + P1 整改）
          intelligence/tests/test_general_finance_fallback.py  新增 141 行（P0-2）
```

---

## P0-1 标签与内容不符（已修）

### 问题

`fallback_assessment_used` 是 5 条 fallback **共用的一个 bool**，而它控制的标签是为
`market_cause` 写死的：

```python
# 修改前 ask.py:2252
assessment_label = (
    "基于周内结构化数据的机制判断（外部触发因素仍待核验）："
    if fallback_assessment_used
    else "基于本轮已收集证据的判断："
)
```

新增的 `general_finance` fallback 也设了 `fallback_assessment_used = True`，于是
「超纯应材合理估值是多少」会拿到一句「基于**周内结构化数据**的机制判断（**外部触发
因素**仍待核验）」——估值题既没有周内盘面，也没有外部触发因素。

**这比空白更糟。** 原改动的目的是解决「降级原因对用户不可见」，结果给了用户一个
错误的降级原因，而且用户无法察觉它是错的。空白至少诚实。

### 修法

`bool` → `str | None`，保留种类信息；标签选择抽成纯函数便于测试：

```python
_FALLBACK_ASSESSMENT_LABELS = {
    "market_cause": "基于周内结构化数据的机制判断（外部触发因素仍待核验）：",
    "general_finance": "基于本轮已检索证据的初步判断（深度分析仍待补全）：",
}
_DEFAULT_ASSESSMENT_LABEL = "基于本轮已收集证据的判断："

def _assessment_label_for_fallback(kind: str | None) -> str: ...
```

`fallback_assessment_kind = None` 初始化；`market_cause` 分支设 `"market_cause"`，
`general_finance` 分支设 `"general_finance"`。其余三条 fallback 原本就不设这个变量，
行为不变。

已确认全仓无 `fallback_assessment_used` 残留引用。

### 复现（不用起服务）

```bash
cd /Users/a77/finance-workspace-private
.venv-workbench/bin/python -c "
from intelligence.services.ask import _assessment_label_for_fallback as f
print('general_finance:', f('general_finance'))
print('market_cause   :', f('market_cause'))
print('None           :', f(None))
assert f('general_finance') != f('market_cause'), 'P0-1 回归'
print('OK: 两种 fallback 不共用标签')
"
```

---

## P0-2 零测试覆盖（已修）

### 问题

`_general_finance_fallback_assessment` 全仓只有 2 处引用：定义处和触发点，**没有任何
测试**。

这个函数尤其需要覆盖，因为它**只在 LLM 挂掉时执行**。正常路径永远走不到它，坏了不会
有人发现——这正是 Run 2 那个缺口能一直存在的原因：`general_finance_qa` 缺 fallback
这件事，在 LLM 正常时完全不可观测。

### 已补

新增 `intelligence/tests/test_general_finance_fallback.py`，11 个用例，全部直接测
纯函数，不跑 owner 管线：

| 覆盖点 | 用例 |
|---|---|
| 有证据 → 含 query + 摘要 + 「初步线索」标注 | 1 |
| 无证据 / detail 全空 → 「未取得」占位 | 2 |
| 单条 evidence 截断到 200 字 | 1 |
| 最多取前 3 条（第 4、5 条不进摘要） | 1 |
| 不含 market_cause 专用措辞 | 1 |
| 标签分发：三种 kind 各自正确、两两不相等 | 4 |
| 未知 kind → 回落默认标签 | 1 |

### 变异测试（已实跑）

把 `general_finance` 的标签改回 `market_cause` 那句（复现 P0-1 原始 bug）：

```
2 failed, 9 passed
FAILED test_general_finance_label_is_not_market_cause_label
FAILED test_two_fallback_kinds_do_not_share_one_label
```

还原后 11 passed。**测试确实能抓到这个 bug，不是摆设。**

---

## P1 摘要长度失控（已修）

### 问题

`evidence_display_text` 返回 `title + "：" + detail`，`detail` 无长度约束。
kb_search 的研报正文常见数百字，3 条拼接后可轻易冲到千字级；而 `AgentLoopResult.
assessment` 在 `agent_research.py:799` 有 `[:1600]` 截断——超长会被**从中间切断**，
末尾那句「模型的深度分析与条件化判断仍需后续补全」正好被切掉，用户看到的是一段
无标注、看起来像已完成分析的截断文本。

### 修法

每条 evidence 单独截断到 200 字，3 条 + 固定措辞最坏约 650 字符，安全落在 1600 以内：

```python
_MAX_ITEM_CHARS = 200
details = [
    agent_research.evidence_display_text(item)[:_MAX_ITEM_CHARS]
    for item in evidence
    if item.detail.strip()
]
```

---

## 已替你排除的疑点（不用重查）

拿到质检报告最容易做的事是把所有可疑点重查一遍。以下四条我已经查过，**不是缺陷**，
省你一轮：

| 疑点 | 结论 |
|---|---|
| `sufficient = True` 是否语义污染（LLM 没跑完却标 True） | **非缺陷。** 现有 4 条 fallback（`market_cause` / `mainline_current` / `market_fact_current` / `market_forecast`）全部这样写，是既有约定。我最初怀疑它，写到一半才去查已有实现——若停在推断上就会提出一条错误整改，让人去改一个符合约定的东西。 |
| 触发条件 `question_type == QUESTION_GENERAL and not assessment.strip() and evidence` | **同模式。** 与其他 4 条 fallback 的三段式条件结构一致（题型/profile + assessment 空 + 证据存在）。 |
| fallback 文案是否泄漏内部 locator（路径、chunk id、hash） | **不泄漏。** 只用 `evidence_display_text`（title + detail），不含 source path / content_hash。 |
| 证据门槛是否过松（1 条证据就触发） | **与既有一致。** `market_cause` 也是 `visible_evidence` 非空即触发，没有条数下限。若要加门槛应统一改 5 条，属独立议题。 |

---

## 验证

解释器必须用 `.venv-workbench/bin/python`（宿主 `python3` 缺 fastapi 等依赖，报
`ModuleNotFoundError` 是解释器错不是环境缺包）。

```
test_general_finance_fallback.py                    11 passed
全量回归（generic_research_owner / agent_research /
ask_compose / ask_external_fallback / task_fulfillment /
conversation_orchestrator / answer_orchestrator）   278 passed
```

---

## 剩余未完成

| 项 | 说明 |
|---|---|
| **实跑验证** | 未完成。8801 的 LLM 凭证在重启时丢失（session-only，非持久化），`/api/llm/config` 显示 `credential_persisted: false`。需重新配 key 后重问「超纯应材合理估值是多少」，确认答案不再空白、且标签是「基于本轮已检索证据的初步判断」而非「周内结构化数据」。 |
| **提交整改** | `ask.py` +27/-10 与新增测试文件尚未 commit。 |
| **合并 main** | 按约定等确认，不自行合并。 |
| **`fix/evidence-logic-lifecycle`** | stash 中有 4 个文件，`git stash pop` 可恢复。 |

### ⚠️ 端口占用警告（给并行作业的人）

**8801 现在跑的是本分支代码**（PID 75743，`source_revision: 03ab6b08`，cwd 指向
主检出树 `/Users/a77/finance-workspace-private`）。照原样重启 8801 会加载本分支代码，
验错东西。并行验证请用独立端口 + 独立 worktree：

```bash
git worktree add /Users/a77/fwp-wt-<name> <your-branch>
cd /Users/a77/fwp-wt-<name>
FINANCE_WS=$PWD WORKBENCH_REPO_ROOT=$PWD \
FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users \
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python \
RAG_INDEX_DIR=/Users/a77/knowledge-base-private/.rag_index \
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port 8802
```

起完用 `curl -s localhost:8802/api/health | grep source_revision` 确认加载的是你的
commit。当前 worktree 占用：`fwp-wt-evaluator`（fix/evaluator-scoring）、
`fwp-wt-logic-match`（feat/logic-market-match）。

### 服务无认证（已知，非本次引入）

8801 无任何认证，`/api/artifacts/{id}/content` 直接开放。��� `127.0.0.1` 时风险可控，
但改成 `0.0.0.0`（手机访问/容器调试）前必须先加 token——同网段任何人可拉走全部 run、
artifact 和回答内容。
