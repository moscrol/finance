# 2026-08-30 · 限定语排在被限定内容之前（上下文压缩第一层修缮）

分支 `fix/observation-qualifier-order`，树 `/Users/a77/finance-workspace-private`（主检出树），
基线 `gitea/main@f40f878b` + 本地 `444a06e3`。实现提交 `52710ee8`。**未 push、未合、未切 8792。**

## 结论先行

对照 ai-agent-book ch2 的五层压缩清单，容易得出「第一层砍太狠、该放宽限额、还缺第 2/3/4 层」。
**实测把这三条都推翻了。** 第一层的限额没砍伤数据；被砍掉且无副本的，只有排在
observation 末尾的口径与使用说明。修的是**位置**，不是**限额**。

## 实测（这是本轮真正的产出，别只看代码）

读 400 份 `~/.local/share/finance-workbench/**/continuous-episode.json`。台账存的是
budget **之前**的全量（`agent_episode` 先 `ledger.add` 再 budget 模型副本），所以能直接算
「砍掉了什么」，不用推断。

**① 240 那刀几乎没触发。** kb_search detail p50 160 / p90 329 / max 858，18% 超限、共丢
5936 字符，是全表最小的一档；`KB_SEARCH_DETAIL_CHARS = 0` 表示送达层根本不截断。
finance_query detail 6197 条里超限率 0.05%。**放宽 detail 限额收益接近零。**

**② 900 那刀砍掉的 92% 是重复副本。** finance_query 的 observation 是把 `evidence[]` 的行
再拼一遍。被砍片段 6012 个，5540 个（92%）在同一条 payload 的 `evidence[]` 里逐条存在。

**③ 无副本的 8% 全是排在末尾的限定语：**

| 文本 | 出现 | 位置均值 | 被砍 |
|---|---|---|---|
| `查询结果已按…截断至 N 条` | 123 | 84% | **67** |
| `实际覆盖 X..Y` | 123 | 92% | **67** |
| `以下字段已在 metrics 中声明，已从 dimensions 移除` | 105 | 83% | 38 |
| `使用要求：`（mainline_context 读法规则） | 81 | 89% | 31 |
| `cycle_status=分歧/消亡不能写成无条件主升` | 70 | 88% | 18 |

即**关于行数截断的通知，一半以上的时候自己被字符截断砍了**；而「时点 / 完整性」正是
`tool_result_budget` 开头声明永不截断的红线。切口还落在半个股票代码上（`股票代码=300731.…`）。

**④ 长局爆窗不成立。** `DEFAULT_MAX_STEPS = 6`（`intelligence/runtime/agent.py:48`）；实测每
episode 工具调用 p50 3 / max 6，工具载荷 p50 12.5K / max 43.6K 字符。且
`build_conversation_context` 只收 `role in {user, assistant}`——**工具结果压根不进对话历史**。
第 3/4/5 层现在没有要压的东西，先别造摘要机。

复现（只读，不写任何东西）：

```python
import json, pathlib, collections
files = sorted(
    (pathlib.Path.home() / ".local/share/finance-workbench").rglob("continuous-episode.json"),
    key=lambda p: p.stat().st_mtime, reverse=True,
)[:300]
tot = cov = 0
per_tool = collections.Counter(); per_tool_unc = collections.Counter()
for f in files:
    try:
        doc = json.loads(f.read_text())
    except Exception:
        continue
    for e in doc.get("events") or []:
        if e.get("kind") != "tool_result":
            continue
        p = e.get("payload") or {}
        o, t = p.get("observation"), p.get("tool")
        if not isinstance(o, str) or len(o) <= 900:
            continue
        blob = "".join(str(i.get("detail", "")) for i in (p.get("evidence") or []) if isinstance(i, dict))
        for seg in [s.strip() for s in o[899:].split("；") if len(s.strip()) >= 8]:
            tot += 1; per_tool[t] += 1
            if seg in blob:
                cov += 1
            else:
                per_tool_unc[t] += 1
print(tot, cov, round(100 * cov / tot), per_tool, per_tool_unc)
```

## 改了什么

本仓 BUILD 模式 4 已经写下「**限定语排在被限定内容之前**」，`episode_tools` 也已在
`limit` 的 schema 描述上用过（`_agent_finance_parameters`）——**只有 observation 这一处没照做**。

1. `episode_tools`：finance_query 的截断提示 / 代偿说明 / 覆盖面提示改为前置。
   数据行在 `evidence[]` 里有副本，限定语没有，所以砍到的只会是有副本的那部分。
2. `agent_research.block_lines_to_evidence`：observation 内的限定语行提到最前，**只重排，
   不增删任何一行**，`evidence` 顺序不动。前缀表下沉为 `QUALIFIER_LINE_PREFIXES` 单一真本源，
   `episode_tools._NON_EVIDENCE_PREFIXES` 改为引用（同一张表既用来挡证据、也用来提前置）。
3. `tool_result_budget`：`context_budget` 只riding 模型副本，所以 `preserved` / `instruction`
   必须描述**整条流水线之后**模型还有什么。删掉「需要完整原文时以 evidence_hashes 为准」——
   `strip_hashes_for_model` 紧跟其后就把该字段摘了，且注册表里没有任何工具接受哈希或证据
   编号当参数。**指向不存在的取回路径，比不给指针更糟。**

## 验收

- 三条新门禁各自先断言「本次确实撞了预算」，再断言限定语可见——钉不变量而非顺序。
- **变异测试三条全红**（抽掉重排 / 改回追加 / preserved 换回 `evidence_hashes`），还原后 57 绿。
- `intelligence/tests` 全量：**6570 passed, 1 failed**。
  唯一那条 `test_conversation_orchestrator.py::test_completed_stream_persists_human_readable_answer`
  **改前就红**（把三个实现文件 `git checkout HEAD~1 --` 后单跑，同样红），与本轮无关。
- pre-commit 全绿（层级 / 路径字面量 / 字段契约 / dataset 注册 / 工具可达性）。

## 没做的那一件（留给下一轮，需要先拍板）

**让第 2 层删掉 observation 与 evidence 的重复**，而不是让第 1 层按字符切。
书里第 2 层的定义就是「低价值直接删、不做摘要」，92% 重复正是它的教科书对象。

**为什么没顺手做**：它会拿掉 finance_query observation 里约 1300 字符的模型可见内容。
虽然是重复内容，但会改变模型的阅读顺序与显著性，属于**要跑 A/B 才能判的改动**，
不是改完跑单测就能发绿的那种。建议按 `intelligence/eval` 的消融流程单独做一轮。
