# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；开发树fwp-wt-e2-boundary-closeout，主树不动。

## 当前状态
应用301dcd9e已提交。D1/P2/P3a此前独立通过；P3b及P3c+返修现已同型号独立上下文通过，仅限本片，不是完整P3。报告/原失败/修正版/日志归档docs/verification/e2-boundary-closeout/qc-301dcd9e/；旧工具前阻塞记录保留。未推/合/部署。

## 决策与被否方案
- 能力/证据计划/输出类型同源冻结；local_only只留认证本地runner，不按cost/freshness猜IO。
- 消费者先绑registry，batch/repair重绑Scope并保留更严上限、task身份和累积诊断，不只改菜单。
- 晚结果红针是超时后二次进适配器，未产出结果。原失败保留，另存单层慢回调，原7断言全留；不改应用/超时/题目求绿。
- 快照docs/handoffs/2026-09-14-e2-p3bc-independent-closeout.md；证据py/log追加.txt但字节不变，避免误收集历史失败针。

## 未验证 / 已知边界
P3未完成：controller早读/普通context来源过滤，预取前歧义与可信基底澄清，四组九类输入、压缩/崩溃恢复/子研究/非工具事实/确定性旁路。不能撤销registry_factory内部IO。
local_only原题号槽/更多runner认证、P4逐题三态、P5可信继承旧答身份、P6材料锚点纯度、P7原始T2→T3未完成。前端/E2E未跑；RE06 I14另线。
b4ba6fb5全测首RAG迟到响应1红、同版复跑绿，未稳定复现/未归因；与本次独立晚结果探针错误不是同一事故。

## 下一步
1. 下一片先压真实run_turn里明确material_only的提前先验读取：conversation_orchestrator.py的inherited answer spec/stance/project prior/视角。先红针再改，不用工厂字段清空冒充入口零读。
2. controller摘要在frame前已送入，QueryResolver也早于边界编译；需可信前置合同与续轮方案，不把所有“继续”拦成材料澄清。再按v10推进余P3–P7，T3不得重贴禁令。
3. 6c7bea6e/413b7a07重叠集成须写接替；合并部署另授权。

## 已验证
独立@301dcd9e：修正版37P（含1汇总）、晚结果两账本条件各5次共10P、重点38P、相关106P，禁止IO均0；原36P/1F及跟踪1F/exit1保留。接续宿主核46项哈希/3段git diff/各exit与IO，未重跑或冒充第二次QC。

## 踩过的坑
每shell显式cd；pytest用主树.venv-workbench/bin/python。尝试计数防吞错假绿；内存repair≠恢复。原题/评分/46针不改。
