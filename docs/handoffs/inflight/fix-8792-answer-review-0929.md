## 这个分支做什么
复审Pi续做并提高8792回答能力；承接WIP #956，代码d9eeb69b7，本次附文档证据。报告：`docs/verification/2026-09-29-pi-continuation-review.md`；决策快照：`docs/handoffs/2026-09-29-pi-answer-review.md`。

## 决策与被否方案
- 保留Pi紧凑作者协议/有界quote纠正/FA-01撤回；补E9延后后空binding普通异常遮住伪来源的回归。
- 同一已知H多摘录归FORMAT，由作者原预算内拆写；否了程序拼接/选源/直接放行。未知、错类、跨H及无来源事实仍硬拒。
- 不恢复FINANCE_RESEARCH_REASONING默认开关；财务与消息仍需实答改善。

## 当前状态
代码固定d9eeb69b7；本提交归档收据和复审。PR #956保持WIP，远端head以平台回读为准；未合main、未部署。Pi原树及其脏文档均保留，已核对的副本在c24112ff9。

## 未验证 / 已知边界
历史新样本n=1且没触发修复，不证明恢复分支自然成功或追平Pi/ReAct/Knevo。旧财务两组partial、消息unusable不变，旧19卷并非成功率。前端/E2E/registry仍是7c原身份证据，不签当前main组合。

## 下一步
沿冻结财务/消息原失败定位首个偏差，固定题和实际模型做小规模对照，保留全部结果；财务分清利润/经营现金流/CapEx/股权估值，消息分清版本和预计/确认。不靠叠提示或改题挑稿。合入仍需用户确认和最新组合验收。

## 踩过的坑
正反顺序、空白E9、同H多摘录掩盖后续伪源都要测；“允许格式重写”不能转换来源身份。8837已停PID482、端口无监听；生产09-29只读为20d49970a，系另一任务切换，别写仍8e45。主树规定venv；其他树脏改动不动。

## 已验证
干净d9全Python18,638P/74S/2X、0F0E，Ruff和收据校验过；独立Standards43P+22探针、Spec36P。新历史run_20260929_101405_411216四旧值/日期及未重核声明正确，1模型0工具。证据`docs/verification/pi-continuation-review-2026-09-29/`，原门禁`~/.finance-runtime/test-receipts/gate-JQq5t2Av/pytest.json`。可复用方法已补共享记忆`retry-must-carry-the-last-rejection.md`。
