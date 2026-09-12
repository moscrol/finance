# feat/instruction-migration-agents-md · 指令迁移（A 组）

**已提交未推送**，从 `gitea/main=6382c13b` 开，单提交。推送 / 开 PR 需用户点头。

## 做了什么
指令正文 CLAUDE.md → AGENTS.md（CLAUDE.md 收为 `@AGENTS.md` + Claude Code 备注）；`build_registry.py` 的 DOC_TABLES 目标同步改到 AGENTS.md；l2-moneyflow 从 `.claude/skills/` 实目录归位为 `skills/` 源 + 软链视图；删 公司画像页 / 潜意识模式 / 行业概览 并同步 dispatcher 路由表；补入迁出参考 `docs/knowledge-backfill-rules.md`、`docs/workflows/strategy-hypothesis-experiments.md`；修 `.devin` / `.codex` 钩子的仓根绑定。

## 刻意不带什么（别顺手加回来）
工作区那批 skill 正文改动（description 归一化、gold-standard 引用、UBIQUITOUS 新术语、daily-full-review 重构）**不属于迁移**，基于落后 main 548 个提交的 `b4a35fa2`，带上会回退：红线「日历行最后写」、整节「local 计划」、「停抓期间只用 `--plan local`」、duckdb-backfill 在 09-07 被刻意移除的 `disable-model-invocation`。**判回归比目标分支，不比快照。**

## 门禁状态：**不可合入**

| 叶子 | 状态 | 依据 |
|---|---|---|
| `registry-check` | **红** | 五步里前四步 exit 0，第五步 `audit_ledger_spec_crosswalk.py` **exit 2**（`registry-check.yml:49-51`，无 `continue-on-error`）：缺号 `R-20260831-02`，台账命中 0 行 |
| `python` | **红** | 9405 passed / 77 skipped / 1 xfailed / **1 failed** |
| `frontend` / `e2e` | 无结论 | 均未跑 |

台账红是**存量**（`6382c13b` 上可复现），但仓规不给存量红豁免。**「不是我引入的」是责任归属，「能不能合」是放行判断，不可互换。** 补前端 + E2E 只消掉「无结论」，两红仍在。

旁证：ruff 绿、`test_code_map.py` 41 passed、`test_agent_hook_roots.py` 3 passed。pytest 收据在 `~/.finance-runtime/test-receipts/*-<revision>.json`（按 revision 取，别读 `latest.json`，多树并发会覆盖）；该 revision 与本提交的差异须只有本文件。

`backfill-tables --check` 删行会红、**改触发词不会红**（`build_registry.py:582` 只为新技能填充），那片绿只覆盖技能名集合。

## 待办
1. 清 `R-20260831-02`：补台账行，或按 `claim_ledger_id.py` 重新取号并改 spec。清完 `registry-check` 才转绿。
2. `test_installed_codex_sandbox_denies_network_and_unix_socket`：**既非稳定红也非已修，污染源未定位**。单跑绿、`intelligence/tests/` 8281 条全绿、全量套件红；它起真子进程实测本机 Codex 二进制沙箱（二进制自 09-10 21:25 未变）。「顺序/状态依赖」只是假设。别预先收窄排查面：全量收四个顶层目录（`intelligence/` 8281 / `tests/` 1152 / `skills/` 48 / `scripts/` 3），差集 1203 条；「先跑 `tests/` 再跑沙箱」得绿，削弱但未排除 `tests/`。
3. 前端四叶与 E2E。
