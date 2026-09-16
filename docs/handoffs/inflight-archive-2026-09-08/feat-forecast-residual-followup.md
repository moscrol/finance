# feat/forecast-residual-followup

## 这个分支做什么

品质残差 P2：首轮公开稿露出未核验格；追问补格不重跑五日包。

## 当前状态

`forecast_residual_followup.py` 已接线：公开稿 `append_unverified_forecast_grids`；gap-mirror 问句当 continuation；prefetch 点名补格只发卡「沿用上轮」。未合、未切。

## 未验证 / 已知边界

- 未跑冻结展望 live。执行方不标 confirmed。
- 8792 仍停在更早 SHA，不要切，除非用户说切。
- 没扩到「1.9 万亿」等其它无格数字。

## 下一步

1. 本机相关测绿后开 PR；全量绿再合。
2. 不要切 8796 / 8802。

## 踩过的坑

gap-mirror 芯片以「关于…上一轮「」未完成核验」开头，旧 `_CONTINUATION_RE` 认不出，座位丢。点名补格若仍 `market_forecast`，会把五日包当新菜重跑。

## 工具沉淀盘点

复用 `compose_followups` / `open_gaps` / `render_unknown_slots`。没新造第三条追问链。样本只覆盖展望座位，不抽通用脚本。

## 已验证

`test_forecast_residual_followup.py` + outlook / followups / query_resolution 回归绿。
