# 行情恢复 QC 修复

## 这个分支做什么
修 #861/#871 的 F1 接线、F2 假覆盖/坏价、F3 过期覆盖。最新快照：`docs/handoffs/2026-09-23-market-recovery-continuation.md`。

## 当前状态
整体 HOLD。main 2edbe4c46 + 修复枝f3c99ab5b重组为257263f63，全仓绿；F1 report、F2补强explore仍被504阻塞，新探针/报告0。业务仍为4fa70046f、981c4d629、3abb7a4d3，本轮无业务代码改动。未合并/推送/部署/staging/换库/写生产。所有本轮进程退出；干净candidate保留。

## 决策与被否方案
- 最新main重组跑全仓，否定tests/或旧全仓收据移签：身份与范围必须同时匹配。
- 原探针逐字节复跑，否定复跑=新独审裁决；旧F2/F3报告仍属4dd5。
- 504后停止开会话，否定自动重试/换模型；Pi exit0不是交付。
- 另建五个单文件历史回退版本，否定必红断言=回归敏感度；旧API的3个TypeError不算行为覆盖。

## 已验证
- 组合257263f63，treedd731224；结束后fetch，main仍2edbe4c46，零漂移复核通过。
- 全仓14874P/85S/2XFAIL，收集14961对账，0F/0E；2385.43秒。require-full-scope、revision、解释器、依赖、干净检查通过。target为候选仓根，非tests/。
- 原独立探针20P（F1 5/F2 9/F3 6）；作者相关131P分账；3次必红对照均1F。
- 5个历史回退版本均有行为失败：20次行为失败、3次API不兼容、0收集错误。是重复运行，不是新增独立用例。临时树已清，验证refs保留。
- Ruff、注册表/解析、交付门5自测通过；无webapp改动，前端/E2E未跑。

## 未验证 / 已知边界
F1无正式报告；F2/F3旧PASS_WITH_LIMITS不移签。F2未补-inf/成员坏close/其他日期独立覆盖；F3未补全列/缺policy其他日期覆盖；并发、完整指纹、部分写后回滚未认证。五问/三合同/5553-5565范围/53只公司行动未裁决。真实nightly、恢复CLI及生产验收未做。

## 下一步
1. 通道恢复后有界补F1 report和F2/F3缺口，不覆盖旧失败目录。
2. 用户裁决业务口径；不要把「继续」当签字或生产授权。
3. main/实现再变则重新判定收据适用性；获授权前不合并/推送/部署/写库。

## 踩过的坑
3请求只有1条HTTP200钩子记录，另2条504只在model_errors；两次Pi exit0均无交付。全仓target可为仓根，不要求空字符串。历史回退红与当前候选失败必须分账。
证据：`docs/verification/2026-09-23-market-recovery-continuation/`；运行根 `~/.finance-runtime/reviews/market-recovery-qc-20260923/continuation-257263f/`；引用 `refs/verification/market-recovery-continuation-20260923`。
