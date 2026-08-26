# feat/reading-rules-baseline-r3

## 这个分支做什么

KOL 判读方法内置为领域基线（默认开）；判断倾向留 perspective_lab 显式开关。
本分支 = r2 的 10 笔 rebase 到 `gitea/main@6c47450e` + 1 笔开关板登记
（`predicate.reading-baseline` 转 active/exists、进臂、默认盒重生成）。
#343 已关闭留指针，接替 PR **#414**。前身分支 `batch1` / `r2` ref 保留未动、无 force push。

## 当前状态（2026-08-26 15:00）

树 `/Users/a77/fwp-wt-reading-rules-r3` @ `2b7fc538`。
全量 pytest **6569P / 12S / 0F**（/Users 树）；ruff 绿；#222 共存钉绿
（`test_reading_baseline_and_perspective_coexist_in_episode_input`）。
#414 mergeable=true。**合并等用户确认**；落生产需独立切流窗口（不与 08-26 执行队列共用）。

## 未验证 / 已知边界

- 从未 live；总开关 A/B 零数据（合并切流后另跑）。
- G1a（封板时间有数无块）未做；G1b（`open_times` 全 NULL）需用户在场外呼，SPT-A06 仍 pending。
- `user_framework` 故意没建；B 类 4 条未落地。

## 下一步

1. 合 #414（等用户确认）→ 切流窗口另排。
2. G1b 用户在场：CDP + fupanhui 对 payload 字段名。
3. G1a 与 G1b 齐了再激活 SPT-A06。
4. 总开关 A/B。

## 踩过的坑

- rebase 唯一冲突在 `episode_protocol.py` import（main 侧加了 `FORWARD_HYPOTHESIS_OUTPUT_IDS`），并集即解；spec 预测的 `market_timeseries.py` 未冲突。
- 开关板两钉按设计翻红（pending-other-branch 假设随落地失效）——翻登记 + 翻钉 + 重生成默认盒，不是删钉。
- 全量必须在 /Users 下的树跑：/tmp 树 codex 沙箱探针会 unproven 假红（08-21 交接已有此坑，08-26 预演树再证一次）。
