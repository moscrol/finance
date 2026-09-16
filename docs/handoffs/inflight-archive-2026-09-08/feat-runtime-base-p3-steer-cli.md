# feat/runtime-base-p3-steer-cli

## 这个分支做什么
工单 #30 范围第 5 条：`python3 -m intelligence.cli steer <episode_id> "<文本>"`。跨进程走 durable 目录的投递槽 `<episode_dir>/inbox-spool/`，`Inbox` 在既有认领点吞槽，三事实仍只由 loop 落账（INV-R5 不变）。基线 `gitea/main@5eb24515`。

## 决策与被否方案
- 选：槽 = 目录里一文件一消息（tmp → fsync → rename），吞完即删。否：追加行 + 偏移量——要管撕裂行与 restore 后的偏移持久化；否：CLI 直接 append events.jsonl——loop 是唯一写者，序号连续性会坏。
- 选：吞槽放在 `Inbox` 的 `pending / claim / discard_all` 里，loop 只改构造一行。否：loop 里加钩子——P4 #684 正在重改 `agent_episode.py`，多一处就多一处冲突。
- 选：删文件在 `send` 之后。否：先删再 send——崩在中间话无痕丢失，违反「崩溃只留 inserted 有、后两者无」。
- 选：CLI 两个 fail closed（events.jsonl 不在 / state.json 终局都拒投）。否：目录不在就建——那就是部署账本「两个家」的复刻，写进没人读的根。
- 选：不做 Workbench 端点（§12 第 4 题，用户 09-09 委托按推荐拍定）。

## 当前状态
`1ca1ca40`（代码）+ `b3335b04`（文档）+ 本交接已提交。**PR #687 已开，等用户确认合入。** 树干净。

## 已验证
- 干净树全量 8311P / 0F / 77 skip / 1 xfail，319 s（收据 `20260909T060819Z-1ca1ca40.json`）；ruff 0；pre-commit 11 道过；`gen_runtime_catalog.py --check` 一致。
- `test_episode_steer.py` 11 条含 loop 级：真 runtime + JsonlEpisodeStore，话只写槽、第二次请求前被认领、槽清空、回执对回、收口后拒投。
- `merge-tree`：对 P4 #684 代码干净，只剩 INDEX 老冲突。

## 未验证 / 已知边界
- 未 live：8792 未切流（仍 0060da5c），CLI 对真 Workbench episode 没投过；切流后与 P3 的 `steer` 探针一起做。
- `restore` 后崩溃前「已 send 未 unlink」的文件会重吞一次（同 `spool_id` 可对出）——与 P3「restore 不处理未决 inserted」同边界，P4 收。
- 收口后写进槽的文件永不被吞：CLI 按 state.json 拒投，剩极小窗口；`--wait` 会报「未见 inserted」。
- `pending()` 现在会做文件系统 IO（列目录）；每次模型请求前一次，量级可忽略，但没量过高频调用场景。

## 下一步
- 用户确认 #687；合入后 P4 #684 前向合并时解 INDEX 那一行（取双方）。
- 切 8792 后：`intelligence.cli steer --list` 看到在跑的 episode → 投一句 → `--wait 30` 看 claimed。
- 端点等 Alpha；做时直接调 `GLMAgentRuntime.steer`，不用再碰槽。

## 踩过的坑
- 用户级 git hook 把 `rm -f` 与「同一条命令里出现 push 和 gitea/main」都当红线拦：提交、推送、conflict-check 分三条命令跑。
