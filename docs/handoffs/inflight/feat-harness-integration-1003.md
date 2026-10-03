## 这个分支做什么
从`origin/main@06198093eb7d4cf57ff20e26a2fa7a7df9df8726`集成Harness四片并完成版本锁定的工程验收；不扩剩余P1b。

## 决策与被否方案
- 以产品代码pin`d09e3b08`归账，文档后续单列；否用`60ff5ba76`改签产品收据，因为它只改handoff。
- 保留主线来源/绑定预检与拒绝顺序；否全选候选实现，因为会削弱冻结材料合同。
- canonical因果答案必需、`cause_attribution`启发式提示可选；否恢复第二硬槽或删测试，因为都破坏用户义务边界。
- adapter合并阶段反馈与交付说明；否在coordinator并集旧裸索引，因为索引可能已不属于当前稿。
- 临时树逐棵安全收口；否全仓`--apply`，因为ignored users/快照、进程和未合分支不可由脚本替人判断。

## 当前状态
- 产品pin工程验收完成：Python、前端/E2E、registry、变异审计均有树外收据；真实金融Workbench调用为0。
- 产品pin之后只改handoff；文档当前HEAD由Git读取，不在本文写自身SHA。PR #30保持Draft；未合入/部署/自动合并。
- 收尾动态状态以证据根`~/.finance-runtime/reviews/harness-integration-20261003/`的`closeout.json`、`evidence-index.json`及PR实际head为准，避免为抄写CI结果循环提交文档。
- 五棵detached门禁树已点名移除；前端260个残留文件和3个数据库保全在本地归档，代码archive ref推至Gitea。命名分支`gate-trees/mutation-fix`保留；具体收口见[日期快照](../2026-10-04-harness-integration-closeout.md)。

## 已验证
- 产品pin：Python`20558P/76S/2X/0F`、collected`20636`，收据审计exit0；前端209 tests，E2E`52P/2S`；registry五项exit0；变异`9/12/13/14`，历史8、边界16，最终审计exit0。
- 文档头`5070054a`的workbench run`37142366948`、registry run`37142366939`均success；这是历史SHA证据，不自动覆盖后续提交。
- 清理收据：`worktree-closeout-20261004-gitea/apply-20261004T011337.json`，apply exit0；Gitea archive ref已验证。

## 未验证 / 已知边界
最终生产补丁`46d9875c6`没有独立审查；只读审查覆盖`5266b5f8`，实际模型为`glm-5.2`，费用basis unknown。结构门禁不证明回答质量；未做真实对照、题型/主体/时间窗在线修订、完整HTTP新计划、SDK跨进程恢复。R17/R19/240格封存。

## 下一步
接手先对照closeout、Git当前HEAD与PR实际head/required checks；三者不符则标未收口，不转签旧绿。用户另批后才做补丁独审或最多12格真实Workbench对照；不合main、不部署。

## 踩过的坑
Python收据必须按revision、解释器、依赖指纹、dirty和完整收集面审计；初次lsof PATH不全时不删。清理时`git status`干净仍不等于可删：ignored数据、launcher、锁、无具名提交都要fail-closed。详见`docs/handoffs/2026-10-03-harness-main-integration.md`及2026-10-04收尾快照。
