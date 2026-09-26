# #81 本地前向候选

## 这个分支做什么
将#832产品27034ce44与main a54fed0d独立合流；不接管原作者树、#892原件或#832远端head。

## 当前状态
合流f051f28d4，变异定义3629e19e2；本地候选，未推/合main/部署。代码固定后的收据只签各自revision，后续文档提交不移签。旧0304独审阻塞不变，本轮模型请求0。

## 决策与被否方案
保留主线结构化分母及next_offset，同时保留分支窗口约束和投影成功后登记；否了整文件择边，会丢掉另一方保护。撤保护复用现有runner，不复制框架。完整背景见`docs/handoffs/2026-09-24-react-trace-closeout-forward.md`。

## 未验证 / 已知边界
未跑新组合完整Python、前端/E2E、#76自然验收；C3拒参后继续取证、C5完整reader独审仍欠。作者临时store与故障注入不代独立终审。未新增任何模型预算授权。

## 下一步
补有限独审方案/授权并重封候选身份；沿原工单独审达标再排完整工程。若采用此合流，核main漂移与产品差分，不移签27034旧门禁或拿本轮380P当全仓。变异复跑用`run_extraction_mutations.py --definitions scripts/review_probes/history_projection_forward_mutations.json --tests tests/test_history_model_projection.py`，输出新目录。

## 踩过的坑
证据标题自带query/card标识，整标题相等会漏取。开发期新增断言6F属测试匹配错误，已修且保留红收据。两文件有四个冲突块，不是两个行为冲突。

## 已验证
f051固定7文件380P、全仓Ruff0，正式收据20260924T130052Z-f051f28d-b3d08fe306e9.json。3629变异基线28P、两撤线6F/1F、恢复6P/1P、最终28P，零collection error。证据`~/.finance-runtime/reviews/pi-closeout-execution-20260924/react-trace-3629e19/mutations/`。提交钩子通过。
