# feat/market-watch-component-first

## 这个分支做什么
`market_watch` 拒收 Engine A；开口前四袋；显式日 `=`。

## 当前状态
**已合 #352 = `af71f048`。** 8792/8796 同 SHA。树 `/Users/a77/fwp-wt-market-watch-component-first` 可拆。
主检出脏树仍不要当 runtime 改。

## 未验证 / 已知边界
- P1 未做：`R-20260824-04` 阈值删句 / `market_data` 记账。
- 长电是链切探针，不是盘面包 A1 再验收。

## 下一步
1. 拆实施树（用户点头后）。
2. P1 另开分支。
3. 回滚见 `docs/handoffs/2026-08-24-market-watch-352-cutover.md`。

## 踩过的坑
8796 启动器写死快照路径；KeepAlive 会把 kill 拉回旧 SHA。

## 已验证
#352 merge-tree rc=0；两港 health 三读过；readiness 13/13。
