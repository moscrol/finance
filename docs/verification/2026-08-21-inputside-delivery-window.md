# 输入侧排查第二段：KB 送达窗——瘦管道、词频绑架、同族挤占（2026-08-21）

> 上游：`2026-08-21-inputside-kb-dark-asset.md`（形状 I/II：调用层——KB 授权但计划不引导）。本单排查**送达层**：当 kb_search 真的被调用时，模型面前那扇窗有多大、装的是什么。
> 样本：近 5 日 31 条 kb/evidence tool_result 形状扫描 + 「长电科技怎么看」高频 query（9 次调用）重放 diff + 液冷/陶瓷纤维目测。
> **结论：三个形状实锤。病灶排序与直觉相反——送达内容质量（词频绑架+同族挤占）的伤害大于截断量本身。**

## 1. 口径链（生产代码实测）

```
kb_rag.retrieve(k=wiki_rag_k=6, excerpt_chars=wiki_rag_excerpt=200)   ← ask_types.py 默认
  → agent_research._kb_search: hits[:5]                               ← 硬编码（掐第 6 条）
  →                 detail=(hit.excerpt or "")[:160]                  ← 硬编码（每条再掐 40 字符）
送达 agent：5 条 × 160 字符 = 800 字符/次；observation 实测 300–500 字符
```

- 31 条 tool_result 里 kb_search 的 evidence **恒等于 5 条**（复算命令 §5）。
- **无深读通道**：12 个注册工具里没有「按 file_path 读页面全文」的能力，kb_search 是 agent loop 唯一 KB 文本入口——检索窗即天花板。对照：Cursor 直调（trace diff 的 A 臂）检索后必读命中文件全文。

## 2. 形状 III：三消费口径不一致，最高频入口拿最瘦管道

检索栈自带粗管道：`WikiHit.llm_evidence`（per-hit 预算 + `apply_total_llm_budget` 总预算 8000 字符，`kb_rag.py`）。消费方核查：

| 消费口 | 管道 | 实测单次送达 |
|---|---|---|
| `evidence_search.py`（415/494 行） | `llm_evidence or display_excerpt or excerpt` | 12 条，observation 3635 字符 |
| `evidence_providers.py`（1127/1181 行） | `llm_evidence or excerpt` | —（主链/预取路径） |
| **`agent_research._kb_search`（366 行）** | **仅 `excerpt[:160]`** | **5 条，observation ~470 字符** |

粗管道存在且同栈两处在用，唯独 agent loop 的 KB 文本入口没接。**这不是「检索能力不够」，是「装配差一根管子」。**

## 3. 形状 IV：excerpt 选段被 query 词频绑架

「长电科技怎么看」重放（hybrid ok、6 命中，§5 命令可复算）逐条看送达内容：

| # | 命中页 | excerpt 实际内容 | 信息量 |
|---|---|---|---|
| 1 | 长电科技_最新逻辑跟踪（**最载荷相关页**） | 来源清单头部+半个 URL（`[:160]` 切在 URL 中间） | ≈0 |
| 2 | 长电科技（600584）实体页 | 页首「一句话」结论段 | **高**（唯一高质量送达） |
| 3 | 2025年度报告 baseline | `- raw/cninfo-baseline/长电科技.json`（一行内部路径） | 0 |
| 4 | 颀中科技 | `[[长电科技]] · [[通富微电]] · …`（wikilink 堆） | 0 |
| 5 | 华天科技 | 同上 wikilink 堆 | 0 |
| 6 | 莱宝高科（被 `[:5]` 掐掉） | wikilink 堆 | 0（这次掐得不冤） |

机制：excerpt 取自命中 chunk（`display_excerpt/snippet/evidence_text`，非页首），而 BM25/向量对这类 query 的最佳 chunk 常是 **query 词密度最高段**——来源清单、wikilink 链接区、路径行，恰恰是信息密度最低的区域。逻辑跟踪页的真正结论段（不反复出现公司全称）反而排不进。**6 条送达里 4 条零信息，最该读的页送达半个 URL。**实体页幸存是因为页首恰好是结论段（结构巧合，不是机制保证）。

## 4. 形状 V：top-K 无同族折叠 + 验收工件页在知识索引里

液冷服务器题（`run_20260820_032014_595378` 等）第一跳 kb_search top-5：

```
液冷服务器产业新变化与新格局全面分析报告   ← 知识正文（仅此 1 条）
液冷服务器-theme-radar-验收 / -v5 / -v6 / -v7 ← 4/5 是验收工件页
```

theme-radar 验收页（v5–v8 多版本）是**测试产物**，高度同质，检索必然连坐命中；top-5 窗被同族挤满，有效密度 1/5。两个独立病：① 检索层无同族折叠（same-prefix/same-page-family 去重）；② **验收工件页根本不该进知识索引**（索引排除规则的卫生问题，比检索端去重更根本）。

## 5. 复算命令

```bash
# 恒 5 条扫描
python3 -c "
import json,glob
for p in sorted(glob.glob('/Users/a77/.local/share/finance-workbench/users/*/runs/run_*/continuous-episode.json')):
    if p.split('/runs/')[1][:12] < 'run_20260817': continue
    try: d=json.load(open(p))
    except: continue
    for e in d.get('events',[]):
        pl=e.get('payload',{})
        if e.get('kind')=='tool_result' and pl.get('tool') in('kb_search','evidence_search'):
            print(pl['tool'], len(pl.get('evidence') or []), len(pl.get('observation') or ''))
"
# 长电 query 重放（需 rag worker；~38s）
cd /Users/a77/finance-workspace-private && KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki .venv-workbench/bin/python -c "
from intelligence.services import kb_rag
res=kb_rag.retrieve('长电科技怎么看','/Users/a77/knowledge-base-private/wiki',k=6,excerpt_chars=200,timeout=60)
[print('---',h.title,'|',(h.excerpt or '')[:160]) for h in res.hits]
"
# 口径链行号：agent_research.py:358 hits[:5]、:366 [:160]；kb_rag.py llm_evidence/apply_total_llm_budget；
# evidence_search.py:415,494 与 evidence_providers.py:1127,1181 用 llm_evidence（kb_search 未用）
```

## 6. 诚实边界

1. 重放用**当前** KB 索引，与历史 run 当时的索引版本可能有版本差（送达 titles 与 run 工件一致，差异不影响形状结论）。
2. 零信息 excerpt 的量化只详查了长电 1 个 query（6 条）+ 液冷/陶瓷纤维目测；「4/6 零信息」是单 query 读数，不是全库比率。形状 IV 的普遍性依据是机制（词频选段）+ 三题同形，非大样本统计。
3. `[:5]` 掐掉的第 6 条在长电案恰好无伤害——形状 III 的主张是「瘦管道+口径不一致」，不是「[:5] 必然丢关键证据」。
4. 遥测缺口：kb tool_result 的 `telemetry` 字段落盘为空 dict，检索内部召回数/截断量/送达率**不可回读**——W5 传感器建议补「kb_search 送达字符数/条数」计数（见台账行）。
5. 修法全部**另行立项**：粗管道接入（_kb_search 改用 llm_evidence）动 agent 上下文预算，须带预算账（W4 已证预算紧张常态）；索引排除验收工件页动知识库仓 ingest/索引规则（跨仓）；同族折叠动检索排序。三者互相独立可分批。
