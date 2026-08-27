# 输入侧排查：KB 检索暗资产与无取证缺口声明（2026-08-21）

> 上游：收口 R1 spec（#300）交付后的下一段 trace diff——输出侧闸门（W1/W2 在修）之后，按封上限框架排查**输入侧证据供给链**（检索召回 → 证据选择 → 截断 → 组装）。
> 方法：**假缺检测**——拿答案里声明的「证据缺口」逐条对 KB 实际在场性验证。真缺=数据覆盖问题；假缺=供给链封上限实锤。
> **结论：两个形状实锤，其中一个改写此前归因（chain_mapping 案「KB 无链路证据」不成立）。**

## 1. 形状 I：取证计划的选择性盲区（KB 授权但计划不引导 → 系统性零调用）

### 读数

对 2026-08-21 trace diff 全部案例 run 扫 `contract.allowed_capabilities` / `contract.evidence_plan.requirements` / `outcome.traces[].capability`：

| run | 题形 | KB 授权 | 计划含 KB | KB 实调 |
|---|---|---|---|---|
| `run_20260821_165210_889002`（减肥药） | 板块发酵 | ✅ | ❌ | ❌ |
| `run_20260821_164659_624916`（CXO B 臂） | 板块发酵 | ✅ | ❌ | ❌ |
| `run_20260821_152044_472523`（CXO A 臂） | 板块发酵 | ✅ | ❌ | ❌ |
| `run_20260821_171744_929436`（钙钛矿） | 板块发酵 | ✅ | ❌ | ❌ |
| `run_20260821_171744_955225`（皇氏集团） | 个股走势复盘 | ✅ | ❌ | ❌ |

**5/5**：`kb_search`/`evidence_search` 在 `allowed_capabilities` 里躺着，`evidence_plan.requirements` 只列盘面+新闻（market_data/mainline_context/market_timeseries/market_midterm/news_search），模型顺计划走完即交稿——**KB 沉淀（概念图谱、链路角色、研报上下文、L1–L3 证据分层）对这些题形贡献为零**。

全局对照（近 5 日有工具调用的 94 个 run）：24 个调过 KB 检索（26%），集中在个股深挖/估值题形——**盲区是题形×计划选择性的，不是通道坏了**。

### 后果实证：chain_mapping 案归因更正

tracediff 文档与收口 R1 spec §W2 曾写「KB 无该题材链路证据」→ 三约束联立无解。**实查不成立**：

```bash
python3 /Users/a77/knowledge-base-private/scripts/query_relations.py graph --concept 钙钛矿 --top 3
# → 奥特维(688516, 上游设备, related, 市占率60%+理由)、捷佳伟创(300724, 整线设备, related)、
#   京山轻机(000821, 涂布/层压, related) —— 带 role/strength/reason，正是 chain_mapping 需要的角色数据
```

KB **有**钙钛矿链路证据；死格真因 = 计划不引导 KB 检索、模型够不着。**这属形状 I（供给通道），不是形状 B（供给不存在）**。spec §W2 已按此修订（见 spec「验收方修订」段）：静态预检基准从「KB 存量」改为「本次供给通道」；钙钛矿案改属新拆的 W2b（通道打通）；W2a 重放案例换成减肥药（KB 概念层实测零节点，见 §2——真·无证据题材）。

### 为什么这是封上限（三筛）

模型越强，越能利用图谱角色/历史研报上下文写出有据的产业链分析——计划盲区把这部分能力的分子直接归零。且它与 W4（预算结构）耦合：KB hybrid 检索在预算紧张时还会被降级 BM25（在途 plan `2026-08-20-retrieval-tier-by-remaining-budget`），即便通道打通，供给质量也被预算压着——修计划盲区时必须带预算账（这正是当初计划可能不含 KB 的原因，打通前要先量一次 KB 检索的耗时分布）。

## 2. 形状 II：负面断言无取证义务（缺口声明在零查证下做出）

减肥药 run 公开稿声明「缺公告级证据」。实查该 run 全程零 KB 调用——声明是在**没查过知识库**的情况下做出的。恰好 KB 里减肥药概念层确实是零节点（`graph --concept 减肥` 无命中、`evidence --theme 减肥药` 0 条；公司层仅翰宇药业 2025-08 RWA 等旧证据）——**这次真缺撞对了**。但机制上：换一个 KB 覆盖好的题材（光刻机/钙钛矿这类），同样的零查证声明就是**假缺**——把库里躺着的证据说成不存在。

这与本仓「负面断言先查在场性」纪律（判官侧已有）是同一个母形状在**答案层**的显影，也是 BUILD.md「结论携带成立条件」的反例：缺口结论的成立条件（至少查过一次/预检过在场性）没有被要求。

**修法方向（并入 R-20260821-11 判据，不单独开行）**：缺口声明必须区分「库无」与「未查」——查过且无 → 可以声明「知识库无 X」；没查 → 只能声明「本轮未检索知识库」。机械可判（有无 kb_search/evidence_search 调用收据），圈给 harness。

## 3. 不在本轮范围（诚实边界）

- **top-8 / `[:80]` 截断层**（08-17 已有两条线索：长电 34 条证据 top-8 挤出 superseded、华西 2776.90 被 `[:80]` 截断）：需要在**有 KB 调用**的 run 上观察，本批案例 run 全零调用无从验证。下一段排查目标，样本池 = 上述 24 个有 KB 调用的 run。
- KB 检索的召回/精度质量（检索到 ≠ 检索得好）：同上，依赖有调用的样本。
- `evidence_plan` 按题形生成的完整规则（哪些题形含 KB、设计动机）：本单只取证了「结果形状」，生成逻辑留给 W2b 立项时点查。

## 4. 台账

- 立 `R-20260821-11`（形状 I + II 合并立案，对应 W2b）：见 `docs/prediction-ledger.md`。
- 钙钛矿案归因更正已回写 spec §W2（验收方修订段）；tracediff 文档原文不改（保留历史现场，本文档是更正指针）。

## 5. 复算命令

```bash
# 5/5 零调用
python3 -c "
import json
for p in ['probe-ledger-0821/runs/run_20260821_165210_889002','probe-ab-0821-post/runs/run_20260821_164659_624916','probe-tracediff-0821/runs/run_20260821_152044_472523','linxiaoqi5111/runs/run_20260821_171744_929436','linxiaoqi5111/runs/run_20260821_171744_955225']:
    d=json.load(open(f'/Users/a77/.local/share/finance-workbench/users/{p}/continuous-episode.json'))
    caps=[t.get('capability') for t in d['outcome']['traces']]
    reqs=[r.get('capability') for r in d['contract']['evidence_plan']['requirements']]
    print(p.split('/')[-1], 'kb_allowed=', 'kb_search' in d['contract']['allowed_capabilities'], 'kb_planned=', any(c in('kb_search','evidence_search') for c in reqs), 'kb_called=', any(c in('kb_search','evidence_search') for c in caps))
"
# 钙钛矿 KB 在场性（改写归因的关键证据）
python3 /Users/a77/knowledge-base-private/scripts/query_relations.py graph --concept 钙钛矿 --top 3
# 减肥药 KB 真无（W2a 替换重放案例的依据）
python3 /Users/a77/knowledge-base-private/scripts/query_relations.py evidence --theme 减肥药 --top 5
```
