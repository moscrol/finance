# feat/methodology-promotion-certification · 工单 #42（OPT-04 第一刀）

## 这个分支做什么
`lifecycle.derive_state` 只认**同身份 + 预声明阶段 + 顶层最终结论**的收据链，按身份变化 / refuted 切验证轮次。堵住 PR #607 留下的四个误晋升路径：跨版本拼链、读 `stats.verdict` 忽略 BH 校正、任意 supported 贪心成链、失效后一份成功复活。工单 `docs/superpowers/specs/2026-09-08-methodology-promotion-certification-workorder.md`；上游补强 spec PR #680 OPT-04。

## 决策与被否方案
- 状态仍从收据**推导**，不落 `experiment_id / validation_cycle_id` 账本；否了新建实验账——多一个真源会漂，且 spec 要求新账先登记台账地图。
- 收据新字段叫 `declared_stage`，不叫 `stage`；否了 `stage`——`by_market_stage[].stage` 已是大盘阶段，会撞名。
- 证伪不需要声明阶段（同身份 refuted 照旧掉档）；晋升需要。否了对称处理——失效监测跑不会带 `--stage`，对称就没人能被证伪。
- 同窗重跑取**最新**一份，不许同级换窗；否了「任一 supported 即过」——那就是事后挑窗。
- **未改经验卡统计门**（`cli.py` 读 `latest_receipt` 单份 supported 即放行常驻卡）：接到 lifecycle 会让常驻卡要求三段门，是产品行为变化，等用户拍板。

## 当前状态
未提交（本文件写完即提交）：`lifecycle.py` 重写推导、`receipts.py` 加 `declared_stage` + md 一行、`scripts/methodology_backtest.py` `run/scan --stage` + `queue` 传规则文件 sha256、两份测试、工单 + INDEX #42 行。未推送、未开 PR。基线 gitea/main `f90af450`。

## 已验证
- `test_methodology_lifecycle.py`（34）+ `test_methodology_backtest.py`：103 passed；ruff 0；pre-commit 全 Passed。
- 新夹具对旧 `lifecycle.py` 实测 17 红（stash 回旧文件跑过），不是空转。
- `queue` 对真规则目录冒烟通过；本机 `methodology/receipts/` **没有**规则收据（只有 `event_pricing/`），无存量方法被降档。

## 未验证 / 已知边界
- 没跑全量 pytest（只跑目标套件）；没跑真库 `run --stage`（旁路库未建）。
- `scan` 收据带 `--stage` 时按 BH 后顶层 verdict 计入；`exploratory` 标记未参与判定——spec 对「探索产物能否当验证证据」没定死，先按「声明即计入」。
- 换机器若 `methodology/receipts/` 有旧收据：全部无 `declared_stage` → 队列显示 candidate + 「历史观察」，需按阶段重跑；这是 spec「不自动补通过身份」的预期后果，不是回归。
- 事后挑窗只堵「同级换窗」；跨规则族的无期限探索要靠 OPT-05 尝试账，本单不做。

## 下一步
1. 用户确认合 PR；合后 INDEX #42 行改 ✅ 并写合入 sha。
2. 拍板是否把经验卡门接到 `derive_state(...).in_method_library`（另开一刀）。
3. OPT-01（`river.py` 阻断错误 strict 宣称）下一单，同流程。

## 踩过的坑
- `rg` 全仓无过滤会卡 30s+（数据产物目录）；限定 `intelligence/ scripts/` 即可。
- INDEX 编号 #33–#41 已被 `docs/closeout-workorders-0908` 等在途分支占用（跨全部 ref `git grep '^# 工单 #'` 得到的），本单直接用 42。
