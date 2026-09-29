# R6×发布组合｜2026-09-19

## 这个分支做什么
把R6财务拒错、交付保护接到精确发布边界，保安全正文、引用与partial补修债。

## 决策与被否方案
- 仅接49fd发布片，a31交付片此前已在；否整枝保稿/RAG/runtime合流。
- 终态claim不挪、不sleep；精确最终事件后重读产物，SSE排空后收口。
- published只证可见性，不升级金融partial；保view出口、合法引用与前后拒句账。
理由：`../2026-09-19-8792-financial-publication-integration.md`。

## 当前状态
树`~/fwp-wt-8792-financial-r6-repair`，业务`d06dc1e8`已提交（父文档0b16bc03，旧业务d9657215）。作者工程仅固定依赖条件下通过；旧R6/R3仍0/4 not_passed。无本候选新live/独立QC，未push/合main/部署/切8792。
收据包`docs/verification/2026-09-19-8792-financial-publication-integration/`；原件`~/.finance-runtime/reviews/8792-financial-publication-integration-20260919/`。文档tip不迁绑业务成绩。

## 未验证 / 已知边界
- F2报告真实取回未修；有限门不认证因果/来源真实性。自然补查复算、根预算全链与跨进程恢复未签；永久缺最终事件仍pending。
- 正常/可信稿恢复的存储/API接缝已验，恢复用已核验稿直接调用，非自然异常续修。原件回放非新完整Episode。
- 宿主registry红及all_passed=false保留；同金融SHA＋KB91725ea9＋site9f60bef五项0。不scan倒退登记。
- 邻枝只读：答案保留ad459ad0/业务20939b18记录RAG已修、新GLM仍not_passed；不借成绩。runtime封存时89f8d727干净但新片未审，旧收据只签6b70。

## 下一步
1. 审邻枝最新已提交最小片，保稿/RAG/runtime各验接缝，不搬WIP、不重复接49fd/a31。
2. 扩组合另冻新SHA及跨仓输入，重验五套SUITES/view/引用/拒句账/债务，不拼旧绿。
3. 新live、独立QC、push、合main、发布分别确认；旧样本不重发挑绿，8792不切。

## 踩过的坑
同SHA可有0执行收据，按pytest.log精确指针选；本轮收据名首输错exit2非测试失败。JUnit无type属性要读message，默认35组有7组仅异常型。初4F漏skill_mode是夹具；前端首红命令实际跑整套。原日志不清理，展示转换双hash。

## 已验证
d06干净同SHA：Python12198P/86S/2X、Ruff0，前端115P、E2E34P/2S；收据20260918T170550Z-d06dc1e8八项过。发布8/接缝6/R6及交付各13组有断言红→绿；默认35组测试体红→绿，不加分母。原件12hash不变/连接0/登记0/0/0/1。8931/8934无listener、临时finance/site已移除。工具包78ec622未合；vault自动同步7457f945/86eb21ba，lint仍20E/17W、图谱0非质量认证。
