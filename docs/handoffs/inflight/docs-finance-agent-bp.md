# 在途交接 · docs/finance-agent-bp

## 这个分支做什么

两件纯文档：
1. 创业比赛 / 孵化器申请用的商业计划书 `docs/bp/2026-09-finance-agent-bp.md`（12 章 + 路演页映射 + 来源 + 待填清单）。
2. 用户 2026-09-04 提出的新方向「历史行情 / 题材编译成结构语言，用历史成功率给纠偏设统计门」的设计稿 `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` 与可分发 P0 工单 `2026-09-04-methodology-backtest-p0-workorder.md`（INDEX #21）。

## 决策与被否方案

- BP 定位：主线卖「证据可追溯的个人研究工作台」面向半专业个人投资者；harness 方法论写成壁垒页不单独卖；机构版放第二阶段。被否：单卖 harness 工具包（是文档不是产品）、直接 To B（无渠道、单人）。
- 合规红线：不写「AI 荐股 / 智能投顾」；产品边界三个不做（不选股、不给买卖时点、不预测价格），依据 2012 荐股软件规定与 2026 防非宣传月口径。
- 数据源：当前会话抓取不作商业叙事，BP 写三步合规化路线。
- 方法论回测形态：规则标签（不做图像识别 / 学习表征）、声明式 JSON → 参数化 SQL（不给 agent 开 run_sql，沿 2026-08-20 决策）、旁路库（不改主 schema）、Wilson + 基准率 + 前后半段四态（不用贝叶斯起步）。
- 形式默认：BP 为 Markdown 长文 + 页映射（问答工具两次回传失败，未拿到用户对形式 / 团队的明确选择，按默认走并在 BP 附录 C 列占位）。

## 当前状态

三份文档 + INDEX 行已落分支，未合 main。BP 中数字：仓内为 2026-09-04 只读核数（52 表 / 413 交易日 / 4,599 实体 / 124 纠偏 / 83 可证伪点 / 7,386 测试通过），外部 21 条来源见 BP 附录 B。

## 未验证 / 已知边界

- 外部数字全部来自媒体转述或三方报告，未核对监管 / 中国结算原文；BP 已注明「口径以原文为准」。
- SAM / SOM 是估算与目标，口径写在 BP §5.1，未经用户确认。
- 定价三档为假设。
- P0 工单未派、未实施；设计稿数字（如 `DEFAULT_CALIBRATION_MIN_N=2`）读自 `checkpoints.py:56`，以实施时为准。

## 下一步

- 用户填 BP 附录 C 占位（产品名 / 创始人 / 融资金额 / demo 截图 / 定价拍板）。
- 按 INDEX #21 派 P0 工单给执行 agent（分支 `feat/methodology-backtest-p0`，从 `gitea/main` 新开树）。
- BP 若要 PPT / Word，从附录 A 页映射压。

## 踩过的坑

- 主检出树在 `feat/content-ops-copilot` 且有他人 51 个未提交改动，故另开树 `/Users/a77/fwp-wt-finance-agent-bp`。
- 本机 `git fetch gitea` 与全树 `git status` 曾长时间挂起；本地 `gitea/main` ref 可直接用于 `worktree add`。
- shell 会话 cwd 不一定在仓内，git 命令要显式 `cd` 或 `-C`。

## 已验证

- 主库只读查询成功（`read_only=True`），四张表区间与行数已入 BP §9.1 与设计稿 §2.1。
- 代码地图查询确认无现成「标签层 / 方法论编译器」实现，只有 `backtest_sector` / `detect_turning_points` / 双红定义。
