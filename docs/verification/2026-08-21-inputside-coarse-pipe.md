# V3：kb_search 送达接 llm_evidence 粗管道（2026-08-21）

> 规格：`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md` §V3
> 台账：`R-20260821-15`（judged pending；live 由验收方回填，本单不得 confirmed）
> 分支：`feat/v3-kbsearch-coarse-pipe`
> **验收面**：送达量与结构。不得从本文件推出选段质量或答案质量结论——那是 V5（R-12 预测③：送达变大 ≠ 选段变好）。

## 0. 一句话

`_kb_search` 的 evidence.detail 从 `excerpt[:160]` 改为 `llm_evidence or display_excerpt or excerpt`（与 `evidence_search` 同规格）；`hits[:5]` / `[:160]` 改为 `KB_SEARCH_MAX_HITS=6`、`KB_SEARCH_DETAIL_CHARS=0`（0=送达层不再二次截断）。

## 1. 新旧送达读数对比

夹具：`intelligence/tests/fixtures/v3-kbsearch-jcet-hits.json`（query=`长电科技怎么看`，k=6，2026-08-22 从当前 wiki 索引冻结）。

| # | 命中页 | 旧管道 excerpt[:160] | 新管道 llm_evidence | 形态 |
|---|---|---|---|---|
| 1 | 长电科技_最新逻辑跟踪 | 160 字，第二项标题被切断 | 772 字，含完整 URL 与后续来源项「长电科技2026年一季报」 | 结构：截断点之后的内容进了 detail |
| 2 | 长电科技（600584） | 160 字「一句话」段 | 588 字，邻块含先进封装/华为芯片供应链 | 正文级字段在场 |
| 3 | 2025年度报告 baseline | 33 字纯路径行 ``raw/cninfo-baseline/长电科技.json`` | 312 字，邻块含 `annual_report_baseline` / L2 | 不再是纯路径行 |
| 4 | 颀中科技 | 30 字 wikilink 堆 | 118 字（命中块+邻块） | 量上升；选段仍可能是链接堆（V5） |
| 5 | 华天科技 | 29 字 wikilink 堆 | 219 字 | 同上 |
| 6 | 莱宝高科（旧 `[:5]` 丢掉） | （未送达） | 107 字 | 默认 max_hits=6，与 retrieve k 对齐 |

合计（evidence.detail 字符数）：

| 规格 | 条数 | 字符数 |
|---|---|---|
| 旧：`hits[:5]` + `excerpt[:160]` | 5 | **412**（上限 800；本 query 多条 excerpt 短于 160） |
| 新：`hits[:6]` + llm_evidence | 6 | **2116** |

合成夹具（6 条 × excerpt 200 / llm_evidence 800）：旧 800，新 4800。钉在 `test_same_query_delivery_chars_beat_legacy_800_cap`。

诚实边界：第 1 条加长后仍可能是来源清单——那是形状 IV，不在本单验收面。

## 2. 默认值预算账

retrieve 侧已经付过的账：

- `episode_tools.retrieve_kb`：`k=6`、`excerpt_chars=240`，超时传入 `context.timeout`（`kb_rag.select_mode_for_remaining` 在 remaining <15s 时把 mode 降到 BM25）。
- `kb_rag.retrieve`：`evidence_budget_for_query` 默认 per-hit 1200、total `max(4800, per_hit×4)` 且封顶 8000；`apply_total_llm_budget` 在返回前截总预算。长电本次 telemetry：`llm_evidence_chars=1200`，`llm_evidence_total_chars=4800`。

送达层默认：

| 参数 | 旧硬编码 | 新默认 | 论证 |
|---|---|---|---|
| `KB_SEARCH_MAX_HITS` | 5 | **6** | 与 `DEFAULT_RAG_K` / episode_tools `k=6` 对齐。retrieve 已按 6 条跑完并按总预算切过；`[:5]` 等于丢掉已付账的第 6 条。多送 1 条不抬总预算上限（总预算已在 retrieve 内切过）。 |
| `KB_SEARCH_DETAIL_CHARS` | 160（且源是 excerpt） | **0**（不二次截断，源是 llm_evidence） | 字符预算已由 retrieve 的 llm_evidence 总预算管住。送达层再 `[:160]` 是本单要拆的瘦管道。 |

**与 retrieval-tier plan 的冲突点（报验收方，未自作主张）**：

未合入文档 `docs/superpowers/plans/2026-08-20-retrieval-tier-by-remaining-budget.md` 的分档语义只有一条：remaining < 15s → 检索 **mode** 降 BM25（`fallback_reason=remaining_budget`）。代码已在 `gitea/main`（`select_mode_for_remaining`）。plan **没有**「剩余少 → 送达字符降档」这一条。

本单把 remainder 穿进 `kb_search_delivery_limits(remaining_seconds=…)` 作为接缝，但 4s 与 20s 返回同一对 `(6, 0)`——**不另建第二套降档**。若验收方日后要按剩余预算缩送达窗，改这一处函数并改 `test_delivery_limits_do_not_invent_a_second_ladder`，不要在 `_kb_search` 里再写一套 if。

未动（本单邻域外）：

- `tool_result_budget.MAX_EVIDENCE_DETAIL_CHARS=240` / `MAX_OBSERVATION_CHARS=900`：模型上下文压缩层，对所有工具生效。V3 改的是工具层 `AgentEvidence.detail`（审计 ledger 拿全量）。抬 240 会改变所有工具的上下文预算，不是本单。
- kb tool_result telemetry 落盘：归 V7，本单不重复实现。

## 3. TDD 红绿

文件：`intelligence/tests/test_kb_search_coarse_pipe.py`。

红（实现前，解释器 `.venv-workbench`，cwd 本 worktree）：

```
FFFFF
test_same_query_delivery_chars_beat_legacy_800_cap     assert 800 > 800
test_max_hits_and_detail_chars_are_configurable        AttributeError: KB_SEARCH_MAX_HITS
test_jcet_replay_delivers_body_not_half_url_or_path_line  assert 5 == 6
test_legacy_160_truncation_is_not_the_default_pipe     detail == excerpt[:160]
test_delivery_limits_do_not_invent_a_second_ladder     AttributeError: kb_search_delivery_limits
5 failed in 0.58s
```

绿（实现后）：同文件 5 passed；连同 `test_agent_research.py` 共 36 passed。

## 4. 变异击杀

先把实现提交，再在已提交树上把 `kb_search_hit_text` 退回 `excerpt[:160]`（`git checkout --` 对未提交树是删除器）。击杀清单见提交后补录的 §4.1。

## 5. 复算命令

```bash
cd /Users/a77/fwp-wt-v3-kbsearch-coarse-pipe

# TDD
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_kb_search_coarse_pipe.py

# 长电夹具（不跑 live RAG）
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import date
from intelligence.services import agent_research
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
hits=json.loads(Path('intelligence/tests/fixtures/v3-kbsearch-jcet-hits.json').read_text())['hits']
class R:
    telemetry=SimpleNamespace(status='ok', warning='')
    def __init__(self, h): self.hits=[SimpleNamespace(**x) for x in h]
tools=agent_research.build_default_tools(lambda *_a, **_k: R(hits))
ctx=agent_research.AgentToolContext(ResearchDeadline.from_timeout(20.0), lambda: False, InformationCutoff(date(2026,8,21),'requested'))
ev, obs, _=tools['kb_search']('长电科技怎么看', ctx)
legacy=sum(len((h.get('excerpt') or '')[:160]) for h in hits[:5])
print('n', len(ev), 'legacy', legacy, 'new', sum(len(i.detail) for i in ev))
print('hit1_has_q1_report', '长电科技2026年一季报' in ev[0].detail)
print('hit3_not_path_only', ev[2].detail.strip() != '- \`raw/cninfo-baseline/长电科技.json\`')
"

# live RAG 重放（需 worker；~20–40s；索引会漂，只作人工对照）
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
from intelligence.services import kb_rag
res=kb_rag.retrieve('长电科技怎么看','/Users/a77/knowledge-base-private/wiki',k=6,excerpt_chars=200,timeout=60)
print('hits', len(res.hits), 'llm_total', res.telemetry.llm_evidence_total_chars)
[print(i, h.title, 'ex', len(h.excerpt or ''), 'llm', len(h.llm_evidence or '')) for i,h in enumerate(res.hits,1)]
"
```

## 6. 不做什么

- 不改选段算法（形状 IV / V5）。
- 不主张答案 KB 引用密度（live，验收方 + V7）。
- 不改 `tool_result_budget` 的 240/900。
- 不写 kb telemetry 字段（V7）。
- 不把 remaining <15s 做成送达字符降档。
