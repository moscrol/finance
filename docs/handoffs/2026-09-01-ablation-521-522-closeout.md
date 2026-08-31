# 2026-09-01 · #521 / #522 消融噪声底 + 判官独立性收口

执行会话合入后撞限额，本文件是收尾。代码已在主干，本单只改交接。

## 落地

依序入 `gitea/main`：

1. **#521** `feat/ablation-noise-floor` → main = `d31d2197`（方差门 + 三行登记 + 质检收口 `0874c829`）
2. **#522** `feat/ablation-judge-independence` → main = `fb17879a`（独立判官 + rubric v3 + 两个洞 `1e4df572`）

`1e4df572` 是 `fb17879a` 的祖先。两 PR 均 `state=closed merged=True`。

**未切 8792 / 8796 / 8802。** 合 main ≠ 上生产。收尾时三口仍是
`5be00c4f` / `40fd5a84` / `5d7529e5`（8802 仍 dirty，与本单无关）。

## 合入前补上的两个洞（都在 `1e4df572`，已随 #522 进主干）

1. **家族优先于传输。** `resolve_judge` 不再因 `transport==cli` 抬成 `independent`。
   现场：`grok-cli-judge/gpt-5.6-sol`（CLI + 同族 gpt）必须是 `weak`。
2. **补评走同一道闸。** `rejudge_quality_ablation` 调 `resolve_judge`，默认 `require`。
   主轮堵自审、补评侧门放行，正是这条分支要堵的形状。

测试：`test_同族走cli也不算独立`、`test_补评也过判官独立性闸`。
执行方全量自称 7350P / 15S / 1x @ 补洞后脏树；本收尾未重跑全量。

## 仍挂着（不是本单没做完）

- 三行不进 `default-v1`，进盒需另一次对照 + 点头
- `fast-path-runner` / `repair-chain` 要真进臂，先造关法
- `knowledge_injection_policy` 市场态门控已在生产，拆不拆另开单
- kappa 校准、grok-cli 完整 require 消融、天花板（加难题或抬满分锚）未做
- runner `_RUNNER_APPLIES_KINDS` 仍只有 `capability`（20 拧得动 / 25 `not_implemented`）

在途稿 `docs/handoffs/inflight/feat-ablation-noise-floor.md` 已改头，勿再读「未合 main」。
