# feat/methodology-promotion-certification · 工单 #42（OPT-04 第一刀）

## 这个分支做什么
`lifecycle.derive_state` 只认**同身份 + 预声明阶段 + 顶层最终结论**的收据链，按身份变化 / refuted 切验证轮次。堵 PR #607 留下的四个误晋升路径：跨版本拼链、读 `stats.verdict` 忽略 BH、任意 supported 贪心成链、失效后一份成功复活。工单 `2026-09-08-methodology-promotion-certification-workorder.md`；上游补强 spec PR #680 OPT-04。

## 决策与被否方案
- 状态仍从收据**推导**，不落实验账；否了新建 `validation_cycle_id` 账本——多一个真源会漂，spec 要求新账先登记台账地图。
- 字段叫 `declared_stage` 不叫 `stage`；否了 `stage`——`by_market_stage[].stage` 已是大盘阶段。
- 证伪不需要声明阶段，晋升需要；否了对称——失效监测跑不带 `--stage`，对称就没人能被证伪。
- 同窗重跑取**最新**一份、同级不许换窗；否了「任一 supported 即过」——那就是事后挑窗。
- **未改经验卡统计门**（`cli.py` 读 `latest_receipt` 单份 supported 即放行常驻卡）：接 lifecycle 会让常驻卡要求三段门，是产品行为变化，等用户拍板。

## 当前状态
已提交 `ca9cae5d`（代码 + 测试 + 工单 + INDEX #42 行），基线 gitea/main `f90af450`。推送 / PR 见本文件提交后的 PR 号。

## 已验证
- `test_methodology_lifecycle.py`（34）+ `test_methodology_backtest.py`：103 passed；ruff 0；pre-commit 全 Passed。
- 新夹具对旧 `lifecycle.py` 实测 17 红（stash 回旧文件跑过）。
- `queue` 对真规则目录冒烟通过；本机 `methodology/receipts/` **无**规则收据（只有 `event_pricing/`），无存量方法被降档。

## 未验证 / 已知边界
- 未跑全量 pytest；未跑真库 `run --stage`（旁路库未建）。
- `scan` 收据带 `--stage` 时按 BH 后顶层 verdict 计入，`exploratory` 标记不参与判定——spec 没定死，先按「声明即计入」。
- 别的机器若有旧收据：全部无 `declared_stage` → 队列显示 candidate + 历史观察，需按阶段重跑；这是 spec「不自动补通过身份」的预期后果。
- 只堵「同级换窗」；无期限探索要靠 OPT-05 尝试账，本单不做。

## 下一步
1. 用户确认合 PR；合后 INDEX #42 行改 ✅ 并写合入 sha。
2. 拍板是否把经验卡门接到 `derive_state(...).in_method_library`（另开一刀）。
3. OPT-01（`river.py` 阻断错误 strict 宣称）下一单，同流程。

## 踩过的坑
- `rg` 全仓无过滤会卡 30s+（数据产物目录）；限定 `intelligence/ scripts/`。
- INDEX #33–#41 已被在途分支占用（跨全部 ref `git grep '^# 工单 #'`），本单直接用 42。
