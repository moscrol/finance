# 在途：输入与底座验收
## 这个分支做什么
阶段A基线及B离线前置。母规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。
## 决策与被否方案
扩既有HTTP夹具验异常，不新造召回或借#76预算。组件绿不代HTTP绿，旧收据不移签；资源拒绝不强行开测。决策：`docs/handoffs/2026-09-25-workbench-memory-faults.md`。
保留merge历史及双方经验；成功夹具补输入，不放宽缺审计时WARN合同。SPT词面合同仍拒收。
## 当前状态
新增测试提交c367aa2a7，仅改HTTP测试：自适应on/off、坏台账、读失败/超时/busy/迟到、写入权限/磁盘满及恢复。pytest未启动，BLOCKED于其他pytest并发；未留后台等待器。
本轮fetch主干64847b7a1只比已整合9d5b9800a多文档，文本预检无冲突，未再merge。未push/PR/合main/部署。
新证据：`docs/verification/2026-09-25-workbench-memory-faults/README.md`。09:28Z health200但未认证代码身份，readiness15秒超时，UNKNOWN。
## 已验证
c367全仓Ruff和提交静态检查PASS；新增测试无运行结果。
旧698fd172d四叶PASS：16423P/0F/74S/2X、完整收集16499，前端123P、e2e34P/2S、registry五项0。只签旧SHA，首轮红保留；详见`docs/verification/2026-09-25-architecture-main-integration/README.md`。
## 未验证 / 已知边界
新HTTP故障候选待运行。既有TestClient仍是合成上一答案、无回答替身，不签部署网络/UI、真实模型采用或金融质量；生产发布BLOCKED。
未读写真实用户、补数/换库/建索引/恢复采集/新增模型；未动树外共享图谱。记忆授权及身份双闸、可选先验、非市场事实边界保留。
SPT原画像1/3、挑战4P/8F拒收；风远替代关系及余42条来源待owner。#76新增记录判官不可用，不借其预算。
## 下一步
1. 先资源采样再启动测试，在独占干净候选跑HTTP/P0/P1相关回归，收据绑定实际HEAD；最终合入仍需对应四叶及用户确认。
2. 行情/KB/发布owner闭合前置，预算齐后分别验真实Workbench和CLI，再C/D。
3. SPT画像/考卷走批准流程；风远沿Q-002。
## 踩过的坑
资源采样不能与启动测试并行；时点准入不是全机锁。空会话上下文含格式提示，不必为空字符串。线程只能有界等待，不能硬杀磁盘IO；顺序去重不签并发去重。
