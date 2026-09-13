# feat/judgment-maintenance-01 交接

## 这个分支做什么
研究进化批次 01：judgment_maintenance 复核台账（纯函数、无 IO）——复核调度、supersedes 链、结果回写。spec `docs/superpowers/specs/2026-09-13-research-evolution-01-05-specs.md` §01；进度 `docs/superpowers/plans/2026-09-13-research-evolution/01/PROGRESS.md`；交 06 的接线诉求在同目录 `BLOCKED.md`。

## 决策与被否方案
- 同 ref 哈希更新按「同生效起点（valid_from/known_day）+ 已证明的严格更晚记录（instant_of 真实时刻）+ 不同哈希」判隐式替代；否了「同 ref 一律替代」（误杀另一版有效期安排）与「哈希序兜底当先后」（J5：同刻不同哈希只保留歧义提示，哈希序仅用于输出确定性）。
- 否了改 retired_refs 全局语义：只加同 ref 隐式 supersedes 分支，跨 ref 显式 supersedes_ref 路径不动。

## 当前状态
- QC 第三轮修复 **`dbf4d357`**（J4[P1] 时区字符串顺序复活旧哈希、J5[P2] 哈希序冒充先后——本轮新回归）已提交，树干净。
- 背景：QC 二/三轮原固定反例均转绿，扩大边界累计确证 13 项，本轨占 3 项（J2/J4/J5），均已修。第三轮证据 `~/.finance-runtime/reviews/research-evolution-round3-qc-20260913/`。
- **06 联测请用 `dbf4d357`。**

## 已验证
- 模块 101 passed（J2/J4/J5 回归均先红后绿）；全量 9641 passed / 77 skipped（干净树 @dbf4d357）；ruff 干净。
- QC 第三轮探针 J4 mixed==normalized 逐字段一致、J5 歧义提示在列；第一/二轮归档探针 01 组复跑不回归。

## 未验证 / 已知边界
- 未与 02/04/05 的新 SHA 做跨轨联测（06 的职责）。
- 隐式替代只覆盖「同生效起点 + 精确时刻可比较」形状；同 ref 不同 valid_from 的哈希轮换仍按多版本有效期处理（设计如此）。
- 纯日期 / naive recorded_at 不参与先后判断（说不出绝对时刻），只按原文兜底输出顺序——不造精确先后。

## 下一步
- 等 06 用 `dbf4d357` 联测；用户确认后才谈合并 main（合前跑全仓等价 CI）。

## 踩过的坑
- 报告 id / 项 id 全由内容派生：改判定规则必须 `JM_FIXTURES_UPDATE=1` 重生成夹具并把 diff 一起送审。
- 输入侧未知字段会被拒绝（不是忽略）；06 造 `EvidenceVersion` 时 `source_hash` 必填，缺 `recorded_at` 降档不报错。
- 工作树没有 venv：解释器用主树 `.venv-workbench/bin/python`。
- ISO 文本顺序 ≠ 时刻顺序（03:00Z 比 10:00+08 更晚）：时刻比较一律走 `instant_of`。
- 上轮口头汇报称「13 项已修复」——准确口径是「原固定反例集转绿」，扩大边界后 QC 累计确证 13 项。写结论区分「固定反例集转绿」与「无缺陷」。
- 交接里引用的 `docs/superpowers/summaries/2026-09-13-*.md` 从未落盘，总结以本文件与 commit message 为准。
