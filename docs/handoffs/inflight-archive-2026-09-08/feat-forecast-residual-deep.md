# feat/forecast-residual-deep

## 这个分支做什么

展望座位在开口五日包齐了之后，才把残差升到 `deep`（12×240s）。

## 当前状态

`forecast_residual_budget.py` 已接线：adapter 在 registry 之后升档；深档连打 `duplicate_query` 停机。未 push 合入前以本文件为准。

## 未验证 / 已知边界

- 生产 8792 仍 `a7a8ba9f`，未切、未跑冻结展望 live。
- 无格 `110–120%` 仍属 outlook `-24`，本单没做。
- P2 followup 露出未做。
- 升档后墙钟以 context.deadline 为准；不改全局 120s 默认。

## 下一步

1. 本机相关测已绿后开 PR。
2. 合入等用户确认。不要切 8796。
3. live 冻结题另开目录，执行方不标 confirmed。

## 踩过的坑

adapter 默认 timeout 会 `min` 掉 factory 的 deep 秒数。升档必须发生在 context 造完之后，用 `for_tier("deep")` 换 deadline，不能只改 `tier=` 字。

## 工具沉淀盘点

升档判据是纯函数（座位 + 开口包），没抽成通用「任意题型升档」脚本——样本只有展望一条座位。

## 已验证

`test_forecast_residual_budget.py` + adapter/episode/outlook 回归绿。
