# feat/market-watch-component-first

## 这个分支做什么
`market_watch` 拒收 Engine A；四袋在 owner 分叉前跑完；显式日 `=` 命中。

## 当前状态
树 `/Users/a77/fwp-wt-market-watch-component-first`。P0 随本分支提交。
主检出脏树不要动。不合 main。不动 8792/8796。

## 未验证 / 已知边界
- 未 live：A1、`2026-07-25 今天市场怎么样`。C1 原题只旁路对照。
- P1 未做：未注册阈值删句、`market_data` 记账。
- G1b / 全量 pytest 未在本树跑。

## 下一步
1. push `origin`（GitHub 可见）后 live 两题。勿覆盖 `four-arm-knevo-20260823/`。
2. 合 main 等用户确认。

## 踩过的坑
隐式「今日复盘」+ 无库：空包 `should_stop` 会盖掉旧答。只在显式日确认无行或休市才停。
有 `2026-07-23-daily-review.md` 时 daily-review 会 own，锁格必须 `merge_into_public_answer`。
C1「2026-07-25 市场怎么样」不是 `market_watch`。

## 已验证
拒收 #1；四袋夹具；07-25 不回落 07-24；#2a/#2b 编排器；orchestrator 100；相关 238 绿。
