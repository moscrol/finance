# top-8 截断下的 stale 提醒走旁路，不占检索名额

2026-08-18 用户拍 **D**（`stale_notes` 旁路）。检索 `max_evidence=8`、adapter 排序（active 前 superseded 后）、prompt、#146 降桶闸判据全部不动；`collect_evidence_index` 在截断外按 target 另扫已被取代 / 已证伪边，每个 target 至多一行提醒进分歧反证桶。详见 `docs/superpowers/specs/2026-08-17-stale-evidence-quota-decision.md` 与执行单 `docs/handoffs/2026-08-18-stale-notes-bypass-implementation.md`。

---

## 实测（2026-08-17 23:10 账本）

默认 top-8 加上「active 永远排在 superseded 前面」，让证据越丰的宿主提醒越够不着：文件级 9 宿主里只有 DRAM / mSAP / 电子特气 3 个稀疏宿主进得了窗；长电第一条 superseded 排第 33。overlay 软回链再加 9 个富宿主，limit=8 下同样 0 条。#146 的 `invalidated` 态检索侧默认丢掉，闸结构性走不到。

## 考虑过的替代

| 选项 | 为何不选 |
|---|---|
| A 维持现状并写进文档 | 正当的「不改」。代价是长电这类被问得多的公司永远看不见「2024 营收已被年报顶掉」。 |
| B 名额制 ≤1 | 覆盖宿主，但 6 个富宿主各挤掉第 8 条 active；MLCC 挤掉的是 2026-07-01 国巨涨价。已被取代行还会进证据链，`ask_synthesis` 可能铸成 `base:fact`。留给「就是要 live 压 #146 闸」的下一单，且必须另做质量序。 |
| C 抬 `max_evidence` | 12 对文件级零增益；24 仍无长电还加税；50 才全覆盖，还要追写死的 `[:8]`。副作用最大，收益最差。 |
| **D 旁路（已决）** | 名额零挤占；提醒进 gap 不是证据链；公司配额填满也不饿死题材 target。闸仍不响——D 是提醒，不是闸覆盖。 |

## 后果

- 旁路按 target 直查，不带 `company_evidence_concepts` 过滤键（#153/#157）。
- 两态对齐：文件 `superseded`、overlay 软改写、以及默认丢掉的 `invalidated` / overlay 硬回链都扫。
- 窗内已出现的 superseded（DRAM 那 2 条 ⚠️）不重复计进提醒行。
- 不铸 EvidenceAtom，不切 8792，不改 launcher。
