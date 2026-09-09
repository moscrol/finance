# fix/board-ledger-freshest-switch

## 这个分支做什么
`worktree_board.py --this`（SessionStart 注入的「8792: …」那行）把生产报成一天前的 rev。两份部署账本都在时，读取侧改为取该 port 末次 switch 最新的那份。

## 决策与被否方案
- 选：只改读取侧 `resolve_ledger_path`，在**存在的**候选里按 8792 末次 switch 的 `unix` 取最新；都没有 switch 行退回覆盖序。否：改覆盖序（把 `~/.finance-runtime` 提到 `<repo_root>/state` 前）——写入侧 `deploy_ledger.resolve_ledger_path` 同序，改一处两边就不对齐，且 dev server 从主树起时仍会往 `state/` 写。
- 选：不碰 `last_switch_for_port`。否：顺手合并「未归属行」逻辑——那是 #572 在改的函数，改了两张必冲突；现在可任意顺序合。
- 选：只认 `unix` 字段，不解析 `ts` 字串。否：双字段兜底——同源，多一套解析多一处漂。
- 写入侧的分家（`<repo_root>/state` 第 4 级）**不在本单治**，另立单。

## 当前状态
已提交 `1e01693d`（`scripts/worktree_board.py` + `tests/test_worktree_board.py`），基线 `gitea/main@368b7a66`。PR 已开，等用户确认合入。

## 已验证
- `tests/test_worktree_board.py` 11 绿；变异（改回 `existing[0]`）新用例红。
- 真账本：本树 `--this` 与 `session_facts.sh` 输出 `8792: 0060da5c1a08`，与 `audit_deploy_ledger.py check`（ledger_rev = health_rev = 0060da5c）一致；改前是 `b594a5e7f8ae`。
- 全量门禁读数见 PR 正文（本树 `/Users/a77/fwp-wt-board-ledger`，不在 `/tmp`——见坑）。

## 未验证 / 已知边界
- `FINANCE_WS` / `FINANCE_DEPLOY_LEDGER` 设了时仍按显式路径取，不比时刻（与旧行为同）。
- 旧格式行没写 `unix` 的账本按 -inf 处理：全是旧格式时退回覆盖序，行为不变；新旧混合时新格式那份会赢——这是想要的。

## 下一步
- 合入后 SessionStart 自动生效（`session_facts.sh` 调 `--this`），不用切 8792。
- 另立单：写入侧为什么会有两个家（主树 `state/` 279 行 vs `~/.finance-runtime` 24 行），是否让 `record` 只认一处。
- #572 合入后跑一次 `tests/test_worktree_board.py` 确认两张叠加无回归。

## 踩过的坑
- 旧用例 `test_ledger_falls_back_to_git_common_dir_parent` 没密封 `Path.home`，宿主真账本会盖过夹具——已补 monkeypatch。
- 全量门禁别把 worktree 建在 `/tmp`：`test_installed_codex_sandbox_denies_network_and_unix_socket` 用真 Codex 沙箱试读仓根 `AGENTS.md`，macOS 沙箱放行 `/tmp` 读，会得到一个「意外成功」的假红（09-08 实测，`/Users` 下同探针 proven）。
