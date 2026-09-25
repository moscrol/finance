# 在途：输入与底座验收
## 这个分支做什么
阶段A基线与B离线前置，不是生产恢复。母规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。
## 决策与被否方案
- 用户委托采用原SPT三题候选标准；不重复问实现选择，不冒充正式批准。
- 词面条件合同拒收：同句不保证同主体/时点/已确认。否堆词刷绿、改金标或静默忽略；正式评分/保存拒绝实验字段，实验仅供失败重放。
- 票据/装配/请求送达/模型采用分报；风远旧值不自动恢复。展开：`docs/handoffs/2026-09-25-spt-contract-rejected.md`。
## 当前状态
已提交：反例冻结8ca4dc4c3、隔离fa82a73ca、证据d39400ee6、用户记忆前置ec806440c/收据ccd641056；后继仅交接。未push/PR/合main/部署。
SPT挑战12项4P/8F，候选REJECTED/预演FAIL；旧3/3不再作采纳依据。真实画像1/3、内存边界2/3，正式卷缺、真实边界空。
用户纠偏离线前置通过：临时A写入并被A的`memory_lookup`消费，B空结果，A撤回后空结果，无身份不装配；Workbench自动写入仍UNKNOWN/BLOCKED。证据：`docs/verification/2026-09-25-user-memory-consumption/`。
09-25 01:43 readiness 503，仅缺`market_data_consistency`；检索协议当次通过，邻接owner仍数据HOLD。既有装配/首次GLM请求送达保留；风远历史95/105，十条替代关系、余42条及人工原授权待追溯。
## 未验证 / 已知边界
未生产写入、补数/换库/索引重建/恢复采集或新增模型。纠偏收据只覆盖临时writer→memory_lookup，不覆盖Workbench写侧或模型主动调用。词面实验拒收不等于SPT通过；本轮非独审/盲测/泛化。真实Workbench/CLI质量、续轮、全量发布门禁未完成。
## 下一步
1. 不恢复被拒合同，不重问原三题；正式画像/考卷走既有批准流程。
2. Workbench纠偏写侧另按`2026-08-30-workbench-correction-loop-design.md`及owner授权实施，不把已有writer消费收据当闭环。
3. 原视角owner沿Q-002追溯风远修订，不复制队列。
4. 行情/KB/发布owner闭合日期/身份/范围/字段/索引；前置及预算齐后按#76验Workbench Episode与CLI，再C/D。
5. 合入前核最新主干、冻结候选、跑完整门禁并等用户确认。
## 已验证
fa82a73ca定向636P/0F/0S；撤护栏21F/5P后恢复636P。ec806440c定向117P/0F/0S（含CLI prime）；Ruff/提交钩子/图谱audit通过。收据见上述验证目录。
## 踩过的坑
候选代码在`scripts/perspective_signal_candidate.py`，勿从`intelligence`导入。`none`不是弃权；旧597P/三题全过不能覆盖反例；后继文档不冒充受测SHA；缺就绪前置不新增模型运行。
