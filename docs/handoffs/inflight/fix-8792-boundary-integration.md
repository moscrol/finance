# 8792 边界组合候选

## 这个分支做什么
登记退出/请求身份/日期引用边界；live后修局部失败连坐，保留可信答案但不放宽事实门。

## 当前状态
树`~/fwp-wt-8792-boundary-integration`；业务`9655b16d`（a969修复＋公开出口续修），基线gitea/main=0a1cb8c4。代码已提交，本交接随文档收口；未push/PR/合main/部署。8792只读核仍bf662 healthy；8828及测试8793/8795已停。
旧3faf四次首题3 completed/1 failed、零重发，**not_passed不变**；本轮新模型调用0。

## 未验证 / 已知边界
- 本轮工程修复未在真实GLM新任务复验；脚本化判官/repair不证明金融质量、稳定性或费用。
- 最近两期跳过Q1、用户截止日未透传information_cutoff、失败用量/判官tokens未知仍待核；旧manual mappingproxy同源未证。
- 清单只查结构形状，不是任意中文/Markdown语义解析器；隐式时间节点沿用默认due，不代签证据支持。
- #770、RE06/#53、#56观察另线；未扩清理/数据写入。真实用户纠偏已CLI落盘，未核下次prompt注入。

## 下一步
1. 读[修复决策](../2026-09-18-8792-local-failure-repairs.md)与[验证索引](../../verification/2026-09-18-8792-boundary-repairs/README.md)，独立复核后再定新live预算/协议。
2. 新真实验收用精确revision、新身份、全写口隔离；每题一次，失败留分母；不得重启旧一次性launcher/重发挑绿。
3. push须显式目标枝（upstream是main）；远端交付/合main/部署/改判官分别确认。并入别枝须验最终整合树。

## 决策与被否方案
- 冻结实参仅JSON边界复制Mapping，否全局解冻/default=str；file URL仍拒绝。
- 删句后重算公开稿缺件，同session有界修复；否关门/全拒答/编阈值。
- 补全失败只恢复本轮旧核验稿并partial，否发布未核验新稿；无可信稿仍fail closed。

## 已验证
9655干净全量11677P/81S/2x/17warnings；Ruff、前端107P/build、E2E34P2S、registry通过；精确收据`20260918T034028Z-9655b16d.json`八项过、base drift0。原QC15/15；8类撤保护均业务exit1。原F1不登记、原阳性仍1条due10-21；F3原file URL拒绝后进展JSON可记账。原219封印不变。
R2=`~/.finance-runtime/reviews/8792-boundary-repairs-20260918/`；旧R=`../8792-boundary-live-20260918/`。

## 踩过的坑
a969首轮全量1F：恢复稿绕过view；接回统一出口后新revision重跑，不借红收据。guard夹具构造错误与health顶层null已留史纠正。completed不代签任务完整；语法/原件hash/扫描未决0各有证明边界。
