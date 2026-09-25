# 在途：输入与底座验收
## 这个分支做什么
阶段A基线与B离线前置，不是生产恢复。母规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。
## 决策与被否方案
- 保留双方历史用merge，不rebase改写旧收据身份；经验冲突保留双方独立记录。
- 旧成功夹具缺审计文件却期待PASS：补齐输入并加WARN传播反例，不放宽运行时或直接改旧断言。
- 写入/送达/采用/质量分报；SPT词面合同仍拒收。展开：`docs/handoffs/2026-09-25-architecture-main-integration.md`。
## 当前状态
冻结主干9d5b9800a已整合至审计分支fa7b80942；仅测试修正698fd172d。未push/PR/合main/部署。
四叶工程门禁PASS仅签698fd172d；后继文档HEAD不移签。证据：`docs/verification/2026-09-25-architecture-main-integration/README.md`。
readiness上轮15秒超时，本轮未采样，UNKNOWN；历史503不沿用。真实采用/金融质量UNKNOWN，生产发布BLOCKED。
## 已验证
698fd172d干净全仓16423P/0F/74S/2X，collected16499；完整收集面与同SHA校验exit0，Ruff与外层门禁exit0。前端123P、e2e34P/2S，registry五项exit0。自适应开关on环境的HTTP及相关回归17P。
首轮fa7b80942为16421P/1F/74S/2X，红原件保留；不是靠局部复跑拼绿。旧794P→3047cb1ee、641P→9533417c3等保持原签名。
## 未验证 / 已知边界
HTTP纠偏仍为TestClient、合成上一答案、无回答替身；常规隔离e2e不签生产纠偏UI、Workbench/CLI真实模型采用或金融质量。
未读写真实用户、补数/换库/建生产索引/恢复采集/新增模型。用户分区不签生产登录认证；树外共享图谱未改。
P1限授权主体研究题，material_only/local_only无预取；1秒、两槽无积压，不是磁盘IO硬取消。未做生产稳定性演练。
SPT挑战4P/8F拒收、原画像1/3；风远十条替代关系及余42条来源待owner。
## 下一步
1. 验收方复核届时主干与实际候选，同SHA门禁及用户确认齐后才合入，不拿文档HEAD代签。
2. 行情/KB/发布owner闭合前置，预算齐后按#76分别验真实Workbench和CLI，再C/D。
3. SPT画像/考卷走批准流程；风远沿Q-002；共享图谱owner补离线与整合证据，保留生产UNKNOWN。
## 踩过的坑
资源采样应先于启动测试，不能并行；本轮重验途中另一树开测，留资源原件，不作性能比较。失败缺文件不等于零债务；服务合同收紧要覆盖消费者夹具。记忆原句送达不等于采用。
