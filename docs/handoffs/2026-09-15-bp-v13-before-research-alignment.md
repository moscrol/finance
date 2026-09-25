# docs/bp-v1.3-roadshow-align · 2026-09-15 晚 · BP 落库 + v1.3 对齐路演口播稿

## 这个分支做什么
纯文档。工作树 `/Users/a77/fwp-wt-bp-v13` 从 `gitea/main@1fef3d27` 新开，两笔提交：
1. `b2f0a8d5` 落库 BP v1.2 母本、对外版、财务假设 JSON、internal 归档、`scripts/build_bp_public.py`、`scripts/render_bp_pdf.py`、`tests/test_build_bp_public.py`。这些自 09-07 起只在主检出树以未提交/未跟踪形式存在（gitea/main 母本仍是 v0.6；09-12 salvage 快照 327242d9 自述不合 main）。逐字节复制，内容不改。
2. v1.3：与 foresight 仓 `gtm/2026-09-15-roadshow-8min-talktrack.md` v2.2 和桌面 pptx v3 对齐。§2「现在能展示什么」收窄为已走通的「记判断 → 到期回检」；§2 补 09-07 后合入主干的内容版本冻结与历史重放、情景树首版、相关样本依赖检验、合取式标签三值逻辑；§3「三条种子规则未过门」改「四条无一条通过 + 85 信号 / 15 交易日 / 3 完整块判样本不足」；资料来源加第 6 条；deck.md（Marp）头部标为历史稿。财务仍 v0.9。

## 决策与被否
- 基准是口播稿（最新、过三岗、与 foresight `product.md` 核心痛点一致）；BP 与 pptx 向它对齐，不反向改稿子。
- 85/15/3 上材料前先在本树重跑：`MARKET_FEATURE_STORE_DB=<主树 db> python scripts/methodology_backtest.py scan --rules-dir methodology/rules --to 2026-03-31 --stage discovery --refuted-dir /tmp/...`（scan 子命令没有 `--db-path`，旁路库跟主库同目录）。读数与 09-11 收据（提交 7a55deb0 / PR #736）逐项一致；已按格式追加进 foresight `docs/validation.md` 记录 M-001。
- 未把 §3「数据飞轮」改成学习曲线叙事（09-14 advisory 的建议，用户未拍板）。

## 已验证
`build_bp_public.py --check` OK；`tests/test_build_bp_public.py` 14 passed；ruff 过；预提交门禁过；`render_bp_pdf.py` 回读 8 页 = 8 区块；对外版 `rg "预测|涨跌|/Users/"` 清零。产物：桌面 `01-Foresight-BP与路演/Foresight-BP-对外版-v1.3-2026-09-15.pdf` 与 `2026-09-finance-agent-bp-对外版.md`（v1.2 的 md 改名 `…-v1.2-2026-09-07.md` 保留）。

## 未做 / 边界
- 申请表 DOCX 与 BP 可编辑 DOCX 未重生成（v1.3 改动不涉及申请表三格；本机无 LibreOffice，见 HEAD.md）。
- pptx v3 在桌面 `Foresight-路演-v3-2026-09-15/`（guizang + Codex 运行时管线，`.build/` 含四个脚本），不进仓；第 5 页演示位的脱敏截图待创始人插入。
- 未合 main，等用户确认；主检出树 `docs/bp` 的未提交改动未动（属他人树）。
- 财务 JSON 仍 v0.9；`offer.yaml` 仍 draft。

## 下一步
用户过目 PDF v1.3 与 pptx v3 → 确认后合 main（`--no-ff` 或 PR）→ 删分支与 `fwp-wt-bp-v13`。口播稿 v2.2 真人计时与三人复述测试是下一个读数。
