# docs/takeover-closeout-1004 在途交接（2026-10-04）

## 这个分支做什么
Claude 接手 codex→arena 的 harness 质量闭环：回收 /tmp 未提交的 10-02 文档，并写接手交接与逐树去向。
全文见 `docs/handoffs/2026-10-04-claude-takeover-closeout.md`。

## 决策与被否方案
| 采用 | 否决 / 理由 |
|---|---|
| FINANCEWORKS-6 先退出 harness 交付损失（切句分支） | 否 arena cc1888e71：坏例驱动、对所有材料题常驻、作者与判官同改 |
| 强模型对照沿用 08-27 react 臂（用户决定） | 本轮不新跑；只能当「强模型+薄循环」参照 |
| 本地独有分支只备份 gitea | 否推 GitHub：公开仓，内容未审 |
| 拆树先出表、等用户点头 | 否本轮直接拆：多棵归 Codex/Pi/arena，嵌套树被工具误报挡住 |

## 当前状态
本分支只有文档，PR #39：三份回收的 10-02 文档 + 接手快照 + 本文件。代码改动是 PR #40（全量门禁 20400 passed / 0 failed）。
arena 的 PR #38 待用户裁决。都未合入，合入须用户确认。

## 已验证
回收件 sha256 与 /tmp 原件一致；19897 已停、8792 healthy；ffe1 已上锁；5 条本地独有分支在 gitea 的 SHA 逐条一致；任务板 1/5/6/13 已留言。

## 未验证 / 已知边界
- 去向表是 16:25 的板面，之后可能有树进出；回收前重跑 `worktree_board.py --landed`。
- arena cc1888e71 全量 18 红全在 tests/test_pi_review_repair.py；同一批测试在 PR #40 门禁里全绿，判为环境红。
- 首稿结构合法 10/20 不等于真实交付率或质量提升。

## 下一步
1. 用户确认两份 PR，切句改动按 8792 规程部署。
2. 预注册 GLM 同模型旧/新配对（holdout）；前置是运输与费用硬边界，Pi 记 live_ready=false。
3. 用户点头后先 apply 无阻塞的 2 棵（dry 收据在 closeout/），再修 worktree_safety 的祖先目录前缀误报（主检出、/private/tmp）。

## 踩过的坑
- zsh：`"$b:refs/..."` 被当成 `${b:r}` 修饰符，要写 `${b}`；不加引号的 `$F` 不分词。
- taskctl 写操作要 `--thread-id`，不传会返回 USAGE_ERROR，宽松解析会把它当成功；写完要读回核对。
