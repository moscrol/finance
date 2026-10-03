## 这个分支做什么
继续四片Harness候选，处理独审S1并刷新主线验收；用户要求验收过关后上线，质量门未过不发布。任务FINANCEWORKS-3。

## 决策与被否方案
- 接纳/反馈统一经ResearchHarness；否只换开场prompt，因为后续又注回默认规则。
- loop保留取消/截止/次数/同包工具/持久化；否把副作用搬进领域接口，因为不是S1所需。
- 新Protocol方法不静默回落默认harness，否则替换失效；不扩finalizer/SDK repair提示重构。
- 选工程与内容分别验；否把测试绿、12格预验当质量通过。背景/取舍见[本轮快照](../2026-10-04-harness-interpretation-seam.md)。

## 当前状态
- 已并入main@108835e27，merge=28cf79c4；产品pin=25de6994bdb79b57e9cf06fcb81f6f5796c67079，已推GitHub/Gitea并回读。
- PR #30仍Draft/OPEN，无auto-merge；生产仍ffe1c60d。条件部署授权不等于质量已通过。
- 本机全量/变异已结束；前端临时树先保全260文件+3DB后移除，四个变异临时树已移除。旧mutation-fix与其它活动树保留。
- 新证据根`~/.finance-runtime/reviews/harness-release-20261004/`；原封口证据根harness-integration-20261003不改。
- 当前文档HEAD由Git读取；CI按实际PR head与树外收据核对，不在本文追逐自身SHA。

## 已验证
25de：Python20584P/76S/2X、collected20662、18warnings；完整范围/解释器/依赖/clean审计exit0。前端209、E2E52P/2S、registry五项exit0。变异9/15/13/14，历史8、边界16，audit-final.exit0。273项是补丁迭代，不代全量。

## 未验证 / 已知边界
新版独立Spec/Standards尚未完成，任务板已请求；历史Spec507与Standards60ff不转签。25de GitHub workbench37150212381待终态，registry37150212352已success。真实问答新增调用0、未证明内容提升；SDK跨进程恢复及剩余P1b不在范围。

## 下一步
先读FINANCEWORKS-1/3及评论，查当前Git/PR/CI。等用户批准费用：树外`model-acceptance-approval-draft.md`建议审查+最多12格预验总上限50元，尚未批准；实际通道计价与物理调用/token/时间帽未核实，不调用模型。12格只验链路与答卷，正式质量门另冻方案；R17/R19/240格不动。未过质量与独审不合main、不部署。

## 踩过的坑
旧d09e绿只属旧基线。JSON载荷tuple会变list；参数化SDK测试须独立Episode ID。工具context不是ResearchRunContext。一次watch300秒超时不代表CI失败/成功。清理PATH含/usr/sbin:/sbin，ignored数据先保全；Gitea代码备份不等于数据已上传。
