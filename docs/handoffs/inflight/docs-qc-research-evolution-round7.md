# 四轨第七轮 QC

## 这个分支做什么
独立复核第六轮修复，扩大执行实例/动作边界；不改四轨实现、不合 main。

## 决策与被否方案
- 原反例通过不外推成完整成本已验证；费用须按任务×执行尝试×组件核验，否了任务级类别并集代签。
- 失败不等于模型没调用；否了凭终态豁免，也否了一律强要未发生的 review。
- J12 旧动作继承留给 06 产品决定；新复现项动作次日有效已核验。
- 详细发现/对照/取舍：`docs/handoffs/2026-09-14-research-evolution-round7-qc.md`。

## 当前状态
报告与可执行反例已提交 `a9bfb977`。四轨锁定 01=6cc5748a、02=e27b3352、04=fcc7838c、05=b6b7c596，均干净；未 push、未合并。
原 J11/J12/PV10 通过；05 仍阻签：PV11/P1 同任务跨成功 attempt 代签模型费；PV12/P1 全失败工具费清掉 retry 缺账；PV13/P2 uncovered_components 在公开输出丢失。前两项修前也复现，属相邻遗漏。

## 已验证
- 模块 110+65+74+115=364 passed；01/05 全仓 ruff 绿。
- round4/5 安全断言 9 passed；round6 6 passed。
- round7 4 failed/4 passed：PV11 两例、PV12、PV13 红；J12 五节点线性链/次日重扫与新 snooze、费用齐全对照绿。
- 原全量收据核验：a3cf9d4b=9650P/77S，cf7e05a5=9655P/77S，dirty=false、exit=0；最终 SHA 只加文档。
- 耐久原始证据：`~/.finance-runtime/reviews/research-evolution-round7-qc-20260914/`（manifest 含 SHA/哈希）。

## 未验证 / 已知边界
本轮未重跑全量，未逐个重跑第一至三轮归档；未在 06 合成候选测四叶门禁与旧动作继承产品语义。四轨单测不等于集成验收。

## 下一步
05 修执行实例覆盖与公开缺口明细，再跑原回归+round7；01/02/04 继续作为 06 候选。06 决定旧动作是否继承并联测，合 main 等用户确认。

## 踩过的坑
外部测试目录的 pytest 收据会绑定报告树 revision；实际被测四轨以 probe JSON sha/manifest 为准。新诊断字段要断言公开输出，内部列表存在无效。领域断言已落仓；通用手法进 agent-memory，脏 harness-reference 未动。
