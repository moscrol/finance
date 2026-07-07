# 复盘推演回检台账

这里放"盘后推演 -> T+1 回检 -> 用户批注 -> 经验沉淀"的人类可读台账。

## 台账入口

| 研判日 | 观察视角 | Markdown | HTML |
|---|---|---|---|
| 2026-07-02 | 站在 2026-07-01 盘后，前瞻 2026-07-02 | [2026-07-02.md](2026-07-02.md) | [2026-07-02.html](2026-07-02.html) |
| 2026-07-02 双盲并排对比 | Claude vs Codex 同题对照 | — | [对比页](../../复盘/daily/2026-07-02/dual-blind-compare-2026-07-02.html) |
| 2026-07-01 | 站在 2026-06-30 盘后，前瞻 2026-07-01（已闭环） | [2026-07-01.md](2026-07-01.md) | [2026-07-01.html](2026-07-01.html) |
| 2026-06-30 | 站在 2026-06-29 盘后，前瞻 2026-06-30（已闭环） | [2026-06-30.md](2026-06-30.md) | — |

## 文件结构约定

- 每天一个 `YYYY-MM-DD.md`，含 **Codex 答卷（§1-6）+ Claude 答卷（§6.5，双盲）+ T+1 回填（§7）+ 用户批注（§8）**。
- 每天一份输入冻结清单 `YYYY-MM-DD.manifest.json`（答卷前由 `scripts/dual_blind_forecast.py manifest` 生成），每个考生一份机器可读答卷 `YYYY-MM-DD.answer.<agent>.json`（`validate` 校验、`aggregate` 跨期聚合）；流程见 [双盲模板](../dual-blind-forecast-template.md)。
- 盘后验证结果唯一机器可读落点 `YYYY-MM-DD.verdict.json`（`verdict` 子命令校验后写入，逐假设 hit/miss/partial/unverifiable）；`index` 子命令重建下方机检状态总表。`YYYY-MM-DD.md` 的回检表由 verdict 渲染，不再手填。全部台账的位置见 [台账地图](../ledger-map.md)。
- 双盲纪律：两 Agent 同源数据、独立答卷、互不可见；考生不做对比/批注/裁决（归用户 + 统一指标）。
- 单次样本留此；反复有效的方法论再升级到经验卡或 Agent Memory。
- 历史单文件台账（迁移前）见 `archive/daily-market-forecast-ledger.legacy.md`。

<!-- BEGIN AUTO dual-blind-status 本表由 dual_blind_forecast.py index 生成，勿手改 -->

## 机检状态总表（脚本生成）

| 研判日 | manifest | 答卷 | 答卷校验 | 验证 | 命中率（hit/已裁定） |
|---|---|---|---|---|---|
| 2026-07-06 | ✅ | claude, codex | claude:✅ codex:✅ | — | — |
| 2026-07-02 | ✅ | claude, codex | claude:✅ codex:✅ | ✅ | claude:3/8 codex:1/12 |

<!-- END AUTO dual-blind-status -->
