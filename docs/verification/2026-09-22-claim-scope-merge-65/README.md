# #65 口径越界 lint（#850 / #854）合入准备 — 证据索引

执行会话 S5（2026-09-22 夜）。本目录只放可提交的文档；收据与日志原件在私有证据根 `~/.finance-runtime/reviews/claim-scope-merge-65-20260922/`（不进仓）。**运行时（`intelligence/`）零改动。**

## 候选身份 [实测]

| PR | head | base | `merge-tree` vs `gitea/main@f24a61a8a` |
|---|---|---|---|
| #850 `fix/answer-claim-scope-0922` | `1cf35f5167ed3adebbb7d6ce60a37f8b92c79d0c` | `main` | clean（预览树 `106f78f6…`） |
| #854 `fix/claim-scope-hardening-0922` | `5f5ce2d114b238edd3f278504e5a25f35f31710d` | `fix/answer-claim-scope-0922`（叠 #850，多 8 提交） | clean（预览树 `463de4fa…`） |

两 PR 共同 merge-base `a2c8d1f9`；main 自此前进 9 提交（1 张合并 #851 + 文档），改动 9 个文件（`market_feature_store/db.py`、`sector_universe.py`、`hithink_sector_preview.py` 与其测试、文档），与 #854 的 32 个文件**零重叠**。`--base-drift-max 5` 口径下漂移 = 1。

## 门禁读数

| 叶 | 树 | 结果 | 原件 |
|---|---|---|---|
| registry 五条 | `/Users/a77/fwp-gate-65/finance-workspace-private`（detached @ `5f5ce2d1`，隔离父目录 + kb / site 同级软链在场） | 5 / 5 exit 0（61 SKILL.md 可解析、注册表无漂移、文档表一致、视图规范、台账 crosswalk 通过） | `registry/1-5*.log`、`registry/identity.txt` |
| #850 head 定向 | `/Users/a77/fwp-wt-answer-claims-0922`（clean @ `1cf35f51`） | `intelligence/tests/test_answer_claim_scope.py` **31 passed**，`dirty=false` | `~/.finance-runtime/test-receipts/20260922T154730Z-1cf35f51.json` |
| #854 head python 全量 | 同上隔离检出 | 待补（准入：1 分钟 load ≤ 8、pytest 进程 ≤ 2；#58 未合，故加 `--ignore=scripts/archive`，收据不记录该收窄，此处写明） | `gate-runner.log`、`~/.finance-runtime/test-receipts/<stamp>-5f5ce2d1.json` |
| #854 head frontend + e2e | 同上 | 待补（`run_frontend_gate.py`，端口 18991 / 18994） | `frontend/frontend.json` |

## 阳性对照（验收第 2 条）[实测 @ `5f5ce2d1`]

| 变异（从 `_RULE_CHECKS` 删一条） | 冻结 run | 变异后 | 还原后 |
|---|---|---|---|
| 删日期规则 | 行情题 `run_20260921_183642_325351`（`--scope-total 20`） | exit 1，命中 3 → 2 | exit 1，三条全回 |
| 删单位规则 | 材料题 `run_20260921_183219_280474` | **exit 0**，命中 0 | exit 1，单位规则回 |

工单验收原文「日期规则注释掉后行情题退出码 1 → 0」在该题不成立（另两条仍命中），改用命中集合变化 + 材料题退出码翻转两种读数。原件 `positive-control/`。

## 冻结 run 基线（合入后 main 上要逐字段复现）

| run | 参数 | exit | `rules_hit` |
|---|---|---|---|
| 材料题 `run_20260921_183219_280474` | 无 | 1 | `unit_gap_claim_contradicts_input` |
| 行情题 `run_20260921_183642_325351` | `--scope-total 20` | 1 | `latest_trading_day_unverified`、`scope_claim_exceeds_comparison`、`fund_flow_claim_without_flow_evidence` |

与 #854 `evidence/frozen-run-parity.json` 一致。

## 本目录文件

- `k3-reverify-condition-card.md` — 交 #76 L5 的再验条件（固定题 / 固定版本 / 预算 / 判定项 / 阳性对照）
- `qc-candidate.md` — 交 #75 的队列行与作者读数（分开记账）
- 接入点设计：`docs/superpowers/specs/2026-09-22-claim-scope-runtime-integration-design.md`

## 边界

- 四叶收据在 #854 head 上取（超集），不是合并预览树；main 漂移文件与本 PR 零重叠是「不重跑预览树」的依据，合前若 main 再动非文档文件须重探 `merge-tree`。
- 全量 python 叶带 `--ignore=scripts/archive`（#58 未合，仓根收集面自 08-20 起断）；收据 `target` 不记录这条收窄。
- 本单零 live、不动 8792、不翻 `ASK_SEMANTIC_JUDGE`。
