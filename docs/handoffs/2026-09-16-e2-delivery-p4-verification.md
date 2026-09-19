# E2 P4（D5）精确提交验证记录：四叶等价 CI + 删保护变异

日期：2026-09-16。执行树 `fwp-wt-e2-delivery-closeout`，分支 `fix/e2-delivery-closeout`。
本文只记录 P4 提交之后在**精确提交**上做的验证与由此引出的两次补丁；设计与取舍见
`docs/handoffs/2026-09-16-e2-delivery-p4.md`，本文不重复。日志根
`~/.finance-runtime/e2-delivery-closeout-20260916/`，收据根 `~/.finance-runtime/test-receipts/`。

## 发现顺序

1. P4 提交 `2462cfde` 干净树全量：ruff 0；pytest **1F**/10013P/83S/2xfail（337s，
   `p4-2462cfde-pytest-full-2.log`）。红的是
   `intelligence/tests/test_session_projection.py::test_public_answer_assignments_all_go_through_view`：
   一条全树 AST 门禁，要求 services/ 与 runtime/ 里所有 `public_answer=` 关键字的值都是
   `view` / `_gap_answer` / `_generic_gap_answer` 的调用。P4 在 `recheck_material_public_delivery`
   与 `_reject_material_gaps` 里写了三处裸变量赋值，适配器又用 `public_answer=` 关键字把投影文本
   传回同一函数（两处）。P4 作者的 27 文件定向集（881P）不含这条门，所以 14 轮迭代全绿。
2. 修复 `9a98f4fc`（3 文件）：三处赋值改为
   `view(TerminalFacts(cause=CAUSE_VERIFIED, public=…))`，与 `_emit_withheld_repair` /
   `_marker_loss_partial_public` 同一形状；两个函数登记进 `_VIEW_CALLERS`（棘轮规定新出口必须登记）；
   `recheck_material_public_delivery` 的形参从 `public_answer` 改名 `projected`（它是调用方送入的
   投影文本，不是 outcome 字段；适配器两处随之改关键字）。允许调用者名单 `_ALLOWED_PUBLIC_ANSWER_CALLEES`
   未加宽。
3. `9a98f4fc` 上跑四叶与 28 个删保护变异；4 个变异仍绿。逐个核对后判定：M13 被邻近的「缺口必须公开
   出现在题正文」接住了带 gap 的题，但「有证据绑定 + 正文只复述题干」这条路无反例；M22 的 missing 被
   `all(...)` 吸收，issue / mandatory 那层没有独立断言；M24 是最终投影接缝的第二道防线，无反例；
   M28 是 fail-closed 分支，无反例。
4. 反例提交 `1f24a6ef`（只加测试，不改生产代码）：四条各一，变异重跑 4/4 红、每个恰 1 条测试红。

## 四叶结果

| 叶 | 跑在 | 结果 | 证据 |
|---|---|---|---|
| python | `2462cfde` | ruff 0；pytest 1F/10013P（见上） | `p4-2462cfde-pytest-full-2.log` |
| python | `9a98f4fc` | ruff 0；pytest 0F/10014P/83S/2xfail，351s | 收据 `20260916T023916Z-9a98f4fc.json`；`check_test_receipt.py --expect-revision 9a98f4fc` ✅ |
| python | `1f24a6ef` | ruff 0；pytest 0F/10018P/83S/2xfail，352s | 收据 `20260916T025729Z-1f24a6ef.json`；`check_test_receipt.py --expect-revision 1f24a6ef` ✅（干净树、解释器/依赖指纹一致） |
| frontend | `2462cfde` | install(frozen) / lint / typecheck / vitest 76P（4 文件） / build 各 exit 0 | `frontend-*.log`；`intelligence/webapp` 的 tree hash `991a798f` 在 `2462cfde`、`9a98f4fc`、`1f24a6ef` 三个提交上相同，结论直接转移 |
| e2e | `9a98f4fc` | 15 passed，46.9s，`WORKBENCH_PYTHON`=主树 venv | `final-9a98f4fc-e2e.log`；`9a98f4fc→1f24a6ef` 只改一个测试文件（`git diff --stat`），后端生产代码相同 |
| registry | `2462cfde` | `check-parseability` / `check` / `backfill-tables --check` / `generate-views --check` / `audit_ledger_spec_crosswalk.py` 五条 exit 0 | `p4-2462cfde-registry.log`；反向对账 96 行 warning 为既有 |

registry 叶第一次跑出五条 exit 2 是 zsh 不对 `$c` 分词把「脚本 子命令」当成一个文件名喂给 python
（记忆里已有同形教训），显式分词后全 0；不是门禁红。

## 删保护变异（`9a98f4fc`，定向集 27 文件 881P/4S，驱动 `p4-mutation-driver.py`）

每个变异：旧串唯一命中 → 写入读回确认 → 清 `__pycache__` + `PYTHONDONTWRITEBYTECODE=1` +
`-p no:cacheprovider` 跑定向集 → `git checkout --` 还原并核对树干净。基线 881P，全部还原后 881P。
数字是 failed 用例数（含参数化）。

| 变异 | 拆掉的门 | 红 |
|---|---|---|
| M01 | finish 逐题结构检查（漏/重/超长/未交代） | 13 |
| M02 | legal_gap 永不成立 | 25 |
| M03 | legal_gap 过宽（不要求公开交代） | 6 |
| M04 | legal_gap 计入 missing_outputs | 25 |
| M05 | legal_gap 当 fulfilled 参与 completed 判定 | 1 |
| M06 | 判官拒绝不重开原题 | 5 |
| M07 | 公开投影后不复验 | 4 |
| M08 | 判官 outage 暂扣稿当漏答 | 2 |
| M09 | 备忘录字数上限 | 3 |
| M10 | 缺口须公开出现在题正文 | 2 |
| M11 | 全缺口顶部说明 | 1 |
| M12 | 重复题段 last-write-wins | 1 |
| M13 | 复述原题不算回答 | **0 → 1**（`1f24a6ef` 补） |
| M14 | 零证据 input_only_rewrite 被拒 | 4 |
| M15 | input_only_rewrite 逃逸 cycle 上限 | 1 |
| M16 | 无工具时材料题 missing 降 optional | 4 |
| M17 | 合同校验：每题唯一必需槽 | 3 |
| M18 | 旧 ranking/track 模板重开材料题缺口 | 1 |
| M19 | legal_gap 结清修复账本 | 1 |
| M20 | 删句后不重编号 | 1 |
| M21 | 材料题语义放行放宽为恒真 | 4 |
| M22 | settled 忽略 issue / mandatory | **0 → 1**（`1f24a6ef` 补） |
| M23 | 适配器最后脱敏后不复验 | 1 |
| M24 | 复验降级 completed→partial 缺失 | **0 → 1**（`1f24a6ef` 补） |
| M25 | 模型输入缺 material_delivery 规则 | 1 |
| M26 | 判官请求缺 material_delivery 上下文 | 3 |
| M27 | 领域不再授权 input_only_rewrite | 5 |
| M28 | 句子坐标失配不 fail-closed | **0 → 1**（`1f24a6ef` 补） |

日志：`p4-mutations-run.log`（28 个）、`p4-mutations-rerun4.log` / `p4-mutations-rerun4.json`（4 个重跑，
基线与还原后 885P）。驱动是一次性件：旧串钉在这几个 revision 的源码上，换提交要改串，故不进 `scripts/`；
可复用的是它防的三种量具陷阱（未落盘 / .pyc / 改一半），已在 `harness-reference/TOOLKIT.md` B 档。

## 不成立 / 未覆盖

- 以上全是作者自验，判官是离线替身；不是独立 QC，不是 P7 隔离验收，不证明材料锚点真实性（D6）。
- 变异只证明「拆掉这一处，定向集会红」，不证明门的逻辑正确；M22 的 issue / mandatory 分支在
  material_only 下是否可达未论证（material_only 无读能力、无证据类型要求），补的是断言不是可达性。
- 前端与 e2e 叶未在 `1f24a6ef` 重跑，依赖的是 tree hash 相同 / 只改测试文件这两个结构性事实。
- 未切 8792、未部署；主检出未动。合并结果见文末。

## 精确头收据（`1f24a6ef`）

`~/.finance-runtime/test-receipts/20260916T025729Z-1f24a6ef.json`：passed=10018 failed=0 error=0
skipped=83，dirty=false，target=整树。本文与 inflight 是其后的 docs-only 提交，和 P3 的
`e37ada9b`（代码头）→ `851e7886`（文档头）同一惯例；合并前用
`python3 scripts/check_test_receipt.py <该收据> --expect-revision <合并候选的代码头>` 复核。

## 合并结果（2026-09-16）

前向合并 `gitea/main`（`727b2611`）得 `f89742eb`：唯一冲突 `skills.registry.json`（生成件，本分支未动 `skills/`，取主干版本，五条 registry 检查 0）。合并头四叶：python ruff 0 / pytest 10151P/0F/83S/2xfail（收据 `20260916T031445Z-f89742eb.json`，`check_test_receipt.py --expect-revision f89742eb --base-drift-max 5` ✅，漂移 4 来自 #749 的 4 个 merge 提交，#749 只动 32 个 `docs/` 文件）；frontend install(frozen)/lint/typecheck/vitest 76P/build 各 0；e2e 15P（端口 8793，另一 session 同时在 8791 跑它的 e2e）；registry 五条 0。日志 `merge-f89742eb-*.log`。

PR #752 经 Gitea API 合并（`merge-tree` 干净），merge 提交 `693043a5`，远端分支已删；`git diff f89742eb gitea/main -- . ':!docs'` 为空。未切 8792。
