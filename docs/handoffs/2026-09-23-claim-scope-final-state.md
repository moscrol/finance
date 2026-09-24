# #65 文档质检补验与清理边界 · 2026-09-23

## 背景与对象

#858 已合入 `86d3e558e3b1`，#879 已合入 `9a02279863733c9b9f60fd92fcc7e840fa83f878`。两份 merge record 的回读均为 base 指向合并提交、head 是双亲、树等于预览树；原件在 `~/.finance-runtime/reviews/claim-scope-merge-65-20260922/merge-{858,879}.json`。

本轮继续处理 #65 遗留文档矛盾与主干补验，不接入运行时、不做模型验收、不操作生产 8792。脏主检出树未用于测试、提交或签结论。

## 按发现顺序

1. #879 本轮工作树 clean 且提交已在主干，已移除该工作树及本地、远端分支。#858 的 `docs/closeout-workorders-0922` 树却有其他会话新工作，随后又产生新提交，因此保留，不吸收其 INDEX 或队列修改。
2. #858 带入的 INDEX #65 行仍写“运行时零改动”；旧交接把 #872 已修问题列为待办。订正为“运行时接入点未改，离线判据、CLI 与测试有改动”，并将缺陷移出待办。
3. #75 候选卡引用的路径实际是 clean detached `da761024ed54c46b8e650d1b86076e1f9d261ed2`，不是卡上的 `6fc6bfa94`。卡片改绑实际对象，原审计树保持冻结。
4. #76 L5 卡的最低基线提高到含 #872 的 `bd2290c861419b30b406633b1620d09d30de71e5`；真正开跑前仍需冻结获批候选。生产身份按开跑前实测值锁定，旧 `adcda94b5e40` 不再写成当前生产约束或回滚指令。
5. 09-23 Gitea API 实读 #854 为 closed / merged=false；Git 已合入事实不变。README 纠正“已用 manually-merged 补标”的过强说法。
6. 为主干快照 `9a0227986` 新建独立测试树 `/Users/a77/fwp-gate-65-final-0923/finance-workspace-private`。运行期间主干至少新增了其他任务的文档提交 `ffd1b7f15`，故本轮只签确切快照，不称“最新 tip 全绿”。

## 验证与原件

证据根：`~/.finance-runtime/reviews/claim-scope-final-20260923/`。

- 主干快照：`9a02279863733c9b9f60fd92fcc7e840fa83f878`，Git 树 `2fca469bcf5af5ae9e4b475ecef28fc894f9feec`。
- **全量门禁 RED，已结束**：Ruff exit 0；Python **14567 passed / 1 failed / 85 skipped / 2 xfailed**，collected=14655，耗时 2096.32 s。唯一收据 `receipts/gate-R2GxQOZc/pytest.json`，JUnit `python-junit.xml`。`check_test_receipt.py --expect-revision ... --require-full-scope --base-drift-max 5` exit 0（漂移 1），只证明身份、覆盖面和读数可信，不代表测试绿。
- 前端六步 exit 0：Vitest 120 passed，E2E 34 passed / 2 skipped；`frontend/frontend.json` complete=true、identity_stable=true、dirty=false。registry 五项 exit 0，crosswalk 保留 98 行反向引用 warning。`runner.log` 最终 **gate_exit=1**，测试树前后身份不变；本轮 runner 与测试端口均已退出。
- 冻结重放：材料题命中 1 条、行情题命中 3 条，CLI 均预期 exit 1；完整解析 JSON 与 #872 修复后 `fix-parity/` 基线相等。`parity-manifest.json` 绑定提交、树、检出路径、结果文件 SHA-256；这次增强不改写旧收据，也不改 CLI 输出契约。
- 静态引用扫描：生产 `intelligence/` 排除模块自身与测试后，唯一文字命中为 `output_review.py` docstring，未发现静态 import 接入。审计树 `da761024e` 与补验树的两个实现及两个测试文件相同；不据此声称整仓相同。
- 文档分支：`git diff --check`、提交前检查通过；未改运行时代码。主干快照收据不等于本分支新 head 收据。

## 未闭合的红项

`intelligence/tests/test_workbench_conversation_integration.py::test_real_turn_terminal_claim_does_not_publish_an_incomplete_artifact_list` 在第 160 行预期 `run["status"] == "completed"`，实读 `queued`。该次用例耗时 1.087 s，不能直接归因为十秒等待超时。

同一 clean 快照单独复跑 **1 passed / 9.55 s**，原件 `targeted-junit.xml`、`targeted-receipts/20260923T043411Z-9a022798-6c6bf2e22b1d.json`。这是未稳定复现，不是根因已修，也不能与旧收据拼成 14568 passed。测试源于 `0b688c3684` 的研究尾单整合线，本轮没有修改该测试或运行时；需后续定位顺序、并发或状态发布原因，再取一次完整绿收据。机器期间负载曾升高，但本轮没有证明负载是根因。

## 决策与被否方案

| 选择 | 未采用 | 理由 |
|---|---|---|
| 新树补验确切主干快照 | 使用脏主树或把旧 head 收据改签 | 收据必须可还原到实际被测提交 |
| 保留 #75 的冻结审计树 | 原地移动到最新主干 | 避免另一个审查者面对变动对象 |
| 在独立文档分支修正 #65 | 接管 #858 的在途 INDEX | 该树已有其他会话新工作，不能覆盖或混入 |
| 新增旁置 parity manifest | 覆写旧证据或扩大 CLI 改动 | 增强本次可追溯性，保留历史证据与接口 |

工具盘点：复用现有 `run_main_gate.sh`、`run_frontend_gate.py`、registry 与收据校验器；树外 runner 仅编排这一次固定快照，不新增仓内第二套门禁或通用抽象。

## 未完成与保留项

- 本文档分支 `docs/claim-scope-final-state-0923` 保持 WIP，未合 main。先闭合上面的全量红项并核对确切合入候选门禁，再取得明确合入确认；不把“继续”扩成运行时接入或真实模型预算授权。
- #75 K3 事后审未完成；候选卡准备好不等于独立审查签字。
- 运行时接入未实施，设计稿 §5 六条验收未执行；#76 L5 真实模型再验亦需单独授权。
- 原 #858 分支与工作树因其他会话继续使用而保留；旧本地 `docs/claim-scope-merge-65` 与 `da761024e` 审计树也保留。新 `9a0227986` 测试树保留用于原收据回读。
- 原合并授权引用保存在 merge record；此前评论接口 403 的独立复核限制未被本轮文档修正消除。
