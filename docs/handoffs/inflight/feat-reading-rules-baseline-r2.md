# feat/reading-rules-baseline-r2

## 这个分支做什么

KOL 判读方法内置为领域基线（默认开）；判断倾向留 perspective_lab 显式开关。
本分支是 `feat/reading-rules-baseline-batch1` rebase 到当前 `gitea/main` 的收口树。

## 当前状态

树 `/Users/a77/fwp-wt-reading-rules-baseline`。`rebase --onto gitea/main 1df6844d` 已完成（9 笔，丢掉已入 main 的 L2）。
`#222` 已在 main：补了 payload/合成两处共存钉。主仓脏树未碰。
**未合 main。** `edd5c5ba`（晨汇 U+FFFD / matcher 课）不进本单。

## 未验证 / 已知边界

- 从未 live；总开关 A/B 零数据。
- `#222` 只做了离线共存，没跑 single 视角 live。
- `user_framework` 故意没建。B 类 4 条未落地。
- G1a（封板时间有数无块）未做。G1b（`open_times` 全 NULL）需你在场外呼，SPT-A06 仍 pending。

## 下一步

1. 合本 PR（等你确认）。
2. G1b 你在场：CDP + fupanhui 对 payload 字段名。
3. G1a 与 G1b 齐了再激活 SPT-A06。
4. 总开关 A/B。

## 踩过的坑

- 旧测试 `build_episode_input(frame, context)` 少传 `registry`——main 已改成必参，rebase 后这一处会红，看起来像基线坏了。
- 主仓那棵仍挂旧分支名 + 日常复盘脏区，续做只用这棵干净树。

## 工具沉淀盘点

漂移门禁仍在测试里（要语义判断），未抽到 TOOLKIT。

## 已验证

`intelligence/tests` **5482 passed / 11 skipped**（工作树含共存钉，基线 rev=`05e22f8f` dirty）。收据 `20260822T100609Z-05e22f8f.json`。
