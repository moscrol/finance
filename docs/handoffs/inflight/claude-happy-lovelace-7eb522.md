# 在途交接 · claude/happy-lovelace-7eb522

## 这个分支做什么

把七轮一次性收口脚本收进仓内：新 `scripts/worktree_closeout.py`（点名、dry-run 收据即计划、先保全再拆），`worktree_board.py --landed`（内容落地比例），`worktree_safety.py` 新只读原语；顺带修 `cleanup_gate_trees.sh` 两个洞。全文 `docs/handoffs/2026-09-28-worktree-closeout-tool.md`。

## 决策与被否方案

- 新脚本，否扩 cleanup / board：扫描器加保全 = 拆脏树的自动扫（09-23 否决）；board 只读。
- DuckDB 残留 clonefile 克隆，否 tar/zstd/`cp -c`：压缩是新数据，`cp -c` 跨卷静默整份拷。
- 回滚锚不自动判，否接部署账本：锚是人指定的，规则判不准。

## 当前状态

代码、测试、AGENTS.md 指针、教训、本交接已提交在本分支。四叶在该 head 上跑，读数贴 PR 评论；合入等用户确认。未对任何真实树 `--apply`。

## 已验证

- 相关四测试文件 121 条绿（沙箱外；沙箱里 cleanup 测试的 mktemp 被拒）。
- 真实仓只读：board `--landed` 28 棵 12 秒；dry-run 点名 4 棵报 CLEAR，诊断为 8792 已切 8e45（12:29），检测正常。

## 未验证 / 已知边界

- apply 只在临时仓测过：推送走本地裸仓，没推过真 Gitea（refs/archive 推送 09-28 旁证可行）；clonefile 只在同卷 APFS 测过，跨卷失败路径靠注入。
- 残留 tar 只核名单与大小，不逐文件哈希；超 5 MiB 的未提交文件不进封存分支，只在补丁 / 残留包。

## 下一步

1. 看 PR 评论四叶读数；红就修。
2. 合入后先对一棵确定可拆的树走 dry-run → apply，核收据的 statvfs 差与归档目录，再批量。

## 踩过的坑

- porcelain 锁理由默认八进制转义：Python 侧用 `worktree_board.unquote_c`，shell 侧 `-c core.quotePath=false`。
- 探针的临时目录建失败会静默落回本仓：断言 `rev-parse --show-toplevel` 再动手。
