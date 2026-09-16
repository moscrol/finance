# 2026-09-16 · 研究进化 06 合并候选 `50074c76`：I11 同意门修复 + 全批次门禁

> 候选 = 06 `feat/research-evolution-06-workbench@3add63d5`（已含 01@85c90b24 / 02@e27b3352 / 04@fcc7838c / 05@2c278e07）
> + I11 修复 `9b92eac8` + 前向合并 `gitea/main@727b2611`（`877383eb`，两处文档冲突两侧都留）
> + 03 尖端 `feat/research-validation-03@68aac886`（RV1–RV3 返修，06 联测时用的是旧版 f2a12fa3）。
> 分支 `fix/re06-i11-consent-measurement`。本文只记本轮实测；06 前八轮的裁决见 `docs/verification/re06-*/REVIEW.md`。

## 1. 起点：合并复核（`codex/review-re06-merge-0bd11ece`）留下的三件

| 项 | 复核方裁定 | 本轮 |
|---|---|---|
| Y1 / Y2（P1，来源身份三态） | 在旧候选 `0bd11ece` 复现 | 06 作者已在 `c5359120` 修；本轮在 `3add63d5` 干净树重放复核方原探针 **2/2 绿**（开工第一步，独立于作者自测） |
| **I11**（P2）：`grant` → `withdraw` `["logging"]` 后研究 completed，仍写 `run_started / run_finished / cost_recorded` | 复现 | 在 `3add63d5` 重放 **红**（断言原样：`post_withdraw_measurements ['run_started','run_finished','cost_recorded']`）→ 本轮修 → 绿 |
| I14（P2，visibilitychange 计时接线） | 工程缺口 | **未纳入**：`fix/re06-visibility-timing` 叠在 `c5359120` 上、其交接自述「task-level I14 仍开」；合并后需 rebase 到新 main 再单独验 |

## 2. I11 修法（`intelligence/services/research_evolution/run_observer.py`）

`ObservingRunStore._record` 写任何测量事件前先过 `_measurement_consented(at)`：

- 只认 owner 自己的 `consent_changed`（`participant_id` 为空或等于 owner——自用测量的参与者就是 owner 本人），按 `effective_at`（缺则 `event_at`）排序折叠 grant / withdraw，与 05 读侧 `measure._scopes_at` 同一套语义；
- **没有任何同意记录 → 照写**（自用默认：owner 观察自己，没人可问；05 按 `pilot_id=workbench:*` 分区，自用事件进不了真人试点读数）；
- 有记录则必须同时覆盖 05 的 `REQUIRED_MEASUREMENT_SCOPES = {research, logging}`，否则跳过并留 stderr 痕迹；研究 run 本身不受影响（`_fold_maintenance` 仍跑——那是 Q2 的维护收尾，不是测量）；
- 台账读失败 → 按未知处理照写并留 stderr：同意门是测量的门，不是被测 run 的门。

被否：**默认不写**（会让既有自用测量测试与「owner 自用」语义整体翻转，且复核方指的缺口只是撤回不生效）；**只看 `logging`**（05 读侧要求两项同时生效，写侧与读侧口径不一致会造出「写了但永远不合格」的事件）。

回归 `intelligence/tests/test_research_evolution_i11_consent.py` 四条一起才承重：撤回必需范围 → 不写（`run_started` 在 `create_run` 内同步写、早于 202 返回，它不在说明门在 create 点就关了）；必需范围齐 → 照写含 `cost_recorded`；撤回无关范围 `blind_review` → 照写；无记录 → 照写。只钉第一条时「干脆永远不写」也会绿。

## 3. 探针重放（候选 `50074c76`，干净树，收据 `20260916T030137Z-50074c76.json`）

第三至八轮 + 合并复核（`docs/verification/re06-{0c275716,957e83f4,ecd90a3c,c8536482,9266407f,fdb5f91d,0bd11ece}/test_review_*.py`，合并复核那份 round8 副本改名 `test_review_round8_merge0bd11ece.py` 避开同 basename 收集冲突）+ 本轮 4 条：**27 passed / 0 failed**。其中 I11 原探针 `test_review_measurement.py` 从红转绿，其余 23 条修前修后都绿（合同守恒）。

## 4. 四叶门禁（候选 `50074c76`，树 `~/fwp-wt-re06-i11`，解释器 `.venv-workbench/bin/python` 3.12.13，`env -i PATH HOME`，无 `db/`）

| 叶子 | 读数 | 凭据 |
|---|---|---|
| ruff | 0 | `~/.finance-runtime/re06-i11-20260916/`（本节全部日志） |
| pytest 全量 | **10362 passed / 0 failed / 77 skipped / 2 xfailed**，653 s | `~/.finance-runtime/test-receipts/20260916T031253Z-50074c76.json`，`check_test_receipt.py --expect-revision 50074c76 --base-drift-max 5` exit 0（漂移 4） |
| 前端 lint / typecheck / test / build | 0 / 0 / 0 / 0，vitest 94 tests / 5 files | `fe-*.log` |
| Playwright e2e（8791 主服 + 8794 RE06 隔离服） | **31 passed / 2 skipped** | `e2e.log` |
| 注册表五步（parseability / check / backfill-tables --check / generate-views --check / ledger crosswalk） | 全 rc=0 | `reg-*.log` |

对照：06 作者 09-14 在 `c5359120` 的读数 10147P / e2e 31/2sk；03 尖端并入后 +215 条测试。

## 5. Q2 过渡合同：按委托接受

Q2 = 复核完成后不再自动收尾，面板「确认成果」显式点一下才闭环。复核方第七、八轮均写「工程上支持，不代用户接受」。用户 09-16 委托「按最优方案推进」，本轮按批次 README §1 已定的默认「维护动作由用户在产品中明确执行」**接受显式确认过渡**——它是那条默认的直接推论，不引入新的产品判断；且只是一处交互设置，改回自动收尾不需要迁移数据。记在此处与交接，用户看到后可翻案。

## 6. 未验证 / 已知边界

- 第九轮独立复核由另一 agent 在 `50074c76` 上进行（分支 `docs/qc-re06-i11-50074c76`，写 `docs/verification/re06-50074c76/`）；本文写成时尚未出结论，**合并以它放行为前提**。
- I13 真人试点 / I15 真实前向实验：证据待授权，不是实现缺陷（04 交接同样声明：存量台账缺 coverage / 版本链 / 曝光日志，真实用户会大面积 unknown，是数据现状）。
- I14：见 §1，合并后由 `fix/re06-visibility-timing` 所有者 rebase。
- 门禁在 `gitea/main@727b2611` 之上跑；写本文时 main 已前进到 `8bb20aa9`（#749，32 个文件全是 `docs/` 下的 knevo 资料，与本候选零文件交集）。
