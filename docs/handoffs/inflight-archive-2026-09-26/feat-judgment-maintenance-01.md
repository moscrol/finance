# feat/judgment-maintenance-01 交接

## 这个分支做什么
研究进化批次 01：judgment_maintenance 复核台账（纯函数、无 IO）——复核调度、supersedes 链、结果回写。进度 `docs/superpowers/plans/2026-09-13-research-evolution/01/PROGRESS.md`；交 06 的接线诉求在同目录 `BLOCKED.md`。

## 决策与被否方案
- 同 ref 哈希更新按「同生效起点 + 已证明的严格更晚记录（instant_of 真实时刻）+ 不同哈希」判隐式替代；否了「同 ref 一律替代」与「哈希序兜底当先后」。
- 否了改 retired_refs 全局语义：只加同 ref 隐式 supersedes 分支，跨 ref 显式 supersedes_ref 路径不动。
- J6/J8/J9/J11：日历日全链走 `market_day_of`（折算东八区再取日）——known_day、expired_at、条件观测过滤、绑定 created_day 使用端与 parse_binding 校验端同源。
- J7/J10/J12：「current 是最新版」必须能对每个同生效起点竞争者证明（不可比或同刻即 ambiguous_version_order）；歧义进项身份（仅歧义时加键）；复现节点拿独立 id（A→B→A 不成环），unchanged 早退与末端去重都不吞歧义。

## 当前状态
- QC 第六轮修复 **`a3cf9d4b`**（J11 绑定解析端市场日、J12 复现节点独立身份消环）已提交，树干净。
- 背景：QC 二至六轮反例均转绿，本轨 11 项（J2–J12）均已修。证据 `…/research-evolution-round6-qc-20260913/`。
- **06 联测请用本分支 HEAD。**

## 已验证
- 模块 110 passed（回归均先红后绿）；全量 9650 passed / 77 skipped（干净树 @a3cf9d4b，`-rf` 无失败）；ruff 干净。
- QC 第六轮断言 6 passed；第一至五轮归档探针复跑不回归（归一身份后与归档逐字节一致）。

## 未验证 / 已知边界
- 未与 02/04/05 新 SHA 跨轨联测（06 的职责）。
- J12：旧 snooze/close 绑历史节点 id，不作用于复现 open 项（实测 rejected、open=1）——06 验收项见「下一步」。
- 纯日期 / naive recorded_at 触发 ambiguous_version_order；dedup_key 歧义时加键，与修复前台账旧 key 不匹配（06 留意衔接）。

## 下一步
- 等 06 联测；用户确认后才谈合并 main（合前跑全仓等价 CI）。
- **06 明确验收项（QC round-11）**：A → 歧义 B → 复现 A，分别带旧 snooze、close——查完整处理后的 rejected、复现项 open=1、历史链与界面反馈，不只看 assess 的 open 数；是否继承旧动作需产品裁决。

## 踩过的坑
- 报告/项 id 全由内容派生：改判定规则必须 `JM_FIXTURES_UPDATE=1` 重生成夹具并送审 diff。
- 输入侧未知字段会被拒绝（不是忽略）；06 造 `EvidenceVersion` 时 `source_hash` 必填，缺 `recorded_at` 降档不报错。
- 汇报口径要区分「固定反例集转绿」与「无缺陷」（上轮误报「13 项已修复」）。
- 交接里引用的 `docs/superpowers/summaries/2026-09-13-*.md` 从未落盘，总结以本文件与 commit message 为准。
