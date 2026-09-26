# #83 / PR #813 · 302132 固定范围回填整合

## 这个分支做什么
302132.SZ 固定范围历史回填的专用父子命令 + 验收脚本 + 演练探针，整合到当前 main。只交代码与证据，**不执行生产回填**。

## 当前状态
**ENGINEERING_PASS_QC_PASS_WITH_LIMITS_TAKEOVER_FORWARDED**，未合入、未写生产。
09-26 起 Pi 会话 01a0ce4c 不再推进，由接手收尾子代理继续。树 `/Users/a77/fwp-wt-l4-pr813-0926`，分支 `l4/pr813-fwd-0926`，已快进推到 PR head `fix/backfill-main-ready-0921`。已合 `gitea/main=346be5d8b`（零冲突）；QC 绑定身份 `4f12e65e4` 是本 head 祖先。

## 已验证
- 重叠核对为**空集**：incoming main 非文档改动只在 `intelligence/**`、`scripts/judge_loss_point_replay.py`、`scripts/review_probes/material_claim_occurrence_mutations.json`，与回填四源文件 + 两测试零交集 → 4f12 业务代码逐字节未变，QC 结论可延用。
- 定向 `tests/test_repair_backfill_stock_history.py tests/test_rehearse_302132_backfill.py` = **119P**（本轮 +1）；ruff 通过。
- 独审 QC 批 22 `~/.finance-runtime/reviews/pr813-glm-qc-20260925-22/`：C1–C7 全 verified，**PASS_WITH_LIMITS**，25P/0F，阳性对照 exit 1，重试 0。
- 4f12 工程收据 `~/.finance-runtime/reviews/pr813-ready-main-e159-0925/`：Python 16349P/0F、前端 123P、E2E 34P/2S、registry 5、完整库演练 37 检查通过。
- 接手方范围化复核 **PASS_WITH_LIMITS**：`~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L4/review.md`。

## 未验证 / 已知边界
四叶未在本 head 重跑（协调者在合并预览上统一跑）；完整库演练只审计 4f12 旧收据未重跑；自然金融正确性不在工程复核内；批 13/19/20/21 结果一律不转签。

## 下一步
1. 协调者跑四叶 → 去 `WIP:` → 合入。
2. 生产回填**另需用户逐字授权**，清单 `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L4/production-backfill-packet.md`：重新冻结输入、验鲜、确认无 WAL（**发现 WAL 停下不删**）、用本轮父收据的 backup_path/SHA。
3. 旧线 `fix/backfill-302132-scoped`（09-14，+12）建议**关闭**，接替指针 PR #813（内容已重做并加强，证据见下方快照）。

## 踩过的坑
- 共享闸门有单测 ≠ 新执行点被接上：`_refuse_production_write_direct` 是 main 既有件，本线在 `cli.py:1594` 新增调用点；把它的 `return 2` 改成 `return None`，原 118 条定向用例**全绿**。已补 `test_cli_child_refuses_canonical_production_target`（只加测试不改源码）。
- 父命令目标由 `MARKET_FEATURE_STORE_DB` 解析，`--db` 仅内部 `--child` 用；不另开直写通道。
- 文档树 `/Users/a77/fwp-wt-backfill-302132-0923` 代码旧，不从它验收或做生产。

展开见 `docs/handoffs/2026-09-26-backfill-302132-takeover-forward.md`。
