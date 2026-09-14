# fix/e2-boundary-closeout

## 这个分支做什么
按v10分阶段收口E2材料题边界；开发树fwp-wt-e2-boundary-closeout，主树不动。

## 当前状态
应用P3b=8ea6c5c1、P3c=b4ba6fb5已提交，未推/合/部署。D1/P2/P3a此前独立通过；P3b/P3c待独立复核：Codex工具前502/429/503，Claude503且零工具调用，无有效报告。独立树/tmp/e2-p3bc-qc-b4ba6fb5干净。证据docs/verification/e2-boundary-closeout/qc-b4ba6fb5-blocked.md及prompt/log。

## 决策与被否方案
- 双轴独立；范围声明不能替事实背书。能力/证据计划/输出类型同源冻结，不只清菜单。
- local_only只保留已审定本地runner；不按cost/freshness猜IO，可信声明不是OS沙箱。
- P3c消费者先绑定受限registry；否了只约束Scope副本，因为原预取仍会进模型。覆盖配置/提示词/播种、升档/预检、菜单/定义/批执行、内存repair；full原对象不改。
- 受限重绑重清prefetch/calc_loader，不以“scope相同”短路；不是清洗既有历史消息。
- 详见docs/handoffs/2026-09-14-e2-p3c-runtime-ceiling.md；前序同日p3b-local-ceiling及p2-p3a-closeout快照。

## 未验证 / 已知边界
P3未完成：预取前澄清/可信基底，controller摘要/stance/project prior/视角与普通context来源过滤，压缩/崩溃恢复/子研究/非工具事实/确定性旁路及回落。不能撤销registry_factory内部已发生IO。
local_only原题号槽/更多runner认证、P4逐题三态、P5可信继承旧答身份、P6材料锚点纯度、P7原始T2→T3未完成。前端/E2E未跑；RE06 I14另线未闭环，不扩为材料比较前置。
全测首跑RAG迟到响应1红；同提交完整复跑绿、单文件44绿、修前同针10次绿。未稳定复现/未归因，不隐去首跑失败。

## 下一步
1. 固定b4ba6fb5按归档prompt独立分审P3b/P3c；无有效报告不升阶段通过、不继续堆未审片。
2. 再按v10推进余P3–P7；T3不得重贴禁令。6c7bea6e/413b7a07重叠集成须写接替。
3. 若RAG再红固定时序/IO分诊；不调阈值求绿。合并部署另授权。

## 已验证
干净b4ba6fb5定向439 passed（新15针）；修前同15针12红3绿。全仓首跑9776P/1F；同提交复跑9777P/83skip/2xfail/17warnings、exit0。原输出full-b4ba6fb5-{first,rerun}-tests.txt；Ruff/diff/提交钩子通过。非独立QC。

## 踩过的坑
每shell显式cd；pytest用主树.venv-workbench/bin/python。禁止IO探针计数尝试防吞错；测试task_id独立。内存repair不等于崩溃/取消恢复。不改原题/评分/46针。
