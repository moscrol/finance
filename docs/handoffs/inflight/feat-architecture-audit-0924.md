# 在途：输入与底座验收
## 这个分支做什么
阶段A基线及B离线前置。母规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。
## 决策与被否方案
主干已有代码漂移，merge固定724028390而非只测旧HEAD；保留历史，不rebase移签收据。资源拒绝不强测、不排除其他agent，20分钟到限退出。
理由与盘点：`docs/handoffs/2026-09-25-architecture-main724-integration.md`。
## 当前状态
固定主干724028390已整合为bb556febd（第一父8e1d6fc28）。包含按模型推理强度/API预算及测试变化，未启用配置。静态PASS，但四叶BLOCKED且均未启动；等待器已退出，无本任务后台进程。
证据与续跑：`docs/verification/2026-09-25-architecture-main724-integration/README.md`，8份原件。未push/PR/合回main/部署。
## 已验证
bb556febd：干净树全仓Ruff、代码/文档差异检查exit0；20分钟41次资源观测全拒绝，磁盘高于门槛，阻塞为其他pytest。
78b25943f：HTTP22P、24文件824P/0F/0S（包含22项），两收据校验通过，见workbench-memory-faults验收目录。只签旧SHA。
698fd172d旧四叶PASS：16423P/0F/74S/2X，前端123P、e2e34P/2S、registry五项0；不移签。
## 未验证 / 已知边界
当前组合无动态收据。HTTP仍是进程内合成上一答案，无回答替身；不签部署网络/UI、真实采用或金融质量，生产发布BLOCKED。
本轮无生产请求、真实用户读写、补数/换库/建索引/恢复采集/新增模型；未动共享图谱。既有生产readiness仍UNKNOWN。
SPT原画像1/3、挑战4P/8F拒收；风远替代关系及余42条来源待owner。#76第二批NOT_PASSED/数值预检问题归原owner，不借预算。
## 下一步
1. 不必重做本轮merge。先确认干净树与实际待测SHA，资源准入后跑现有前端/E2E、registry五项、全仓Python入口及完整收据校验。若在后继文档HEAD跑，只签实测版本。
2. 四叶齐后复核届时主干、独立验收并等用户确认再合。期间不移动受测候选。
3. 行情/KB/发布owner闭合前置，预算齐后分别验真实Workbench和CLI，再C/D；SPT走审批，风远沿Q-002。
## 踩过的坑
资源采样先于启动，不是全机锁；历史PID不是当前事实。静态绿不代动态绿，未启动不算FAIL。空会话仍有格式提示；线程不能硬杀磁盘IO，顺序去重不签并发去重。
