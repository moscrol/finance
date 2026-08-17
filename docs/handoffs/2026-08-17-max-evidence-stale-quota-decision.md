# Handoff：top-8 截断 × stale 边可达性——出决策材料，不改行为

日期：2026-08-17 晚
roadmap_ref：L1-8792（决策队列 2026-08-17 更正行）
前序：#146（降桶标注）→ #149（更正：长电靶 stale 边被截断未入上下文）
本单性质：**只产出决策材料，不改 `intelligence/` 代码；裁决归用户**

交付（2026-08-17 23:10）：材料已落 `docs/superpowers/specs/2026-08-17-stale-evidence-quota-decision.md`；复算脚本 `docs/verification/2026-08-17-stale-evidence-quota-scan.py`；决策队列已挂「材料就绪待裁决」，owner=`用户`。

## 0. 一句话

`max_evidence=8` 的 top-8 截断让富证据宿主的「已被取代」提醒机制（⚠️标记、新证据指针、#146 降桶标注、`llm_fact_only_superseded_evidence` 门禁）**结构性够不着**。量化这件事、列出方案与利弊、给推荐——改不改、怎么改由用户拍板。

## 1. 机制事实（2026-08-17 实测，含代码坐标）

- `collect_evidence_index`（`intelligence/services/evidence_providers.py:526`）对每个 target 调 `ctx.knowledge.get_evidence(target, limit=options.max_evidence)`，`AskOptions.max_evidence` 默认 **8**；adapter 排序 active 优先。
- **截断发生在循环之前**：排在 top-8 外的 superseded 边，连 `bundle.stale_notes`（「已被新证据取代，新证据：…」那条通道）都进不去——不是「进了但没标」，是整条边不存在于本轮证据。
- KB 现状（`$KNOWLEDGE_WIKI/relations/evidence_index.json`，19581 条 / 20 条 superseded / 9 个宿主）：

| 宿主 | 总证据 | superseded | top-8 内 |
|---|---|---|---|
| DRAM | 7 | 2 | **2** |
| mSAP | 3 | 1 | **1** |
| 电子特气 | 6 | 1 | **1** |
| CPU | 21 | 1 | 0 |
| 中船特气 | 15 | 1 | 0 |
| 明阳智能 | 17 | 1 | 0 |
| MLCC | 22 | 6 | 0 |
| 电子布 | 22 | 5 | 0 |
| 长电科技 | 34 | 2 | 0 |

规律：**证据越丰，stale 提醒越够不着**——而富证据宿主恰恰是被问得多的主流标的。复扫脚本（KB 会演化，出材料前重跑）：

```sh
set -a; . <(grep '^export ' /Users/a77/.local/bin/start-finance-workbench | sed 's/^export //') >/dev/null 2>&1; set +a
cd ~/finance-workspace-runtime
PYTHONPATH=$PWD /Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
import os, json
from intelligence.adapters.knowledge import KnowledgeAdapter, evidence_status
ka = KnowledgeAdapter(os.environ['KNOWLEDGE_WIKI'])
d = json.load(open(os.environ['KNOWLEDGE_WIKI'] + '/relations/evidence_index.json'))
items = d if isinstance(d, list) else list(d.values())[0]
hosts = sorted({i.get('target') for i in items if isinstance(i, dict) and i.get('status')=='superseded'})
for t in hosts:
    for lim in (8, 12, 16, 24, 50):
        top = ka.get_evidence(t, limit=lim).get('items') or []
        n = sum(1 for it in top if evidence_status(it)=='superseded')
        print(t, lim, len(top), n)
"
```

## 2. 要产出的数据（材料的骨架）

1. 可达性 vs limit 曲线（8/12/16/24/50），逐宿主。
2. 每宿主的 stale 边排位（active 优先排序下它们实际排第几）。
3. 名额制反事实：若 top-8 强留 ≤1 条 stale（带新证据指针的优先），每个宿主被挤掉的那条 active 是什么、损失多大。
4. token 成本：stale 边入围平均增加多少上下文字符（stale 边带「新证据：…」后缀，比 active 长）。
5. 顺手核对：`evidence_status` 对 `invalidated` 的处理是否与 `superseded` 同路（#146 判据 `_STALE_EVIDENCE_PERIODS` 是两态，检索侧别只顾一态）。

## 3. 方案空间（至少评这四个，可加）

- **A. 维持现状**：接受「stale 提醒只覆盖稀疏宿主」，把这条语义写进文档。零成本，语义诚实但覆盖窄。
- **B. stale 名额制**：top-N 保留 ≤1 个 stale 槽（有新证据指针者优先）。覆盖直接拉满，代价是挤掉一条 active + 每题多几十 token。
- **C. 抬 max_evidence**：一刀切扩容。副作用最大（所有题上下文变长、与 tool_result_budget/超时预算联动），大概率不推荐，但要给数据而不是拍脑袋。
- **D. stale_notes 旁路**：检索名额不动，另起短通道只带「X 已被取代，新证据：Y」一行。改动面在 `collect_evidence_index` 的遍历来源（要在截断前扫 stale），并需查 `build_quality_context` 对 `stale_notes` 的消费方式是否兼容。

每方案给：覆盖变化（用 §2 数据）、token/预算代价、与 #146 门禁及降桶标注的联动、实现面大小。**给一个明确推荐及理由**，但把「不改」保留为正当选项。

## 4. 验收（可判定）

1. 一份材料文档落 `docs/superpowers/specs/2026-08-XX-stale-evidence-quota-decision.md`（或 `docs/verification/`，按内容偏设计还是偏实测选），含 §2 全部数据、§3 利弊矩阵、推荐。
2. `docs/roadmap.md` 决策队列加一行「材料就绪待裁决」，标 `用户`（参考 2026-08-16「10 题窗仍等…」那行的写法——待裁决行的 owner 列写 `用户` 不写 `已决`）。
3. **不改 `intelligence/` 任何代码**；docs-only 薄账 PR（先例 #148/#149），ruff 过即可。
4. 材料里的每个数字可复算（附命令或脚本路径）。

## 5. 纪律红线

- 基线从 `gitea/main` 开分支（本机旧 `main` 落后几百个提交）；`gh` 不可用，PR 走 Gitea API（token：`security find-generic-password -s gitea-local -a a77-token -w`）或网页 http://localhost:3300 。
- 不动 8792；只读 KB 与代码，重扫脚本是只读的。
- 若忍不住想顺手改代码：停——那是另一单，材料批了才开。
