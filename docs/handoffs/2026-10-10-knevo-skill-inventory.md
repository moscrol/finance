# knevo 专项补齐与机制清单：决策、被否方案与踩坑（2026-10-10 快照，写完不改）

分支 `feat/knevo-skill-inventory-1010`，基 Pi 线 `fix/knevo-pi-runtime-1010` HEAD `708411e7d`。接续 `docs/handoffs/inflight/feat-knevo-skill-inventory-1010.md`。

## 决策与被否方案

| 选择 | 否了什么 | 理由 |
|---|---|---|
| 基于 Pi 线 HEAD 开枝 | 基于 `6c1` 再加同名文件 | 同路径不同内容合并必冲突；Pi 线（用户派的 Pi agent）当时仍在改 market-review 与 finance-mode |
| 新专项独立文件 + 新测试文件 | 改 `test_knevo_skill_layer.py` 的清单 | Pi 线可能同时改锚句 |
| `finance-earnings-review` 并入 `finance-analyze-stock`、`finance-industry-report` 并入 `finance-industry-track` | 照 knevo 九篇一比一 | 同对象窄切面用同一专项减少路由歧义；report↔track 接力需要同一文件；两套骨架都保留 |
| finance-mode 的待并入项只写进清单 §1 / §4 | 直接改 OS skill | OS 当前由 Pi 线持有（表达阶段逐句对齐在进行） |
| knevo 阈值数字一律改「按本仓台账定」 | 照抄审查偏差百分比、有效期天数 | 量纲是它的；运行时 skill 不写数字（契约测试拦） |

## 来源

44 轮原文 `agent-memory/60_dialogues/knevo/2026-08-08-工具编排与step上限-44轮原文.md`：finance-mode L1365–1716；analyze-stock L1743–1832；earnings-review L1877–1922；industry-report L1926–1972；industry-track L1976–2010；forecast-event L2069–2150；kol-analyze L2154–2222；review-check L2226–2305；associate L2311–2373。
机制抽取子 agent（2026-10-09 深夜）通读全部材料后的表与矛盾清单，已落 `docs/superpowers/specs/2026-10-10-knevo-mechanism-inventory.md`。

## 踩过的坑

- 运行时 skill 正文不能有数字型阈值（`\d+%`、`\d+亿`、六位代码会被契约测试拦）。
- `build_registry.py backfill-tables` 给新 skill 插的是「（待补：SKILL.md 无触发词字段）」占位行，要手工改成「无触发词：运行时专项…」再 `--check`。
- 提交钩子 `handoff-budget` 拦新 inflight 超 3000 字节：展开写到本快照，inflight 只留指针。
- Pi 的 knevo review-check 原文骨架没有 🎯 核心结论（以 Review Verdict 一行收口），契约测试要为它单独豁免。
- 真实首发前树必须干净（runner `require_clean_code`），所以先提交再跑。
