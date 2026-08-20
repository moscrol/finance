# fix/episode-answer-hygiene-p1

## 这个分支做什么
P1 公开稿护栏：Q1 未尝试声称改口；Q3 残稿减句回退。Q2 不做。

## 当前状态
已合 **#285** `4a1abf79`（head `309cec07`）。**未切 8792**。主检出 `feat/reading-rules-baseline-batch1` 脏树勿动。展开：`docs/handoffs/2026-08-21-episode-answer-hygiene-p1.md`。

## 未验证 / 已知边界
Live 锂矿/铝/电网 `not_run`。与 #222 未共存。Q2 / `R-20260820-11` deferred。

## 下一步
1. 不要切 8792，除非用户另拍。
2. 用户要 live：锂矿窗口截断不得改口；电网有收据不得改口；铝未查才改口。
3. 新活从 `gitea/main@4a1abf79` 开干净树。

## 踩过的坑
- Q3 只挂判官 repair 后。挂 preflight 会把 Q1 改口稿当残稿，把「未返回」交还用户。
- 修前稿 <80 字地板：否则玩具稿全被 withhold。
- C3 不要减句，整篇修前稿（空 `rejected_sentence_indexes`）。
- 对账看 traces 的 capability（`directional_news`），不要用工具名 `news_search`。

## 已验证
定向 190 passed；收据 `~/.finance-runtime/test-receipts/20260820T164557Z-48369a31.json`。合入前 ruff 绿。模块 `intelligence/services/episode_answer_hygiene.py`。

## 工具沉淀
KIT 已有「Episode 公开稿对账」。未抽脚本：要对账 capability 语义。
