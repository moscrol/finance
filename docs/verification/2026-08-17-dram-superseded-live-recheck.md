# DRAM 靶降桶探针 live 复验（落盘上下文级）

日期：2026-08-17 23:07 CST
roadmap_ref：L1-8792
前序：#146 → 长电靶覆盖为零 → #149 更正 → 本单（handoff `2026-08-17-dram-superseded-live-recheck.md`）
性质：live 验证。**未改 `intelligence/`、未改 prompt、未动 8792。**

## 0. 结论

1. **证据侧已打通（一手，落盘上下文级）**：`use_llm=True` 收据里的 `prepared_synthesis_messages[1]`（user，25891 字）含 `⚠️已被新证据取代` **4 次**（两条 stale 边各出现在证据清单 + claim 注册表）。可 `grep`，不是从答案正文反推。
2. **标注侧仍为零（预期）**：`tier_note_present=false`，`claim_id=` 0，`structured_claim_count=0`。prompt 教学门禁，#146 设计内豁免。
3. **建议题会打空**：handoff 建议的「长鑫科技的收入规模和 DRAM 国产替代进展怎么看」锚到 `长鑫科技`（5 条全 active），`get_evidence` 对 target **精确相等**，题面带「DRAM」≠ target=`DRAM`。本发 live 题面改为恰好 `DRAM`。
4. **模型处置**：见了 stale 标记。招股书 508 亿被写成「已被上市新证据取代，只能作历史参照」；现用事实走 07-27 上市口径（8.66 / 660 亿 / 3.3 万亿）。华西 07-24 的 2776.90 等数字**没进上下文**（证据行 `evidence[:80]` 截断），模型只复述了定性「一体化龙头」。

证据等级：**落盘上下文级**（非 `trace.jsonl`）。trace 化探针（另一单）未交付，走 handoff 优先级 B。

## 1. 现场

| 项 | 值 |
|---|---|
| 8792 | `877e1f721e05` / dirty=false / match=true / **未切未重启** |
| 探针树 | `~/finance-workspace-runtime` → 同 SHA 快照 |
| lock | `/tmp/finance-8792-live.lock` 不存在 |
| grounded | `WORKBENCH_GROUNDED_PRESENTER=0`（marker lane） |
| 题 | `DRAM`（不是建议的长鑫句，理由 §3） |
| 墙钟 | 180.0s（合成段 telemetry 16.1s / glm-5.2 / zhipu） |
| 诊断 | `accepted` / `validated` |
| 脚本 | `~/.finance-runtime/claim-tiering-20260817/run_live.py` sha256 `75d82bb3659550f8b75b813c87121f92a9b6b02cefc84afe0707fb298564fb76` |

收据：

- `~/.finance-runtime/claim-tiering-20260817/live-dram-superseded.json` sha256 `56a04d9d9ce55064187dc5b7c54d9781da7de6665086a02e09f114bd012fefc1`
- `~/.finance-runtime/claim-tiering-20260817/live-dram-superseded.messages.json` sha256 `2bbff0e1cfdc41328e399d5061119e47dbeb85ccd1d3a425b5c0304a0362b301`（96649 字节）
- 预扫 `~/.finance-runtime/claim-tiering-20260817/preflight-dram.json`

## 2. 一手：上下文里的 stale 边

对 `prepared_synthesis_messages` 全文 `grep`「⚠️已被新证据取代」命中 4。落盘原文（user 段，截断仅此处展示）：

```
- [candidate] DRAM：2026-05-18 长鑫招股书细化：26Q1收入508亿(+719%)、归母247.62亿(+1688%)，26H1预计归母500-570亿（[[晚间卖方研报20260518]], 2026-05-18, 质量 medium ⚠️已被新证据取代）｜证据=R6
- [candidate] DRAM：华西计算机长鑫科技深度：国产DRAM研发设计制造一体化龙头，…2025年扭亏为盈；AI算力（[[晚间卖方研报20260724]], 2026-07-24, 质量 medium ⚠️已被新证据取代）｜证据=R7
```

同文件还有 `stale_notes` 通道：`DRAM 该条证据已被取代，新证据：DRAM||2026-07-24|[[晚间卖方研报20260724]]|…只能作历史参照`。

| 针 | prepared | 终稿 |
|---|---|---|
| `⚠️已被新证据取代` | 是（4） | 否 |
| `晚间卖方研报20260518` | 是 | 否 |
| `晚间卖方研报20260724` | 是 | 否 |
| `508` | 是 | **是**（带「已被取代」限定） |
| `2776.90` | **否** | 否 |

`2776.90` 不在上下文：`collect_evidence_index` 把 `evidence` 截到 80 字，华西营收数字在截断之后。这不是模型没看见数字，是**检索装配没把数字送进去**。

## 3. 建议题为什么不能当靶

`get_evidence`（`intelligence/adapters/knowledge.py`）`item.get("target") != target` 精确匹配。`collect_evidence_index` 的 targets = `anchor.entity` + `matched_theme` + **query 全文** + 图谱公司名。

建议题「长鑫科技的收入规模和 DRAM 国产替代进展怎么看」预扫：

| 项 | 值 |
|---|---|
| anchor | 长鑫科技（688825），概念暴露含 DRAM |
| matched_theme | null（07-15 题材候选 50 条无 DRAM） |
| 实际 targets | `长鑫科技`、query 全文 |
| 长鑫科技 top-8 | 5 条，**0 superseded** |
| DRAM top-8 | 7 条，**2 superseded**（05-18 / 07-24） |

题面带「DRAM」只保证字符串出现，不保证 `get_evidence('DRAM')` 被调用。本发改用 query=`DRAM` 之后，options.query 自身即 target，7 条（含 2 条 stale）进 cap-8。

这是 #149 截断问题之外的**第二条可达性裂缝**：富证据宿主被 top-8 挡住；精确 target 又让「题面点到概念名」够不着概念宿主上的 stale 边。

## 4. 模型处置（终稿，修订版）

修订轮因盘面新鲜度 WARN 回灌，不是降桶门禁（`revision_trigger=null`）。

长鑫段原句：

> 更早的招股书口径显示 26Q1 收入 508 亿（+719%）、归母 247.62 亿，但该条已被上市新证据取代，只能作历史参照。华西证券深度报告称其为研发设计制造一体化龙头，覆盖 DDR/LPDDR 并布局 HBM——这一条同样属研报观点，待公司正式披露验证。

对照：

- **复读旧数**：508 / 247.62 进了终稿，但立刻降成历史参照（跟 stale_notes 文案同向）。
- **新证据指针**：用了 07-27 上市实况（发行价 / 募资 / 市值），这是 DRAM 宿主上仍为 active 的那条，不是 07-24 华西营收预测。
- **缺口**：明确写盘面停在 07-15、上市后走势缺失。
- **未做**：没写 2776.90（上下文里没有）；没出 `（待核验：所据证据已被取代或证伪）`；没写 claim marker。

## 5. 遥测（as-is）

| 字段 | 值 |
|---|---|
| `structured_claim_count` | 0 |
| `unbound_claim_line_count` | 14 |
| `full_markers_in_output` | 0 |
| `tier_note_present` | false |
| `revision_trigger` | null |
| warnings | 无市场数据（快照 07-15）；AnswerSpec 绑到其他题材；质检新鲜度 WARN 已回灌 |

## 6. 不做什么

- 不改 `max_evidence`、不改 prompt、不切 8792。
- 不把「508 进了终稿」写成降桶失败——模型看见了取代标记并降成历史参照；降桶标注文案本单不验收。
- 不把建议题打空写成 DRAM 宿主 top-8 失败——那是精确 target，交给 top-8 截断决策材料那单并记。
