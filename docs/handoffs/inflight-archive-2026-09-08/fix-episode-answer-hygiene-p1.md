# fix/episode-answer-hygiene-p1

## 这个分支做什么
P1 公开稿护栏：Q1 未尝试声称改口；Q3 残稿减句回退。Q2 不做。

## 当前状态
已合 **#285** `4a1abf79`（head `309cec07`）。**2026-08-21 已切 8792 → `dfc25221b07b`**（回滚 `48369a313ff5`），live 四跑已跑。主检出 `feat/reading-rules-baseline-batch1` 脏树勿动。展开：`docs/handoffs/2026-08-21-episode-answer-hygiene-p1.md`；切换读数见 `docs/handoffs/inflight/main.md` 顶部行。

## 未验证 / 已知边界
Live 锂矿/铝/电网**已跑**（2026-08-21，sidecar :8796）：三题判据全过，四跑 `unattempted_claim_count=0`。**但只证了「有收据不改口」这半边** —— Q1 改口路径、Q3 减句回退**一次都没触发**，机制仍只有离线证据，`R-20260820-09`/`-10` 保持 `pending`。与 #222 未共存。`R-20260820-11` 已改记 `deferred`。

## 下一步
1. 8792 已切、live 已跑，两项都不用再做。
2. 想给 `-09`/`-10` 攒 live 证据：得**造出会触发的形状**——无资讯 trace 且稿含缺口声称（Q1 改口），或 repair 把稿塌成残句（Q3 回退）。自然题跑不出来。
3. 新活从 `gitea/main` 开干净树。

## 踩过的坑
- Q3 只挂判官 repair 后。挂 preflight 会把 Q1 改口稿当残稿，把「未返回」交还用户。
- 修前稿 <80 字地板：否则玩具稿全被 withhold。
- C3 不要减句，整篇修前稿（空 `rejected_sentence_indexes`）。
- 对账看 traces 的 capability（`directional_news`），不要用工具名 `news_search`。

## 已验证
定向 190 passed；收据 `~/.finance-runtime/test-receipts/20260820T164557Z-48369a31.json`。合入前 ruff 绿。模块 `intelligence/services/episode_answer_hygiene.py`。

## 工具沉淀
KIT 已有「Episode 公开稿对账」。未抽脚本：要对账 capability 语义。
