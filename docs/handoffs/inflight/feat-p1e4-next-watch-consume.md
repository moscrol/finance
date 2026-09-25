# feat/p1e4-next-watch-consume

## 这个分支做什么
P1-E4：跟踪题「下期关注」写入既有 `checkpoints.jsonl`，次日 foresight 强制对照。

## 当前状态
**已合 `gitea/main=bbdb8317`（#229）。未切 8792（仍 `441c60f2`）。轨道 C 可开。**

## 未验证 / 已知边界
- 全量四件套未跑（合前按规程只跑定向）。
- Q2 episode E=21 略低于地板 23；两发复核超时（R-06），不挡 E4。

## 下一步
开轨道 C（E2）。不要因 #227「B 可链切」去切 8792。

## 踩过的坑
- 真 `theme_track` 只在会话口。ingest 曾只挂 legacy ask-compose，live 走 `_complete_continuous_turn`。
- helper 在 pytest 下 no-op，接线要用 spy。

## 已验证
r3 live Q1 入账 1 / Q2 入账 3。质检收据 `20260819T082649Z-d11a65f9`。
