# local 同步计划与日报质检契约对齐

## 背景与范围

用户要求继续推进 local 同步与日报门禁对齐；本轮不请求复盘会、不要求登录、不接本地篮子资金兜底，不做生产数据回填。原数据工作树有他人 WIP，因此在 `/private/tmp/fix-local-plan-gate-alignment`、分支 `fix/local-plan-gate-alignment` 开工。基线是 `gitea/main@1fef3d27`，本轮 fetch 后未变化。

## 发现顺序与实现

1. 基线已有完整 local 计划和 registry 驱动的两道门裁剪。`run_review_sync.run_release_steps` 本来就显式传计划；不是整套 local 未合主线。
2. `DailyReviewOptions` 没有 plan，日报两道门依赖各自默认值；跨日 `quality.check_daily` 不读取 `REVIEW_SYNC_PLAN`，导致同步 local、生成 full。
3. `render_daily_review_briefing.py` 还会再调用质检。只修日报的两道前置门仍不足以覆盖显式参数优先于环境的场景。
4. `intelligence daily` 的旧同步步骤是 `daily-update`，不支持 local/cheap。不能在不换同步生产者的情况下仅放宽下游门。非 full 且实际选中旧同步的工作流现在拒绝执行，提示先完成匹配同步再 `--skip-sync`；从日报恢复执行不会触发该拒绝。
5. 生成段旧代码根问题是已有独立工单 #50：`docs/superpowers/specs/2026-09-12-generation-stage-code-root-workorder.md`。本轮不以修改 cwd 或硬改脚本绝对路径的方式半修，涉及用户态/episode/导出落盘归属，仍待独立验收。

实现提交 `4fbc8c42981d969c2f52e87ad3f67009b0c8bd53`：
- 在 `market_feature_store/consumption_registry.py` 共用 `requested_plan` / `resolve_plan`：显式参数 > `REVIEW_SYNC_PLAN` > full；空环境等于未设，非法配置失败；auto 按指定交易日周五 full、其余 cheap。
- 同步器保留导入的 `resolve_plan` 接口；两道门、日报、HTML 内部门使用相同解析器。
- `DailyReviewOptions` 在构造时冻结实际计划，summary 记录实际档位，恢复执行不重新读取可变环境。
- 跨日未指定日期时先取库的最新交易日，再解析 auto，不用墙钟今天。
- registry 只修过时注释；`theme_flow.steps` 没新增 local。连板/新高/主线/核心股早已有 local 生产者，不得按旧概括继续豁免。

## 方案取舍

| 方案 | 结论与理由 |
|---|---|
| 删除全局资金表质检 | 否；full/cheap 仍应查，不能全局放宽 |
| 本地板块篮子资金写入题材面板表凑数 | 否；不同口径，不属于计划接线修复 |
| 只给跨日 parser 加环境默认 | 不充分；遗漏显式参数、HTML 内部门、auto 的日期解析 |
| 共用解析器并显式传实际档位 | 采用；保持既有生产语义，覆盖恢复和嵌套门 |
| 给旧 daily-update 偷换成新 local 同步器 | 否；涉及 staging 发布链，不能恢复第二条写入链 |
| local/cheap 误选旧同步时失败关闭 | 采用；宁可提示正确操作，不偷偷调用 full |
| 顺手改生成段代码根 | 暂不做；#50 要分别验 import 与数据归属，零抓取单测不能替代其验收 |

## 验证与收据

使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，未使用宿主 Python 跑测试。

- 10 个针对性测试文件合计 **144 passed**，含新增 `tests/test_review_plan_alignment.py` 的 **39 项**，其余为原有同步/门禁/结构化状态/本地加工回归。最终针对性收据：`~/.finance-runtime/test-receipts/20260914T155618Z-1fef3d27.json`（提交前补丁树，不冒充干净基线）。
- 变异验证：临时删除日报跨日门 argv 的 `--plan`，9 个组合测试全红；恢复后 144 项重新全绿。变异收据 `20260914T155517Z-1fef3d27.json`，不是当前代码失败。
- `ruff check .` 与 `git diff --check` 绿；提交钩子通过。
- `scripts/build_registry.py check` 绿，**仅 ws 在场，跳过跨仓 23 项**，不是跨仓完整门禁结论。消费 registry 与同步步骤同序由 `test_consumption_registry.py` 覆盖。
- 在干净提交 `4fbc8c42` 跑 `pytest -q`：**9654 passed / 2 failed / 77 skipped / 2 xfailed**，490.27s；收据 `~/.finance-runtime/test-receipts/20260914T160652Z-4fbc8c42.json`；完整日志 `/private/tmp/local-plan-alignment-4fbc8c42-pytest.log`。
- 唯二失败：`intelligence/tests/test_codex_headless_runtime.py::test_installed_codex_sandbox_denies_network_and_unix_socket[False|True]`，`receipt.status=unproven` 而非 `proven`。
- 未修改基线 detached 树 `/private/tmp/local-plan-alignment-baseline-1fef3d27` 同两项复现失败：2 failed / 30 deselected；收据 `20260914T160726Z-1fef3d27.json`。只复跑了失败两项，不称基线全量对照。
- 真 CLI 零执行演练：`intelligence.cli daily --date 2026-09-14 --plan local --skip-sync --from-step daily-review --dry-run`，summary `plan=local`，两道门与 HTML 命令均带 `--plan local`，状态 SKIP。收据 `/private/tmp/local-plan-alignment-dry-run.json`。
- 临时库验证：local 豁免资金面板而仍报应产表缺数/关键字段 NULL；full/cheap 不放宽；River 对只有上一交易日同名题材资金行返回 Gap，不展示为当日行。该测试只证明题材行日期过滤，未扩展到资金所有消费者。

## 当前边界与下一步

代码已本地提交，未 push、未合 main、未部署、未补跑日报。原数据树未动。本轮没跑生产同日/跨日/L2 门，不能宣布生产日报恢复。

合并前：处理沙箱门的既有红项，补齐规范要求的完整 registry / frontend / e2e 叶子并拿到用户确认；不得带红合入。后续生成代码根切换按 #50 单独做，分别验加载版本和用户态/episode/报告落盘根，之后才在真实数据通过门禁的前提下补跑生成。

工具沉淀：故障保护落在仓内回归测试，不新增第二套排查 CLI；可迁移原则是“入口解析一次、对子消费者显式传递、拒绝不支持该档的生产者”。已加入共享知识既有门禁方法笔记，不改脏的 harness-reference。
