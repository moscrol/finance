# docs/inflight-archive-merged-branches

## 这个分支做什么
`docs/handoffs/inflight/` 累到 101 份、94 份分支已不在 gitea。把已合分支的 93 份 `git mv` 进 `docs/handoffs/inflight-archive-2026-09-08/`，每份在 `INDEX.md` 登记「已合」证据；inflight 只留活的 8 份。

## 决策与被否方案
- 选：`git mv` 进带日期的目录，一字不改。否：删除——skill 说「只留在快照」，这些文件本身就是快照，删了外部「见 inflight/x.md」的引用就断；否：拼成一个大 md（09-03 对 `main.md` 的做法）——93 份拼一起 368KB 没法 grep 单份，`--follow` 也追不到。
- 选：三类证据分级（A 合入提交 70 / B 文首自述 7 / C 本地分支 `git cherry +0` 或两边皆无 16），逐份写进 INDEX。否：只看「远端没分支」就搬——squash/rebase 合入没有 merge 提交，弃置的分支也没远端，两者要分开。
- 留 `fix-ceiling-required-block-degrade.md`：本地分支对 gitea/main `cherry +1`，有一个补丁没进 main，不能按「做完」处理。
- 没动 `main.md`（7.7K，超 3K）：那是别人的活文档，压缩要判断哪些还活着，不在本单。

## 当前状态
已提交 `905d7c1a`（93 rename + INDEX.md），基线 `gitea/main@368b7a66`。PR 已开，等用户确认。

## 已验证
- `tests/test_ledger_spec_crosswalk.py` 14 绿。
- `scripts/audit_ledger_spec_crosswalk.py` 读数与 gitea/main 逐字相同（它只扫 inflight 一层）；那 1 个「缺号」error 在 main 上就有，与本单无关。
- `session_facts.sh` 注入行改报「inflight/ 下另有 8 份」；`check_inflight_stale.sh` 只按当前分支 slug 找文件，不受影响。
- 纯文档，ruff 无对象；pre-commit 11 道全过。

## 未验证 / 已知边界
- C 类 16 份里 2 份（`docs-operator-prefetch-os`、`perf-rag-worker-slimming`）本地远端都没分支，按同题 fix 已合 / 项目笔记「#587 已合」判定，没有 git 级证据。
- 外部文档若写死 `docs/handoffs/inflight/<x>.md` 路径，读者要看 INDEX 顶部那句「自本文起指本目录」；没逐个改引用。

## 下一步
- 合入即生效，无切流。
- 想让它不再累积：`check_inflight_stale.sh` 或 `worktree_board.py` 加一条「分支已合且远端已删 → 提示搬归档」的读数（0 档），本单没做。

## 踩过的坑
- 判「已合」不能只看 merge 提交：Gitea 合并有 `from X into main`，GitHub 时期是 `from owner/X`，squash/rebase 什么都没有——后者用本地分支 `git cherry gitea/main <br>` 全 `-` 判。
