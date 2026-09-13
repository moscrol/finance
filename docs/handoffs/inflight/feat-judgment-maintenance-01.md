# feat/judgment-maintenance-01 交接

## 这个分支做什么
研究进化批次 01：judgment_maintenance 复核台账（纯函数、无 IO）——复核调度、supersedes 链、结果回写。spec `docs/superpowers/specs/2026-09-13-research-evolution-01-05-specs.md` §01；进度 `docs/superpowers/plans/2026-09-13-research-evolution/01/PROGRESS.md`；交 06 的接线诉求在同目录 `BLOCKED.md`。

## 决策与被否方案
- 同 ref 哈希更新按「同生效起点 + 已证明的严格更晚记录（instant_of 真实时刻）+ 不同哈希」判隐式替代；否了「同 ref 一律替代」与「哈希序兜底当先后」。
- 否了改 retired_refs 全局语义：只加同 ref 隐式 supersedes 分支，跨 ref 显式 supersedes_ref 路径不动。
- J6/J7：日历日一律 `market_day_of`（先折算东八区再取日，expired_at 同）；「current 是最新版」必须能对每个同生效起点竞争者证明——任一方说不出精确时刻或同刻不同哈希即 ambiguous_version_order，且 unchanged 早退不得吞歧义（仍建 open 项、epistemic unknown）。

## 当前状态
- QC 第四轮修复 **`cfd88c04`**（J6 市场日折算、J7 不可比时刻留歧义、J5-补充 歧义不被 unchanged 吞）已提交，树干净。
- 背景：QC 二至四轮原固定反例均转绿，扩大边界累计确证 17 项，本轨占 6 项（J2/J4/J5/J6/J7/J5-补充），均已修。第四轮证据 `~/.finance-runtime/reviews/research-evolution-round4-qc-20260913/`。
- **06 联测请用 `cfd88c04`。**

## 已验证
- 模块 104 passed（J2/J4/J5/J6/J7 回归均先红后绿）；全量 9644 passed / 77 skipped（干净树 @cfd88c04）；ruff 干净。
- QC 第四轮探针 01 组三项全绿 + 安全断言 test_adjacent.py 4 passed；第一/二/三轮归档探针 01 组复跑不回归。

## 未验证 / 已知边界
- 未与 02/04/05 的新 SHA 做跨轨联测（06 的职责）。
- 隐式替代只覆盖「同生效起点 + 精确时刻可比较」形状；同 ref 不同 valid_from 的哈希轮换仍按多版本有效期处理（设计如此）。
- 纯日期 / naive recorded_at 不造精确先后，但会触发 ambiguous_version_order（J7）——不再静默定序。

## 下一步
- 等 06 用 `cfd88c04` 联测；用户确认后才谈合并 main（合前跑全仓等价 CI）。

## 踩过的坑
- 报告 id / 项 id 全由内容派生：改判定规则必须 `JM_FIXTURES_UPDATE=1` 重生成夹具并把 diff 一起送审。
- 输入侧未知字段会被拒绝（不是忽略）；06 造 `EvidenceVersion` 时 `source_hash` 必填，缺 `recorded_at` 降档不报错。
- 工作树没有 venv：解释器用主树 `.venv-workbench/bin/python`。
- 上轮口头汇报称「13 项已修复」——准确口径是「原固定反例集转绿」，扩大边界后 QC 累计确证 17 项。写结论区分「固定反例集转绿」与「无缺陷」。
- 交接里引用的 `docs/superpowers/summaries/2026-09-13-*.md` 从未落盘，总结以本文件与 commit message 为准。
