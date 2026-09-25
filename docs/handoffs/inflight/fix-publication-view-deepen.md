# fix/publication-view-deepen

## 这个分支做什么

P0-A：加深已有 `session_projection.view`，止住 knevo28 B2 形难看稿。不新开 `PublicAnswerCompiler`，不重开 D1，不动 P0-B。

1. `invalid_repair_finish` + 证据非空 → 成因 `verification_incomplete`，开口不是「现有证据不足」。
2. 未兑现槽由 `TerminalFacts.unknown_slots` 经 `view()` 渲成「这次还核验不了」，禁止 `【结构缺口】`。
3. adapter 不再调用 `ensure_preplaced_gap_sections` 改公开稿。
4. `finance_query` 收据按工具身份投影到 `market_data` / `mainline_context`。

## 当前状态

树 `/Users/a77/fwp-wt-publication-view-deepen` @ `fix/publication-view-deepen`，基线 `gitea/main@b07259c0`。代码已写，全仓离线绿。**未合 main、未切端口。**

| 检查 | 结果 |
|---|---|
| 全仓 pytest | 6281 passed / 13 skipped（收据 `~/.finance-runtime/test-receipts/20260824T034903Z-b07259c0.json`，文件名 SHA 是基线；工作区当时 dirty） |
| layer_audit | ERROR 0 |
| path literals / unread fields | 无新增 |
| ruff | 本单文件过 |
| 8792 / 8796 | 未切 |

台账：`R-20260824-12`/`-14` 离线夹具已绿，live/矿重放未跑，**不得 confirmed**。`-13` 等 28 题重放。`-15`…`-19` 只占号，P0-A 合入后再动。

## 未验证 / 已知边界

- 未 live，未重放 knevo28 矿。夹具绿 ≠ QC marker=0 已在 28 题成立。
- `finance_query` 工具身份同时满足 `market_data` 与 `mainline_context`。比「对 dataset 名字做子串」紧，比「必须带 sector_daily 字段」松。矿重放若仍有假缺，再收窄 dataset 表，不要改回字符串启发。
- 普通 `model_finish` 缺口仍走「现有证据不足」（中间档测试未改）。
- adapter 里 `_episode_gap_answer` 等旁路仍自己拼串；本单只拆出口后缝合。
- 未把 spec v2 文件并进本支（规格在另一棵 docs 树）。

## 下一步

1. 你确认后合 `gitea/main`。合前 `merge-tree` 自探，别信 Gitea `mergeable`。
2. 不要切 8792/8796，除非你另说。
3. 合入后再开 `feat/research-program-compiler`（P0-B）。不要在这支续写 program。

## 踩过的坑

- B2 难看稿不是禁语漏网：成因误贴 + `view()` 之后再缝 `【结构缺口】`。再造编译器会变成第二张措辞表。
- `_gap_answer` 普通 gap 仍禁止从 draft 捞正文。只有 `verification_incomplete` 且已兑现槽才把 draft 写入 `public=`。

## 已验证

`test_publication_view_deepen.py`（B2 形 n=3 + adapter 缝合=0 + typed receipt）+ `test_gap_answer_middle_tier.py` 新成因 + `test_session_projection.py` 五类首句互不相同。
