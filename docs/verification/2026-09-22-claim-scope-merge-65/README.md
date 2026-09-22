# #65 口径越界 lint（#850 / #854）合入 — 证据索引

执行会话 S5（2026-09-22 夜 → 09-23 凌晨）。本目录只放可提交的文档；收据与日志原件在私有证据根 `~/.finance-runtime/reviews/claim-scope-merge-65-20260922/`（不进仓）。**运行时（`intelligence/`）零改动。**

## 结果 [实测]

| PR | head | 合并提交 | 记录 |
|---|---|---|---|
| #850 `fix/answer-claim-scope-0922` | `1cf35f5167ed3adebbb7d6ce60a37f8b92c79d0c` | `a696c5e1d0fdc2ebe230b76c9a51b9528178b996`（`gitea_pr.py merge` 回读：base 指向合并提交、head 是双亲、合并树 == 预览树） | `merge-850.json` |
| #854 `fix/claim-scope-hardening-0922`（先 `PATCH` base → 主干） | `5f5ce2d114b238edd3f278504e5a25f35f31710d` | `6fc6bfa94070beba2fbb1f944863a25a8493cf94`（POST 客户端 30 s 超时，服务端已合；回读：tip 树 `cfaeb58c…` == 预览树，`^2` == head；PR 对象滞后，用 `manually-merged` 补标） | `merge-854.json`（手工补写） |

授权原话与出处（逐字，来自本会话用户消息）：`2026-09-22T16:11:39Z`「继续按照最优路径推进，然后可以合并的就合并」→ S5 按推荐案 A；`16:34:51Z`「继续按照最优方案推进，该合并的可以合并」。两条记录文件都带 `authorization_source`。

## 合前门禁读数（全部在 #854 head `5f5ce2d1`，除注明外）

| 叶 | 树 | 结果 | 原件 |
|---|---|---|---|
| python 全量 | `/Users/a77/fwp-gate-65/finance-workspace-private`（detached，隔离父目录） | **12576 passed / 0 failed / 85 skipped / 2 xfailed**，1692 s，`dirty=false`；`check_test_receipt.py --expect-revision 5f5ce2d1… --base-drift-max 5` → 可采信（漂移 4）。带 `--ignore=scripts/archive`（#58 未合），收据 `target` 不记录该收窄，此处写明。带负载起跑（load 7→25），用户 00:35 再授权后放弃等准入 | `~/.finance-runtime/test-receipts/20260922T170400Z-5f5ce2d1.json`、`python-leaf.log` |
| frontend + e2e | `/Users/a77/fwp-gate-65-fe/finance-workspace-private`（同 SHA 第二棵 detached） | `run_frontend_gate.py` **exit 0**：install / lint / typecheck / test / build / test:e2e 六项全 0，e2e 34 passed，`complete / identity_stable`，`dirty=false`，端口 18991 / 18994 | `frontend/frontend.json` + 六份日志 |
| registry 五条 | 同 python 叶那棵（kb / site 同级软链在场） | 5 / 5 exit 0 | `registry/*.log` |
| #850 head 定向 | `/Users/a77/fwp-wt-answer-claims-0922` @ `1cf35f51` | `intelligence/tests/test_answer_claim_scope.py` 31 passed（该 head 无 `tests/test_check_answer_claims.py`，由 #854 新增） | `…/20260922T154730Z-1cf35f51.json` |
| 预览树定向 | `8e798937`（含 #863）+ `5f5ce2d1` 的 `merge-tree` 预览（== 合后 tip 树 `cfaeb58c`） | PR 测试 + `output_review` 相邻测试（`test_output_review / test_ask_compose / test_conversation_orchestrator / test_golden_answers` 等）**240 passed** | `…/20260922T163800Z-071ecc01-*.json` |

`merge-tree`：两 PR 对 `f24a61a8a` 与 `8e798937`（#863 合入后）均 clean；main 自 merge-base `a2c8d1f9` 前进 525 文件（168 代码），与 #854 的 32 文件零重叠。

## 合后核对 [实测 @ `6fc6bfa94`]

两冻结 run 在合后主干 detached 检出重放，与合前 `5f5ce2d1` 裁决**逐字段一致**（`rules_hit / issue_count / clean / context / issues[rule,quote,reason] / degraded`）：材料题 exit 1 命中 `unit_gap_claim_contradicts_input`；行情题（`--scope-total 20`）exit 1 命中三条。原件 `replay-on-main/`，脚本 `replay-on-main.sh`。

## 阳性对照（验收第 2 条）[实测 @ `5f5ce2d1`]

| 变异（从 `_RULE_CHECKS` 删一条） | 冻结 run | 变异后 | 还原后 |
|---|---|---|---|
| 删日期规则 | 行情题（`--scope-total 20`） | exit 1，命中 3 → 2 | exit 1，三条全回 |
| 删单位规则 | 材料题 | **exit 0**，命中 0 | exit 1，单位规则回 |

工单验收原文「日期规则注释掉后行情题退出码 1 → 0」在该题不成立（另两条仍命中），改用命中集合变化 + 材料题退出码翻转。原件 `positive-control/`。

## 第二方审查

`second-party-review.md`：S5 确定性探针（零模型请求）`PASS_WITH_LIMITS`。发现 1（中）证据台账正则不辨否定语境 → 资金流规则可被「未取得净流入数据」静默（fail-open，**后续单**，L5 条件卡已加人工缓解）；发现 2（低）「无法确认」免责句触发日期规则（误报）。#75 K3 通道审查未开队列，合入依用户授权不等它；#75 可对合后主干事后审。

## 本目录文件

- `k3-reverify-condition-card.md` — 交 #76 L5（候选 SHA 已填 `6fc6bfa94070beba2fbb1f944863a25a8493cf94`）
- `qc-candidate.md` — 交 #75（候选已合入，改事后审）
- `second-party-review.md` — 第二方确定性审查
- 接入点设计：`docs/superpowers/specs/2026-09-22-claim-scope-runtime-integration-design.md`

## 边界

- 四叶收据在 #854 head 上取（超集）而非预览树；预览树只跑了 240 条定向。依据：main 漂移文件与本 PR 零重叠、`--base-drift-max 5` 内（4）。
- 合后主干 tip 的全量批次门禁**未跑**：合入时机器磁盘 < 1 GB、swap 10.6/12 G、9 套 pytest 并发（#69 会话 01:10 告警），新起全量会假红；留给主干下一轮批次门禁（#59 形态）。
- 全量 python 叶带 `--ignore=scripts/archive`；零 live、不动 8792、不翻 `ASK_SEMANTIC_JUDGE`。
