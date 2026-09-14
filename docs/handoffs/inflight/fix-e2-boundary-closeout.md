# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；开发树fwp-wt-e2-boundary-closeout，主树不动。

## 当前状态
应用1f6ebc5d已提交，未推/合/部署。D1/P2/P3a此前独立通过；P3b/P3c+返修@301dcd9e独立通过，报告归档dcd57d60（qc-301dcd9e/）。P3d已获独立QC通过（16P；material_only四类禁止尝试0/0/0/0），报告归档p3d-1f6ebc5d-independent-qc-20260915/，仅限四生产者。Grok仅有不完整输入的回顾性试跑；Knevo本轮未发新题、无未揭盲配对、无正式PK（详见`llm-judge-knevo-status-20260915.md`）。

## 决策与被否方案
- 能力/证据计划/输出同源冻结；local_only只留认证本地runner，不按cost/freshness猜IO。
- registry消费者/batch/repair先重绑Scope，保留更严上限、task与诊断；原晚结果红针是二次进适配器，原失败/7断言/超时保留，非产品缺陷。
- P3d在旧答产物/stance/project prior/视角生产者前短路，不靠工厂事后丢字段；full/local_only/普通路径保持。
- 快照docs/handoffs/2026-09-15-e2-p3d-prior-read-ceiling.md；前片2026-09-14-e2-p3bc-independent-closeout.md。

## 未验证 / 已知边界
P3未完成：controller前history/context与QueryResolver早读，歧义/可信基底预取前澄清、四组九类来源过滤、压缩/崩溃恢复/子研究/非工具事实、确定性/legacy回落及交付后读取。不能撤销registry_factory内部IO。
local_only原题号槽/更多认证runner、P4逐题三态、P5可信继承旧答身份、P6材料锚点纯度、P7原始T2→T3未完成。前端/E2E/完整registry-check未跑；RE06 I14另线。
b4ba6fb5全测首RAG迟到响应1红、复跑绿仍未归因；不是已判清的独立晚结果探针错误。

## 下一步
1. 继续按v10推进余P3–P7，但每片单独冻结、作者验证、独立QC；下一片先审controller前history/context与QueryResolver早读，不把所有“继续”拦成材料澄清。
2. q3被解析进材料的问题单列为上游解析缺口；不得用动态题号断言宣称原题号完整。预取前澄清、可信继承、来源过滤、恢复/压缩/确定性旁路仍未闭环。
3. 正式T2→T3/Knevo PK须先完成可审产品路径、全题交付、未揭盲成对答案与固定判官；合并部署另授权。6c7bea6e/413b7a07重叠集成写接替。

## 已验证
干净1f6ebc5d定向210P；全仓9797P/83skip/2xfail/17warnings、exit0，Ruff/钩子绿。四处各删闸均4F/12P。收据归档p3d-1f6ebc5d/；初始夹具16F、有效修前4F/12P、全测工具240秒中断均保留，后者无pytest终态。
前片独立37P（含1汇总）/晚结果重复10P/重点38P/相关106P，禁IO0；46项哈希/3段diff已核。作者测试不替独立QC。

## 踩过的坑
每shell显式cd；pytest用主树.venv-workbench/bin/python。计数防吞错假绿；内存repair≠恢复。原题/评分/46针不改。
