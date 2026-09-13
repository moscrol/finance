# feat/judgment-maintenance-01 交接

## 这个分支做什么
研究进化批次 01：judgment_maintenance 复核台账（纯函数、无 IO）——复核调度、supersedes 链、结果回写。进度 `docs/superpowers/plans/2026-09-13-research-evolution/01/PROGRESS.md`；交 06 的接线诉求在同目录 `BLOCKED.md`。

## 决策与被否方案
- 同 ref 哈希更新按「同生效起点 + 已证明的严格更晚记录（instant_of 真实时刻）+ 不同哈希」判隐式替代；否了「同 ref 一律替代」与「哈希序兜底当先后」。
- 否了改 retired_refs 全局语义：只加同 ref 隐式 supersedes 分支，跨 ref 显式 supersedes_ref 路径不动。
- J6/J8/J9：日历日全链走 `market_day_of`（折算东八区再取日）——known_day、expired_at、条件观测过滤、绑定 created_day 四处同源。
- J7/J10：「current 是最新版」必须能对每个同生效起点竞争者证明（不可比或同刻即 ambiguous_version_order）；歧义进项身份（仅歧义时加键，无歧义字节不变），unchanged 早退与末端去重都不得吞歧义——同 id 冲突留 open 项。

## 当前状态
- QC 第五轮修复 **`8127283d`**（J8 条件观测越截止、J9 绑定提前成立、J10 歧义被去重丢掉——本轮新回归）已提交，树干净。
- 背景：QC 二至五轮原固定反例均转绿，扩大边界累计确证 21 项，本轨占 9 项（J2–J10）均已修。证据 `…/reviews/research-evolution-round5-qc-20260913/`。
- **06 联测请用 `8127283d`。**

## 已验证
- 模块 108 passed（J2–J10 回归均先红后绿）；全量 9648 passed / 77 skipped（干净树 @8127283d，`-rf` 无失败）；ruff 干净。
- QC 第五轮安全断言 5 passed（4 缺陷钉 + 1 合法对照）；第一至四轮归档探针 01 组复跑不回归（输出与 QC 归档归一身份字段后逐字节一致）。

## 未验证 / 已知边界
- 未与 02/04/05 的新 SHA 做跨轨联测（06 的职责）。
- 同 ref 不同 valid_from 的哈希轮换按多版本有效期处理（设计如此）；纯日期 / naive recorded_at 不造精确先后，但会触发 ambiguous_version_order。
- dedup_key 形状变了（歧义时加键）：与修复前报告/台账里同一问题的旧 key 不匹配，回写侧按新 key 开项——语义正确（歧义项确是新状态），但 06 联测时留意台账衔接。

## 下一步
- 等 06 用 `8127283d` 联测；用户确认后才谈合并 main（合前跑全仓等价 CI）。

## 踩过的坑
- 报告 id / 项 id 全由内容派生：改判定规则必须 `JM_FIXTURES_UPDATE=1` 重生成夹具并把 diff 一起送审。
- 输入侧未知字段会被拒绝（不是忽略）；06 造 `EvidenceVersion` 时 `source_hash` 必填，缺 `recorded_at` 降档不报错。
- 汇报口径要区分「固定反例集转绿」与「无缺陷」（上轮误报「13 项已修复」）。
- 交接里引用的 `docs/superpowers/summaries/2026-09-13-*.md` 从未落盘，总结以本文件与 commit message 为准。
