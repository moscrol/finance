# 投研基础补强 spec · 2026-09-08

## 这个分支做什么
把时间真实性、方法验证、运行时恢复、研究上限整理成可拆工单的设计：`docs/superpowers/specs/2026-09-08-research-foundation-optimization-design.md`（OPT-01…11）。只写设计，不动代码、不同步数据。

## 决策与被否方案
- 在现有事实库/快照/标签/收据/runtime 接缝上补合同；否了重建中台、堆提示词与回测次数。展开见 spec §2。
- L2、晚间卖方、晨汇按用户确认占位（纠偏 `27947017531c`）；否了判无源或同步失败，不启动同步。
- 实验固定方法与拟合产物，各窗口可用不同日期快照；否了跨规则版本或内部未校正结论拼接晋升。
- durable 写失败即停派发；本地意图去重不等于外部效果只发生一次，未知结果先对账。
- 09-08 晚用户「执行」：终稿与 `6e4adee8` 逐字节一致，只刷新交接；否了当场拆 A 阶段工单——OPT-02/06/07/08 的对象层已有在途单（见下一步），先对照再拆。

## 当前状态
spec `6e4adee8`，分支 `docs/research-foundation-optimization`，基线 gitea/main `f90af450`（09-08 晚 fetch 仍是它，免 rebase）。树干净、未推送、未合并、未切流。

## 已验证
- 用户回贴的终稿覆写后 `git diff` 为空。
- 7 条相对链接本树全可达（含 runtime-base endstate——它在 main 上，主检出 `b4a35fa2` 树里没有）。
- pre-commit 对 spec+本文件全 Passed（文档检查，非功能验收）。
- 纠偏 `27947017531c` 实在 `user_space().root/corrections.jsonl`，ts 2026-09-08T14:50Z。

## 未验证 / 已知边界
源码审查钉在 f90af450；当时 8792 health 为 `0060da5c`，不是同一实现。PIT/lifecycle 反例为内存复现，未做生产中断演练、未跑模型回测。三项占位未定补齐窗口。

## 下一步
1. 用户拍板后推送开 PR 到 main（纯文档）。
2. 实施前先对照分支 `docs/closeout-workorders-0908`（cherry +4，未合）：#35 river.window ↔ OPT-02、#34 ContextProjection ↔ OPT-07、#37 情景树 ↔ OPT-06、#38 runtime-base P0–P2 合并切流（P3 已合 #677，P4 #31 在途）↔ OPT-08、#40 数据洞 ↔ OPT-11。
3. OPT-01 内容版本 PIT、OPT-03 状态门、OPT-04 认证、OPT-05 相关样本尚无在途单，A 阶段从这四项拆起。

## 踩过的坑
主检出树有他人未提交的 09-05/09-06 spec 与 BP，本树从 gitea/main 独立建立；对齐时逐条移植，不整文件覆盖。主检出 `inflight/HEAD.md` 是别人的 BP 交接，本分支只写本文件。无可迁移脚本：本轮全是一行 shell 的单点核对。
