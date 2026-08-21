# V2 缺口声明取证义务 + V1 第一阶段 KB 通道计划（2026-08-22）

> 规格：`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md` §V1 / §V2
> 台账：`R-20260821-14`（V2，judged pending；live 由验收方回填，本单不得 confirmed）
> V1 映射代码与 `R-20260821-13` **本单不立**——经验收方确认题形表后再写
> 分支：`feat/v2-gap-proof-v1a-kb-plan`（worktree `/Users/a77/fwp-wt-v1v2-kb-plan`，基线 `gitea/main=5d4a3684`）
> 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
> 本轮未打 live 探针、未碰 8792/8803

## 0. 一句话

V2：公开稿里「缺公告级证据 / 库无 / 暂无」按本轮 `provider=agent:kb_search|agent:evidence_search` 二分——零调用改成「未查证」限定，有查证未命中才允许「库无」。
V1 第一阶段：量了 `kb_rag.retrieve` 三档耗时，并枚举 `contract.question_type` 给出「该不该含 KB requirement」提案。不改 `resolve_evidence_plan`。

---

## 1. V2 TDD 红绿

文件：`intelligence/tests/test_kb_gap_proof.py`（8 钉）。
实现：`episode_answer_hygiene.py` 的 `kb_gap_claim_kind` / `rewrite_unverified_kb_gap_claims`；`episode_semantic_verifier` 在 unattempted-claim 改写后接 `_apply_kb_gap_proof_rewrite`。
called 口径与 V7 钉 `test_shape_i_called_uses_provider_not_capability` 一致：**看 provider，不按 capability 分组**（成功路 capability 是 `agent_loop`）。

命令（cwd 本 worktree）：

```
git rev-parse --short HEAD
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_kb_gap_proof.py --tb=short
```

### 红（实现前，`5d4a3684`）

```
5d4a3684
读数收据: /Users/a77/.finance-runtime/test-receipts/20260821T173831Z-5d4a3684.json

==================================== ERRORS ====================================
___________ ERROR collecting intelligence/tests/test_kb_gap_proof.py ___________
ImportError while importing test module '/Users/a77/fwp-wt-v1v2-kb-plan/intelligence/tests/test_kb_gap_proof.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
intelligence/tests/test_kb_gap_proof.py:17: in <module>
    from intelligence.services.episode_answer_hygiene import (
E   ImportError: cannot import name 'find_unverified_kb_gap_claims' from 'intelligence.services.episode_answer_hygiene' (/Users/a77/fwp-wt-v1v2-kb-plan/intelligence/services/episode_answer_hygiene.py)
=========================== short test summary info ============================
ERROR intelligence/tests/test_kb_gap_proof.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.30s
```

### 绿（实现后，提交前仍在 `5d4a3684` dirty）

```
........                                                                 [100%]
读数收据: /Users/a77/.finance-runtime/test-receipts/20260821T173930Z-5d4a3684.json
8 passed in 0.41s
```

实现提交：`15e4d8ec`。相邻 `test_episode_answer_hygiene.py` + `test_mandatory_satisfiability.py` 合计 35 passed，未碰 W2 satisfiability / `_repair` / `skills.registry.json`。

---

## 2. V2 变异击杀

基线提交 `15e4d8ec`（实现已在树上）。把 `kb_gap_claim_kind` 改成恒返回 `"库无"`（二分判据删掉、全部当库无），然后：

```
FFF..FF.                                                                 [100%]
读数收据: /Users/a77/.finance-runtime/test-receipts/20260821T174500Z-15e4d8ec.json

=================================== FAILURES ===================================
/Users/a77/fwp-wt-v1v2-kb-plan/intelligence/tests/test_kb_gap_proof.py:111: AssertionError: assert '库无' == '未查证'
/Users/a77/fwp-wt-v1v2-kb-plan/intelligence/tests/test_kb_gap_proof.py:119: AssertionError: assert '未查证' in '板块在发酵，但缺公告级证据，无法确认订单落地。'
/Users/a77/fwp-wt-v1v2-kb-plan/intelligence/tests/test_kb_gap_proof.py:127: AssertionError: assert '未查证' in '知识库无该题材公告级证据，产业链角色无法落格。'
/Users/a77/fwp-wt-v1v2-kb-plan/intelligence/tests/test_kb_gap_proof.py:159: AssertionError: assert '库无' == '未查证'
/Users/a77/fwp-wt-v1v2-kb-plan/intelligence/tests/test_kb_gap_proof.py:166: AssertionError: assert '未查证' in '板块在发酵，但缺公告级证据，无法确认订单落地。'
=========================== short test summary info ============================
FAILED intelligence/tests/test_kb_gap_proof.py::test_zero_kb_call_is_unverified_kind
FAILED intelligence/tests/test_kb_gap_proof.py::test_zero_kb_call_qualifies_announcement_gap
FAILED intelligence/tests/test_kb_gap_proof.py::test_zero_kb_call_must_not_keep_assertive_absent
FAILED intelligence/tests/test_kb_gap_proof.py::test_capability_name_without_kb_provider_is_unverified
FAILED intelligence/tests/test_kb_gap_proof.py::test_public_answer_zero_kb_has_unverified_qualifier
5 failed, 3 passed in 0.21s
```

击杀清单：恒「库无」会红掉「kind 二分」「缺公告级限定」「断言性库无改写」「capability 冒充 provider」「公开稿零调用」五钉。三条「有查证未命中 → 允许库无」保持绿——它们本来就要走「库无」支。

`git checkout -- intelligence/services/episode_answer_hygiene.py` 后 8 passed（收据 `20260821T174509Z-15e4d8ec.json`）。

---

## 3. V2 行为与诚实边界

- 判定本轮是否调过 KB：`trace.provider ∈ {agent:kb_search, agent:evidence_search}` 且 `_attempted`。`capability=kb_search` 但 provider 不是这两个，不算查证。
- 零调用：断言性「缺公告级证据 / 知识库无 / 知识库暂无 / 库无 / 暂无公告级」改写为带「未查证」的句子，并去掉断言动词「知识库无/暂无」。
- 有查证（含 `result_count=0` 的未命中）：原文「库无/暂无」保留。
- W2 的 `CHAIN_MAPPING_KB_GAP`（「知识库暂无该题材产业链证据」）由 `ensure_preplaced_gap_sections` 在 adapter 缝进公开稿，**本单不改 satisfiability、不改该常量、不改 adapter**。那是静态 relations 预检的另一条取证通道，不是本轮 `kb_search` 收据。
- 修稿路径 `_repair` 未接本改写（禁区）。若修复轮新写出断言性缺口且不再走 hygiene，属已知边界。

---

## 4. V1 前置：KB 检索耗时分布

对照 R-10：成稿轮残值 median **13s**；未合 plan / 已合代码 `select_mode_for_remaining`：remaining < 15s → 检索 mode 降 BM25。

量测协议（生产等价，不是冷进程）：

- `KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki`
- `RAG_WORKER_ENABLED=1` + `kb_rag.prewarm`（生产 8792 是 1；worker 关着每次新进程重载模型，会虚高）
- `HF_HUB_OFFLINE=1`，`timeout=90`（避免被 15s 档误降），`k=6`，`excerpt_chars=200`
- 题目 22 条，全部来自台账近期案例（减肥药 / CXO / 钙钛矿 / 皇氏 / 长电 / 液冷 / 锂矿 / 光刻机 / PCB / 莲花控股 / 太辰光 / 固态电池 / 低空经济 / 商业航天 / 电网设备 / 创新药 / 算力PCB / 3D打印钛合金 / 中际旭创 / 宁德时代 / 光伏 / 动力电池），每档 n=22≥20
- 三档：`bm25` / `dense`（向量）/ `hybrid`；`effective_mode` 与请求一致，fallback=0，22/22 ok，协议 `persistent_worker`

### 4.1 主表（wall clock = `kb_rag.retrieve` 整段，含 llm_evidence）

| 档 | n | ok | p50 (s) | p95 (s) | mean | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| **bm25** | 22 | 22 | **10.26** | **45.21** | 14.90 | 6.35 | 58.60 |
| **dense**（向量） | 22 | 22 | **5.92** | **7.63** | 5.56 | 1.88 | 11.14 |
| **hybrid** | 22 | 22 | **17.54** | **35.31** | 19.79 | 8.50 | 46.56 |

对照：worker 关闭的单次冒烟（query=`长电科技怎么看`）bm25 16.65 / dense 11.14 / hybrid 26.98——冷进程比暖 worker 更慢，不能当生产账。

诚实拆：BM25 的 p95 被预热后前几次拖高（58.6 / 46.4 / 22.3）。去掉前 5 次后 n=17：p50≈9.8s、p95≈13.3s。dense 几乎全程稳在 2–8s。hybrid 暖机后仍常见 12–35s。

### 4.2 预算账结论（对照成稿轮残值 median 13s）

| 档 | 能否进成稿前工具轮 | 门槛 |
|---|---|---|
| **dense** | **能**（p95 7.6s < 13s） | remaining 建议 ≥10s；低于现有 15s 档本就不会走 dense |
| **bm25** | **有条件** | p50 10.3s 贴着 13s 残值；暖机后 p95≈13s 勉强。现有 `<15s → BM25` 防的是 hybrid，**不保证** 15s 授予够跑完一次 BM25（全样本 p95 45s）。映射若选 BM25，仍须 remaining 门槛，不能无条件塞 |
| **hybrid** | **不能无门槛** | p50 17.5s 已经大于 13s 残值和 15s 降档线。进工具轮必须 remaining 远大于 15s（与 retrieval-tier 已有分档对齐，不另建第二套）。成稿轮残值常态下应被降成 BM25 |

总判：不得无条件全题形加 KB。V1 第二阶段若写映射，KB requirement 必须是 **optional + 跟 `select_mode_for_remaining` 走**，禁止在 prompt 里硬塞「请调 kb_search」。

---

## 5. V1 题形枚举 + 提案（到此为止，不写映射）

### 5.1 怎么数（解析器，不数行号）

AST 扫 `intelligence/services/`：

| 源 | 数量 | 是什么 |
|---|---:|---|
| `route_table.ROUTE_TABLE` 的 `question_type` | 22 | 路由表正式取值（chat/meta/clarify 为 `None`，不进 contract） |
| `task_frame._POLICY_BY_QUESTION_TYPE` 键 | 23 | 上表 22 + 兜底 `general_finance_qa` |
| `answer_orchestrator.QUESTION_TYPES` | 18 | 分类器集合；多 `answer_review` / `market_review`，少若干路由表行 |
| `query_resolution._DETERMINED_QUESTION_TYPES` | 16 | 已判定、禁止被软解析覆盖的子集 |

**合同可见并集 25 个**（剔除误扫的 `overnight_external_premise`——那是 lane overlay 规则名，不是 `question_type`）：

`answer_review` `comparison` `comparison_analog` `concept_definition` `dated_market_review` `event_forecast` `external_market` `fact_check` `financial_analysis` `general_finance_qa` `general_knowledge` `kol_review` `market_cause` `market_forecast` `market_review` `market_technical` `market_watch` `methodology_discussion` `news_impact` `quick_fact` `stock_deep_dive` `theme_analysis` `theme_track` `trade_advice` `valuation_estimate`

现状（本单未改）：`resolve_evidence_plan` 对发酵/复盘落到 `mainline_current` 时只列盘面+新闻；`kb_search` 在 `_RUNTIME_CAPABILITY_FLOOR` 里对许多政策**已授权**（`theme_multi_layer_evidence` / `general_finance_evidence` / 公司三件套等），但**不进 `evidence_plan.requirements`**——这就是 R-11「授权躺着、计划不引导」。V1 要动的是 requirements，不是再扩授权。

V7 金标提醒：减肥药人话「板块发酵」，机器题形是 **`general_finance_qa`**，不是 `theme_analysis`。只给 `theme_analysis` 加 KB 会漏掉这条 miss-route。

### 5.2 提案表（请验收方批第二阶段）

判据列的「该不该含」= 要不要在 `evidence_plan.requirements` 里出现 KB（`kb_search` 和/或 `evidence_search`）。默认 **optional + 预算门槛**，禁止 mandatory 全开。

| `question_type` | 建议 | 判据 |
|---|---|---|
| `theme_analysis` | **应含**（spec 发酵 + 产业链） | 答案依赖图谱角色 / L1–L3 / 研报上下文。R-11 钙钛矿/CXO 三案授权未计划。optional，remaining 走 `select_mode_for_remaining` |
| `theme_track` | **应含**（发酵的持续跟踪） | 与上同类，政策已授权 KB；计划应引导一次检索看边际是否已入库 |
| `dated_market_review` | **段级应含，非整题**（spec 复盘板块归因段） | 全市场复盘主证据是盘面，整题加 KB 会挤工具槽。仅当问句有板块/题材归因（overlay，形状同 `overnight_external_premise`）才追加 optional KB |
| `market_review` | **同 `dated_market_review`** | 分类器遗留别名（`QUESTION_MARKET_REVIEW`），不是 route_table 行。第二阶段按同一 overlay，不要当新题形各写一套 |
| `market_cause` | **应含（optional）** | 板块/窗口归因常要产业/催化背景；纯指数涨跌仍以盘面+新闻为主 |
| `comparison` | **产业链问法应含**（spec 产业链） | 「A 和 B 的链路角色」需要图谱；「液冷 vs 风冷优劣」可 optional。用问句是否含产业链/公司角色作 overlay，不要整类 mandatory |
| `comparison_analog` | **optional** | 历史类比可能用到 KB 剧本/产业页；不是每题都要 |
| `stock_deep_dive` | **应含（保持引导）** | 政策已授权且全局 26% KB 调用集中于此。计划补 requirement，避免「授权了但计划没写」的同形盲区（皇氏案 planned=❌） |
| `valuation_estimate` | **应含（optional）** | 同上，估值带常引用研报/画像；主锚仍是财务口径 |
| `financial_analysis` | **默认不含** | 主证据是三表/公告。KB 研报判断不得升 L2。需要时走已有 `evidence_lookup`，不加 KB requirement |
| `news_impact` | **默认不含** | 主通道是 news / l3。KB 只在「历史订单是否入库」时 optional overlay |
| `fact_check` | **optional** | 核验说法常要 KB 证据页；mandatory 会在无库题材上制造假计划 |
| `kol_review` | **optional** | 对照已蒸馏观点/研报；不是每条 KOL 评论都值得一次 hybrid |
| `trade_advice` | **optional（走个股政策）** | owner 已是 stock-deep-dive；KB 作催化/画像补充，不得变成买卖依据 |
| `event_forecast` | **默认不含** | 未发生事件；KB 历史类比最多 overlay，不能当主证据 |
| `market_forecast` | **不含** | 主证据是盘面情景与双红序列 |
| `market_watch` | **不含** | 当日看点=盘面 |
| `market_technical` | **不含** | 点位计算，KB 无增量 |
| `quick_fact` | **不含** | 取值。政策 floor 里虽有 kb_search，计划不应引导 |
| `external_market` | **不含** | 海外行情，A 股 KB 覆盖弱 |
| `concept_definition` | **不含（现状空计划保留）** | 纯定义走 stable_knowledge；与「当前盘面」复合时已有 mainline overlay，那是盘面不是 KB |
| `methodology_discussion` | **不含** | 方法论，禁止金融数据/KB 泄漏 |
| `answer_review` | **不含** | 审回答，不是取证题 |
| `general_knowledge` | **不含** | 非金融标的，走 web |
| `general_finance_qa` | **不得无条件加** | 兜底题形。R-11 减肥药、R-08 live 都落到这里。正确修法是**先把发酵问句路由回 `theme_analysis`**，而不是给兜底加 KB（否则所有没认出来的题都会多一次 10–35s 检索） |

spec 点名三类的落点：发酵 → `theme_analysis` / `theme_track`（外加 `general_finance_qa` 的路由债）；产业链 → `theme_analysis` + `comparison` overlay；复盘板块归因 → `dated_market_review` / `market_cause` / `market_review` 的段级 overlay。

第二阶段若被批准：只改 `resolve_evidence_plan`，立 `R-20260821-13`，夹具先红后绿；禁止 prompt 硬塞调用指令。

---

## 6. 复算命令

```bash
cd /Users/a77/fwp-wt-v1v2-kb-plan

# V2 TDD
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_kb_gap_proof.py --tb=short

# 题形并集（解析器）
/Users/a77/finance-workspace-private/.venv-workbench/bin/python - <<'PY'
import ast
from pathlib import Path
root = Path("intelligence/services")

def S(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None

def dict_keys(node):
    if isinstance(node, ast.Dict):
        for k in node.keys:
            val = S(k)
            if val:
                yield val

types = set()
mod = ast.parse((root/"route_table.py").read_text())
for n in ast.walk(mod):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "RouteRow":
        for kw in n.keywords:
            if kw.arg == "question_type" and S(kw.value):
                types.add(S(kw.value))
mod = ast.parse((root/"task_frame.py").read_text())
for n in ast.walk(mod):
    target = None
    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
        target, value = n.target.id, n.value
    elif isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name):
        target, value = n.targets[0].id, n.value
    else:
        continue
    if target == "_POLICY_BY_QUESTION_TYPE":
        types.update(dict_keys(value))
mod = ast.parse((root/"answer_orchestrator.py").read_text())
for n in ast.walk(mod):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id.startswith("QUESTION_") and t.id != "QUESTION_TYPES" and S(n.value):
                types.add(S(n.value))
print(len(types), *sorted(types), sep="\n")
PY

# 耗时分布（暖 worker；约 10–15 min；勿对 8792 发请求）
HF_HUB_OFFLINE=1 RAG_WORKER_ENABLED=1 \
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python - <<'PY'
import os, time, statistics
from intelligence.services import kb_rag
wiki = os.environ["KNOWLEDGE_WIKI"]
qs = [
    "减肥药这波从月初发酵到现在怎么看","CXO概念这波怎么看","钙钛矿电池产业链怎么拆",
    "皇氏集团走势怎么看","长电科技怎么看","液冷这个题材还能不能追",
    "锂矿板块从月初发酵到 2026-07-23","光刻机产业链核心公司","PCB概念发酵复盘",
    "莲花控股怎么看","太辰光怎么看","固态电池有什么新进展",
    "低空经济这个题材还能不能追","商业航天后续怎么看","电网设备这波从月初发酵到 2026-07-23",
    "创新药板块怎么看","算力PCB","3D打印钛合金","中际旭创怎么看",
    "宁德时代估值贵不贵","光伏最近一个月有什么新变化","动力电池产业链近况跟踪一下",
]
print(kb_rag.prewarm(wiki, timeout=90))
for mode in ("bm25", "dense", "hybrid"):
    xs = []
    for q in qs:
        t0 = time.perf_counter()
        r = kb_rag.retrieve(q, wiki, k=6, mode=mode, timeout=90, excerpt_chars=200)
        xs.append(time.perf_counter() - t0)
        assert r.telemetry.effective_mode == mode
    xs.sort()
    def pct(p):
        k = (len(xs) - 1) * p / 100
        lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
        return xs[lo] * (1 - (k - lo)) + xs[hi] * (k - lo)
    print(mode, "n", len(xs), "p50", round(pct(50), 3), "p95", round(pct(95), 3))
PY
```

---

## 7. 不做什么

- 不改 `resolve_evidence_plan`，不立 `R-20260821-13`
- 不碰 W2 satisfiability / `CHAIN_MAPPING_KB_GAP` / `_repair` / `skills.registry.json`
- 不打 live 探针，不标 confirmed
- 不把 worker 关闭的冷进程读数当成生产账
