# 在途：输入与底座验收
## 这个分支做什么
阶段A基线及B离线前置。母规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。
## 决策与被否方案
冻结097a99745验四叶，完成后才复核新主干；不在测试途中移动候选。首轮PATH缺uvx，补环境而非删图/加skip，完整重跑，不拼局部绿。
理由：`docs/handoffs/2026-09-26-architecture-fourleaf-097a99745.md`。
## 当前状态
干净097a99745四叶PASS，包含已整合主干724028390；本轮未改代码/测试。42份原件在`docs/verification/2026-09-25-architecture-main724-integration/validation-097a99745/`，含首轮红和最终绿。
测试后fetch主干1341f5c22，新增两运行时文件的数值校验/双红时间轴修复，共10提交/10路径。文本预检无冲突，但未实际再merge，新组合UNKNOWN。未push/PR/合回main/部署。
## 已验证
097a99745：Ruff、Python16444P/0F/0error/74S/2X，完整收集16520，外层gate与完整范围校验0；frontend123P、e2e34P/2S；registry五项0，98warning保留。
首轮16443P/1F原件保留；同图只改PATH由uvx_missing变20命中，定向44P/3S后完整重跑。所有测试/临时防休眠进程退出、19981/19984无监听，绿basetemp已清、红保留。
## 未验证 / 已知边界
四叶只签097a99745，后继文档HEAD及新主干组合不移签。执行中有长间隔，不作性能比较。
E2E是隔离夹具服务；生产装配、真实采用/金融质量及生产readiness仍UNKNOWN，发布BLOCKED。未读写真实用户、调用模型、发生产请求、补数/换库/建生产索引或恢复采集；未动共享图谱。
SPT原画像1/3、挑战4P/8F拒收；风远替代关系及余42条来源待owner。#76第三批NOT_PASSED归原owner，不借预算。
## 下一步
1. 冻结下一批实际待合入组合，复核1341f5c22中asof_prefetch和episode_semantic_verifier交叉影响，整合后取得对应验收与用户确认；文本可合不等于语义兼容。
2. 行情/KB/发布前置齐、预算齐后分别验真实Workbench和CLI，再C/D；SPT走审批，风远沿Q-002。
## 踩过的坑
白名单PATH须包含实际uvx目录（本机$HOME/.local/bin），先验工具可达。资源采样先于启动，不是全机锁；不留跨休眠自动开测等待器。线程不能硬杀磁盘IO，顺序去重不签并发去重。
