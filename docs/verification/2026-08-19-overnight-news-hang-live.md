# 隔夜新闻挂载 live（2026-08-19）

> 代码：`feat/overnight-news-hang` @ `87f3c5c0`（PR #221）  
> sidecar `:8796`，隔离用户 `overnight-news-hang-2`  
> 生产 `:8792` 只读 health，仍 `15510ad7`，未切  
> 入口：`POST /api/conversations` → `.../messages`（`continuous_episode`）  
> 未用：`live_probe ask` / `POST /api/runs`

## 题目

「基于周二的盘面数据，你认为主线是什么。今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会」

## 判定

**挂载通过。** 第一次 sidecar（`d969cc51` / `run_20260819_113527_705804`）`market_data` 21 条全是行情，新闻 0。原因：`as_of` 用了 A 股 `served_date=2026-08-18`，东财隔夜标题是北京时间 08-19；检索词「美股科技」要求标题整词命中，真实标题是「美股…科技/存储」。第二次 sidecar（`87f3c5c0`）改用 episode `information_cutoff` + 检索词「美股」后，第一次 `market_data` 观察就带上 6 条 `news_search`。模型不再另调 `news_search`。

## 读数

| | 第一次（空挂） | 第二次（本发） |
|---|---|---|
| 代码 | `d969cc51` | `87f3c5c0` |
| run | `run_20260819_113527_705804` | `run_20260819_114317_390006` |
| 第一次 `market_data` 里的 `news_search` | 0 / 21 | **6 / 27** |
| 新闻日期 | （模型后来自调，全 08-19） | E22–E27 全 **2026-08-19** |
| 模型是否再调 `news_search` | 是 | 否 |
| Yahoo 领跌 | 有 | 有（费半/NVDA/MU/HYNIX/SNDK） |
| 发明 2.2万亿 / 60 / 27% | 无 | 无（成交 24006 亿） |
| 【互斥因果假说】 | 有（靠后调新闻） | 有；H1 存储周期 vs H2 AI 基建抛售，用 E23 新闻 + E18–E21 相对强弱 |

本发挂上的标题：美债破 6（噪声）、AI 基建抛售波及港股、存储盘后速递、海力士/闪迪跌超 9%、存储芯片重挫、存储/光通信集体重挫。

## 残留

- 检索词「美股」会捞到美债标题（E22）。标题百分比仍可能被核验裁成未绑定时间戳——不放宽 verification。
- 纯 A 股预测题仍不应取新闻（单测锁了；本 sidecar 没复跑对照题）。
- 不合、不切 8792。

## 产物

- 收据 `~/.finance-runtime/overnight-news-hang-live-2/receipt.json`
- sidecar 已停；8792 仍 `15510ad7`
