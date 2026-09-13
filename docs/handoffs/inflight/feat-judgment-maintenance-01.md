# feat/judgment-maintenance-01 交接

## 这个分支做什么
研究进化批次 01：judgment_maintenance 复核台账（纯函数、无 IO）——复核调度、supersedes 链、结果回写。spec `docs/superpowers/specs/2026-09-13-research-evolution-01-05-specs.md` §01；进度 `docs/superpowers/plans/2026-09-13-research-evolution/01/PROGRESS.md`；交 06 的接线诉求在同目录 `BLOCKED.md`。

## 决策与被否方案
- 同 ref 哈希更新按「同生效起点（valid_from/known_day）+ 更晚记录 + 不同哈希」判隐式替代，旧记录永久退场进 ended；否了「同 ref 一律替代」（会误杀 valid_from 不同的另一版有效期安排，控制测试 test_unsuperseded_sibling 锁此语义）。
- 否了改 retired_refs 全局语义：只加同 ref 隐式 supersedes 分支，跨 ref 显式 supersedes_ref 路径不动。

## 当前状态
- QC 第二轮修复 `d1a514ee`（J2[P1] 同 ref 哈希复活）已提交，树干净。
- 背景：QC 第二轮（`~/.finance-runtime/reviews/research-evolution-repair-qc-20260913/`）确认原 13 项固定反例转绿，扩大边界后确证 8 项，本轨占 1 项（J2），已修。
- **06 联测请用新 SHA `d1a514ee`**（不是上轮的旧 SHA）。

## 已验证
- 模块测试 99 passed（含新增 2 条 J2 回归，先红后绿）；ruff 干净。
- QC 探针 `spec_010204_probes.py` J2 组复跑转绿（探针断言 HEAD=固定修后 SHA，提交前复跑有效）。

## 未验证 / 已知边界
- 未与 02/04/05 的新 SHA 做跨轨联测（06 的职责）。
- 隐式替代只覆盖「同生效起点」形状；同 ref 不同 valid_from 的哈希轮换仍按多版本有效期处理（设计如此）。

## 下一步
- 等 06 用 `d1a514ee` 联测；用户确认后才谈合并 main（合前跑全仓等价 CI）。

## 踩过的坑
- 报告 id / 项 id 全由内容派生：改判定规则必须 `JM_FIXTURES_UPDATE=1` 重生成夹具并把 diff 一起送审。
- 输入侧未知字段会被拒绝（不是忽略）；06 造 `EvidenceVersion` 时 `source_hash` 必填，缺 `recorded_at` 降档不报错。
- 工作树没有 venv：解释器用主树 `.venv-workbench/bin/python`。
- 上轮口头汇报称「13 项已修复」——准确口径是「原 13 项固定反例转绿」，扩大边界后 QC 又确证 8 项。写结论区分「固定反例集转绿」与「无缺陷」。
- 交接里引用的 `docs/superpowers/summaries/2026-09-13-*.md` 从未落盘，总结以本文件与 commit message 为准。
