# Generation root 387028b8 · 独立 Spec 复核

结论：**原 R1/R2/R3 的 7 项反例已全部挡住；本轮另实证 1 项 P2，既有告警写入遗漏于路径预检。冻结候选仍需返修这一边界，不能把原探针全绿解释为所有生成写入已隔离。**

## 对象、来源与操作边界

- 冻结树：`/Users/a77/fwp-wt-generation-root-guards-validation`，HEAD `387028b846a21a1327d964af8c4b428367f88fcf`；开始及全部探针/测试结束后 `git status --porcelain=v1` 均为空。
- 固定比较：`git diff 1fef3d276d0e251158803fc09d5a81e60d79241b...387028b846a21a1327d964af8c4b428367f88fcf`。提交链 `4fbc8c42 → 07d42891 → 2f82d4d3 → 0f6c2810 → 9b974691 → 387028b8`，含已说明的 local-plan 前置。
- 规格：冻结树 `docs/superpowers/specs/2026-09-12-generation-stage-code-root-workorder.md`（#50）；作者树 `/Users/a77/fwp-wt-generation-root-guards/docs/handoffs/2026-09-15-generation-root-boundary-guards.md`；旧裁决 `docs/verification/2026-09-15-generation-root-0f6c2810-qc.md`；冻结版 `docs/agent-product-door.md:33`。
- 使用 code-review 的 Spec 轴。未改候选代码/测试，未推送、合并、部署，未请求模型或生产 DB、KB 接收/生产 L2。所有执行数据由原 rig 生成临时 DuckDB、用户目录与代码副本；其 SQL/质量结果替换边界原样保留。
- 额外告警线索由 Standards 审查转交；本报告独立运行真实 launcher/CLI/runner/writer 复现，不把线索来源称为独立发现。

## S1 · P2 · 既有告警文件不在最终写入路径校验里

**规格原句**：#50 §4.3，`docs/superpowers/specs/2026-09-12-generation-stage-code-root-workorder.md:51`：**“全在数据根，代码根下零新增文件”**。冻结版门页 `docs/agent-product-door.md:38`：**“缺代码根/包、写入位置落进代码根时拒绝生成。”**

**代码证据**：新增 `intelligence/workflows/generation_paths.py:73` 的目标集合覆盖 exports、日期、矩阵、两种用户、episode、质量状态，以及后续选中归档/回检/summary 输出，未包括告警目标。实际 `intelligence/workflows/daily_review.py:404` 默认在 FAIL 时告警，`:419` 调 `send_alert`；`scripts/notify_ops.py:29` 把日志定位到 `Path.home() / '.finance-runtime' / 'alerts.log'`，`:34`–`:36` 创建父目录并追加内容。

**可执行反例**：只在临时 HOME 预先创建 `.finance-runtime/alerts.log → CODE/qc-alert.log`；固定临时质量结果 `TEST_GATE_RC=3`，运行真实启动器 `--date 2026-09-11 --plan local --skip-sync --only-step daily-review`，保留默认告警。实际 exit **1**、未报 `generation code/data root invalid`，代码树新增 **`qc-alert.log`**，内容为 `[daily-review FAIL] ... failed=quality-gate ... returncode 3`。这是业务失败后已发生的写入，并非副作用前拒绝。

**合法对照**：同样质量失败，但 HOME 告警日志位于正常外置目录，exit 1、告警正常落盘、代码树零变化。`notify_ops` 源码不含网络或凭证访问；临时 PATH 内的 `osascript` 空操作 stub 拦住桌面弹窗，未发真实通知。

**最小修复方向**：把生成流程已有的真实告警落点加入同一静态预检，在业务步骤与告警副作用之前拒绝代码根目标，同时保留安全外置日志写入。门页的“未枚举的新增写入”例外不覆盖本项：该告警调用在既有 daily 流程中已存在，此反例也无运行期换链。

证据：`generation-spec/probe_alert_boundary.py`（可复跑、未改候选）；`generation-spec/alert-boundary.json`；`generation-spec/alert_log_symlink_to_code.{stdout,stderr}.log`；探针退出 1 明确表示这一合同失败。其两项用例不计入下述 165 项测试或原 7 项探针。

## 原要求逐项复核

| 要求 | 本轮证据与结论 |
|---|---|
| 固定代码根加载、cwd 无关、缺根拒绝 | `tests/test_generation_code_root.py` 真实子进程对照通过；来源打印在冻结副本下，poison 数据树未执行。 |
| 数据与代码分根，用户/episode/exports 保持正确 | 真实报告/HTML/metrics writer 与存储接口夹具通过；相对覆盖按数据根、合法外置用户软链与循环目录正常。S1 是未覆盖的另一既有写入点。 |
| R1 具体路径和后代软链 | 未改原探针用户子目录、日报日期、质量目录三项均 exit 2 且无代码变化；新增回归也覆盖文件软链、归档、episode 与安全外置目录内回链。 |
| R2 同一参数语义 | 完整参数、等号、合法缩写、重复最后值均有行为回归；最后值安全时能写，最后值指代码根时预先拒绝。 |
| R3 真实代码归属 | 原两个软链脚本反例均 exit 2、旧码哨兵未执行；工作流模块/嵌套脚本回归及内部链接对照通过。静态校验的已声明边界不等于 OS 沙箱。 |
| L2 保留 | 本 diff 对 `scripts/moneyflow/` 为空；`test_eval_launchd_wiring.py` 的真实 shell + 假执行器覆盖 L2 先于同步守卫、L2 失败阻断生成、成功生成和不嵌套 S7。没有执行生产 L2。 |
| 原调用点回归可证伪 | 定向集包含将临时夜跑副本改回裸 `-m`、出现 poison 哨兵、再还原转绿；三处删闸变异也仅作用于测试临时副本。 |
| 范围 | local-plan 共享解析器是明确前置，原交接有独立需求/因果依据；未发现另外的未说明行为扩张。全量及部署不在本次独立执行范围。 |

## 验证与可采信条件

1. **原未改探针 7 passed / 0 failed，exit 0。** 执行冻结版 `scripts/probe_generation_code_root.py --repo <冻结树> --output <本证据目录>/original-probe.json`。另以 Git 确认该文件自 `9b974691` 至 `387028b8` 无差异。7 项各自 exit 2，代码清单零变化，旧码哨兵均未执行。
2. **本轮 10 文件定向集 165 passed / 0 failed，46.52 秒，exit 0。** 目标：`tests/test_generation_code_root.py`、`test_review_plan_alignment.py`、`test_eval_launchd_wiring.py`、`test_processing_quality_order.py`、`test_consumption_registry.py`、`test_review_sync_export_release.py`、`test_structured_daily_update_status.py`、`test_daily_review_json_canonical.py`、`test_daily_review_agent_entry.py`、`test_daily_review_unmapped.py`。这是本轮选择的分母，不冒充作者 158 项或全量。
3. 解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `3328bed61f3e21ea`；`dirty=false`、`worktree_dirty_total=0`、依赖门未绕过。收据：`generation-spec-receipts/20260919T171331Z-387028b8.json`。冻结树 `scripts/check_test_receipt.py <精确收据> --expect-revision 387028...` exit 0，日志 `generation-spec/receipt-check.log`。未引用全局 latest。
4. 冻结 conftest 不支持 `FWP_TEST_RECEIPT_DIR`；仓外插件 `generation-spec/receipt_redirect.py` 只将 `_RECEIPT_DIR` 路由到父任务指定目录。使用清洁环境、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider` 与仓外 `--basetemp`；未改依赖门、测试逻辑、计数或源码。插件为收据位置适配，已在日志与此处披露。
5. 原探针/定向 pytest 日志为 `generation-spec/original-probe.log` 与 `generation-spec/targeted-pytest.log`；额外探针 `generation-spec/alert-probe.log` exit 1。完整差异和初始身份分别保存为 `generation-spec/review.diff`、`generation-spec/start.json`，终态/哈希在 `generation-spec/manifest.json`。

本轮未重跑作者全量、前端/E2E/registry，也未证明真实模型回合、矩阵业务计算、KB 接收或生产同日/跨日/L2 门。独立结果仅针对上述冻结源码与临时夹具的已列合同。
