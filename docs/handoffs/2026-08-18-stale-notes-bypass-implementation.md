# Handoff：实施方案 D——`stale_notes` 旁路提醒行（top-8 截断 × stale 提醒，已裁决）

日期：2026-08-18
roadmap_ref：L1-8792（决策队列 2026-08-18「已决 D」行）
裁决：**用户已拍 D**（2026-08-18 00:39）。A/B/C 不做；B 若将来要压 #146 闸另开单。
前序：#146（降桶标注）→ #149（更正：长电靶被 top-8 截断）→ #151（决策材料，含全部量化数）→ 本单
决策材料：`docs/superpowers/specs/2026-08-17-stale-evidence-quota-decision.md`（方案定义、数据、边界全在里面，**先读它再动手**）
复算脚本：`docs/verification/2026-08-17-stale-evidence-quota-scan.py`（只读，可重跑核对账本现状）

## 1. 一句话

检索 top-8 名额一格不动；在 `collect_evidence_index` 截断之外**另扫**每个 target 的已被取代/已证伪边，往 gap（分歧反证桶）写至多一行提醒：「{target} 有 {n} 条证据已被取代；最近新证据：{最新指针}」。让长电科技这类富证据宿主的用户也能看见「2024 营收已被年报顶掉」，而不把旧数塞进证据链。

## 2. 实现边界（材料 §6 拍过的，不要越）

- **只动**：`intelligence/services/evidence_providers.py` 里 `collect_evidence_index` 的遍历来源与 `stale_notes` 组装。若旁路扫描需要 adapter 支持（如拿到被默认丢弃的 `invalidated`），可在 `intelligence/adapters/knowledge.py` 加**只读**入口（如 `include_invalidated=True` 的调用或独立 `get_stale_edges`），不改既有排序与默认行为。
- **不动**：`AskOptions.max_evidence`、adapter 既有排序（active 前 superseded 后）、prompt、#146 闸判据（`_STALE_EVIDENCE_PERIODS`）、`ask_synthesis` 的 `[:8]`、`ask_blocks` 的窗口帽。
- **不铸 EvidenceAtom**：D 是提醒，不是闸覆盖。降桶闸的 live 压测归另一单（材料 §5 留给 B）。
- 提醒行进 `stale_notes` → 现网它汇入 `gap_lines` →「分歧反证」段（`ask.py` 现有消费，`build_quality_context` 已兼容，不需要新桶）。

## 3. 规格

1. **扫描范围**（两态对齐，材料 §3.6）：文件级 `status=superseded`、overlay 软回链改写、**以及** `get_evidence` 默认丢掉的 `invalidated` / overlay 硬回链。只顾 superseded 一态不验收。
2. **粒度与预算**：每个 target 至多 1 行；行内容 = 已被取代边数 + 最新一条新证据指针（`superseded_by` 或 overlay 目标）。单行目标 80–180 字，撞上 `_evidence_text_for_llm` 的单条 360 字帽也装得下，不需要改帽。
3. **不带概念袋过滤**：旁路扫描按 target 名直查账本，**不要**把 `company_evidence_concepts` 的绑定概念当过滤键带进去——那是 #153/#157 刚踩过的坑，概念袋治理归 `docs/handoffs/2026-08-18-concept-bag-filter-design.md` 那单，别搅。
4. **去重**：某边已经通过 top-8 进了证据行（DRAM 这类稀疏宿主，行尾带 ⚠️已被新证据取代），同一 target 的提醒行不重复计它；全部 stale 边都已在窗内时不出提醒行。
5. **多 target**：按 target 逐个扫（anchor、theme、query、图谱公司同待遇），公司配额填满不影响题材 target 的提醒——这是 D 相对抬 limit 的核心优势（材料 §4 第二层封杀行），要有测试钉住。

## 4. 测试（先红后绿，模板照 #157 的 `CollectEvidenceIndexAnchorTests`）

1. **长电科技**（富宿主，现状 0 提醒）：修后 `stale_notes` 含长电行，指针指向 2026-04-08 年报 baseline；top-8 证据行与修前逐条相同（名额零挤占）。
2. **DRAM**（稀疏宿主回归）：2 条 superseded 已在 top-8 窗内，⚠️行为不变，提醒行不重复报这两条。
3. **MLCC 反例钉死**：修后 top-8 第 8 条 active（2026-07-01 国巨涨价）仍在——这是当初否掉 B 的理由，拿它当「没有变相名额制」的断言。
4. **invalidated/overlay-hard**：合成 fixture（或真实账本里风华高科 hard 命中）能出提醒行，证明两态对齐。
5. **多 target 不饿死**：公司 target 填满 8 格后，题材 target 的提醒行仍产出。
6. 字符预算断言：单行 ≤ 允许上限；无 stale 边的 target 零输出。

## 5. live 复验（合并后，走 #152 的官方探针，不碰 8792）

```sh
test ! -e /tmp/finance-8792-live.lock
cd <合并后 main 检出>
PYTHONPATH=$PWD /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/live_probe.py ask "长电科技的营收规模怎么看" --slug stale-note-changdian --repo-root "$PWD"
```

验收看一手（`evidence_grade=llm_context`，不从答案正文反推）：

- `<slug>/llm_context.json` 里 grep 到长电的提醒行（「已被取代」+ 新证据指针）；
- 同文件 R 证据链 286.69 仍在（#157 不回退）；
- 提醒行落在分歧反证/gap 段，不在证据链段；
- 收据与路径写进 PR。8792 全程 `877e1f72` 不动。

## 6. 门禁与流程

- 新活从 `gitea/main` 开分支；PR 走 Gitea API（token：`security find-generic-password -s gitea-local -a a77-token -w`）。
- 合并前四件套：ruff + 全量 pytest + `intelligence/webapp` pnpm lint/typecheck/test/build，`umask 022`。
- **跑 pytest 前摘干净启动器变量，只留 `PATH` 和 `KNOWLEDGE_WIKI`**——`PYTHONPATH` 指运行时快照会混树导入（2026-08-17 夜已踩：假红 19 条那类全是它）。
- 台账：PR 内更新 `docs/handoffs/inflight/main.md`（一行，含收据路径）；roadmap 决策队列「已决 D」行不用再动。
- **补 ADR**：`docs/adr/0003-stale-notes-bypass.md`，记录 D 的裁决与被否方案（材料 §4/§5 摘要即可）——材料 §8 说好拍板后补记，落在本单。

## 7. 红线

- 不切 8792，不改 launcher。
- 不动 `max_evidence` / adapter 排序 / prompt / #146 闸判据；不铸 stub atom。
- 提醒行不得进「证据链」段，不得被 `ask_synthesis` 铸成 `base:fact`（那正是 B 被否的原因）。
- 结论落盘可复算：测试 + live 收据 + 台账，不接受口头绿。
