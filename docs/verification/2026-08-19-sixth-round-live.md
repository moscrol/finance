# 第六轮同题对照（2026-08-19）

> 代码：生产快照 `15510ad7`（P0-A/B + P1-C + #215）  
> sidecar `:8796`，隔离用户 `sixth-round-0819`  
> 生产 `:8792` 只读 health，未切  
> 入口：`POST /api/conversations` → `.../messages`  
> 对照：第五轮 Workbench `run_20260819_000940_130301`；Knevo 同夜同题（spec §一）  
> 仓内副本：`docs/verification/2026-08-19-sixth-round-live.md`；原始读数 `~/.finance-runtime/sixth-round-live/2026-08-19-sixth-round-live.md`

## 题目

「基于周二的盘面数据，你认为主线是什么。今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会」

## 判定

**第六轮主发通过 spec §四 条 1–5。** 相对第五轮：授权、领跌结构、互斥因果都在公开稿里。相对 Knevo：同一套「存储跌深于英伟达 → 不是全面证伪 AI」结构已经出现；本发裁决倾向「情绪回吐」而 Knevo / P1-C 更偏存储周期。新闻仍授权未调用。

## spec §四

| 条 | 要求 | 读数 | 结果 |
|---|---|---|---|
| 1 | 原题授权含 news/web；纯 A 股不回退 | 原题 allowed 含 `news_search`/`web_search`；对照题「昨天的反弹能持续多久」无 news/web | 过 |
| 2 | 外盘前提须工具核验或显式缺口 | Yahoo E17–E21（2026-08-18），不是 `user_premise` | 过 |
| 3 | 不发明 2.2万亿 / 60涨停 / 27% | 主发用 24006亿 / 涨停79 / 电子31.2%（均有 E） | 过 |
| 4 | E 覆盖 ≥23 | 28 | 过 |
| 5 | [M]/框架名不是深度判据 | 未引用 | 过 |
| 6 | 无外盘词预测仍本地-only | 对照题授权正确；**公开稿发明「约2.2万亿」**（核验标了 unsupported numeric） | 授权过 / 正文部分 |

## 对照

| | 第五轮 Workbench | 第六轮 Workbench | Knevo 同夜 |
|---|---|---|---|
| 授权 | 无 news/web | 有 news/web | 新闻+行情+记忆 |
| 美股个股 | 无 | SOX/NVDA/MU/HYNIX/SNDK 全绑定 | 闪迪/海力士/美光 vs 英伟达 |
| 因果假说 | 无（只有量能 A/B/C） | 假说A 存储见顶 vs 假说B 情绪回吐，倾向 B | 存储周期担忧 ≠ AI 证伪 |
| 新闻 | 无 | 授权未调用 | finance_news ×5 |
| 纪律 | E 编号在 | E 编号在 | 零引用 |

本发海力士已绑到 8-18（−8.51%）。P0-B 当时海力士滞后未绑。

裁决与 P1-C live（倾向存储周期、部分并立）不一致：同一相对强弱，这次读成「英伟达抗跌 → 情绪」。缺新闻归因两边都写了缺口。这是 n=1 波动，不是回退。

## 残留

- 原题仍不调 `news_search`（授权在）。这是 overnight news hang 要补的 Knevo 缺口，不是 P1-D。
- 对照题公开稿发明 2.2万亿 / 2万亿离场线；闸看见了，稿子里还在。
- 主发 `deadline_exhausted` / episode `partial`；对外 run `completed`。
- 主发写了 `likelihood中`（不是 40% 那种数值概率）。

## 产物

- 主发 `run_20260819_105845_919694`
- 对照 `run_20260819_110003_775678`
- 收据 `~/.finance-runtime/sixth-round-live/receipt.json`
- sidecar 已停；8792 仍 `15510ad7`（不为文档追切）
