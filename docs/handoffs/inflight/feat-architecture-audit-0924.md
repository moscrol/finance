# 在途：输入与底座验收
## 这个分支做什么
阶段A基线与B离线前置，不是生产恢复。母规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。
## 决策与被否方案
- SPT词面合同拒收，同句不保证同主体/时点/确认；不恢复旧3/3。
- 写入/装配/送达/采用/质量分报。开口记忆复用runner，授权+身份双闸；非市场事实，gap非判断。
- HTTP另开空会话，排除历史回显；保留真实路由/编排/Episode，只替换模型与其他市场预取。展开：`docs/handoffs/2026-09-25-memory-http-delivery.md`。
## 当前状态
P0写侧f3d39d7d2，P1读侧9533417c3；HTTP测试提交3047cb1ee，本轮未改运行时。未push/PR/合main/部署。
临时纠偏→新空会话首provider回调送达PASS；跨用户与撤回后为空，检查点身份/哈希一致。证据：`docs/verification/2026-09-25-workbench-correction-ingest/`。
冻结主干1751e21e0fd3与3047cb1ee比ahead31/behind218；merge-tree唯一文本冲突为.claude/lessons_learned.md，双方经验需保留。代码自动合并不签语义兼容，未开始实际merge。
readiness本轮15秒超时，当前UNKNOWN；09-25 01:43历史503不沿用。
## 未验证 / 已知边界
HTTP为TestClient进程内路由，上一完成稿为合成夹具；模型无回答替身，不签已部署HTTP、浏览器UI、真实Workbench/CLI采用或金融质量。后两项UNKNOWN，发布BLOCKED。
未读写真实用户、补数/换库/建生产索引/恢复采集/新增模型。用户分区测试不签登录认证。树外共享图谱未改。
P1仍限授权主体研究题；material_only/local_only无预取。1秒期限、两槽无积压；线程不能硬杀磁盘IO，未做生产稳定性演练。
SPT挑战4P/8F拒收、原画像1/3；风远十条替代关系及余42条人工来源待owner。
## 下一步
1. 整合冻结主干并审语义差异；候选冻结后完整门禁/同SHA收据，等用户确认合入。
2. 行情/KB/发布owner闭合前置，预算齐后按#76分别验真实Workbench和CLI，再C/D。
3. SPT画像/考卷走批准流程；风远沿Q-002追溯；共享图谱owner补离线PASS，保留未部署/采用UNKNOWN。
## 已验证
3047cb1ee干净794P/0F/0S，clean-http-receipt.json，24文件范围在target；同SHA校验exit0，Ruff/差异/提交门禁通过。后继文档不移签收据；不是完整发布门禁。
旧641P→9533417c3、231P→f3d39d7d2、117P→ec806440c保持原签名。
## 踩过的坑
pytest在fixture后重设测试标记，须隔离根后才启生产写门。请求用E编号不暴露内部tier；记忆原句送达不等于模型采用。坏台账不能报空，记忆与gap引用须双层校验。
