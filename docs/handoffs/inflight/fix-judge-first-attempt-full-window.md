# fix/judge-first-attempt-full-window

## 这个分支做什么
grok 判官首发从半窗 25s 改成整窗 50s，罩 46.7s 尾巴。

## 当前状态
已合 **#276** `cce84cf2`，`gitea/main` 含它。**未切 8792**（仍 `b58a7a9b`）。
正文 `docs/handoffs/2026-08-20-judge-first-attempt-50.md`。

## 未验证 / 已知边界
- 从未 live。部署后才看得到 `timeout_asked=50`。
- 默认 T=120 被 T/3=40 卡住；生产 T=300 预留 60。
- leftover 只查 episode 剩余，不查 `window_left`（半截重试洞，本轮没修）。

## 下一步
1. 用户拍板才切 8792。
2. 切后看首轮 `timeout_asked=50`；46.7 那种尾巴还超时不算修好。

## 踩过的坑
- 探针必须复刻适配器 argv（`--max-turns 1` / `--json-schema` / `--no-plan` / `effort=low`）。漏了会报 >120s 假数。
- 交接原文 cap 45 + 窗 75 → `min(45,37.5)=37.5`，罩不住 46.7。
- 合 PR 走本机 Gitea API；禁本地 merge/push main。脏主树别碰。

## 工具沉淀盘点
无新脚本。argv 探针是语义判据，未脚本化。

## 已验证
离线 DEFAULT/窗/complete 都是 50；leftover(49) 拒、(50) 放行。质检双轴无硬违规、无 spec 缺口。
