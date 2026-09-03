# feat/forecast-residual-followup

## 这个分支做什么

品质残差 P2：首轮公开稿露出未核验格；追问补格不重跑五日包。

## 当前状态

已合 `gitea/main` **#370 `760bf79b`**。台账 `R-20260824-36` pending。未切 8792/8796/8802。

## 未验证 / 已知边界

- 未跑冻结展望 live。执行方不标 confirmed。
- 生产仍停在更早 SHA；P1 升档 + P2 露出都还没进 8792。

## 下一步

用户再说「切」才切 8792 到含 #366/#369/#370 的 tip。不要动 8796。

## 踩过的坑

gap-mirror 芯片以「关于…上一轮「」未完成核验」开头，旧 continuation 正则认不出。点名补格若仍 `market_forecast`，会把五日包当新菜重跑。

## 工具沉淀盘点

复用 `compose_followups` / `open_gaps` / `render_unknown_slots`。没新造第三条追问链。

## 已验证

全量 pytest **6379 passed / 13 skipped / 0 failed**，`dirty=false`，收据 `20260824T171107Z-e42cba13.json`。
