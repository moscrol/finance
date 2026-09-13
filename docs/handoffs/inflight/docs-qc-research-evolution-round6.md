# docs/qc-research-evolution-round6

## 这个分支做什么
独立审查第五轮修复后的 01/02/04/05，只交反例与报告，不改候选、不合 main。

## 决策与被否方案
- 原固定反例转绿≠扩大边界无缺陷；保留有效全量收据，不以新反例否认旧测试。
- 用纯函数公开入口确定性复现，否了启动生产/UI：问题在领域合同内即可证伪。
- J12 旧管理动作复活仅列语义风险，不单列 P1；替代链成环可独立判错。细节见 `docs/handoffs/2026-09-13-research-evolution-round6-qc.md`。

## 当前状态
报告与自动反例已提交 `b12b613c`。仍阻断：PV10/P1（有 run 任意费用核销缺模型账）、J11/P2（绑定解析仍截字符串取日）、J12/P2（歧义消解产生替代环）。未 push/合并。
固定候选：01 d39b011e、02 e27b3352、04 fcc7838c、05 dd3e8ad0；四轨干净。
证据：`~/.finance-runtime/reviews/research-evolution-round6-qc-20260913/`（manifest/修前后输出/日志/收据）。树 `/tmp/research-evolution-r6-qc-fgmhNt/{01,02,04,05,report}`。

## 已验证
- 原第五轮 5 passed、第四轮 4 passed。
- 新安全断言 5 failed/1 passed，对应 3 根因，费用合法正负控绿。
- 模块 01=108、02=65、04=74、05=114 passed；四轨全仓 ruff 绿。
- 归档 01/02-timezone/04/04-boundary/05-extra exit=0。
- 核对全量收据：9648/77@8127283d、9654/77@340d3b26，dirty=false/exit=0/failed_ids=[]。

## 未验证 / 已知边界
本次未重跑全量 pytest、未跑 06/API/UI 联测。J12 旧 snooze 在末态重新 applied、open 1→0 已实测；是否应继承旧管理动作待明确，不能仅靠 assess 数量断言端到端保留。

## 下一步
01 修 J11/J12；05 修 PV10；02/04 保留候选。用 RESEARCH_EVOLUTION_QC_ROOT 指向四个检出树，跑 docs/verification/research-evolution-round6/test_round6.py，修后应 6 绿，再交 06 旧 key/动作衔接与集成验收。

## 踩过的坑
- 内容状态键不等于历史节点身份；同键末态替换旧态会留下反向边成环。
- 按 run 有任意费用≠该 run 每个模型组件有账；跨任务类别覆盖不能代签。
- 日期使用端与准入验证器必须同源。
- 本次误调不存在 standards_02_probe.py；改实际 standards_02_timezone_probe.py 后绿。旧错误日志保留，非产品失败。
