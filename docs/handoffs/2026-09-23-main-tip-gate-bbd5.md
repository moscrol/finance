# 2026-09-23 main 门禁批次：bbd53487f4ce

## 结论与观察时点

截至 2026-09-23 15:32 CST，远程 main 是 `bbd53487f4cefdae97eae90f7322394d36e65462`（PR #876）。本轮只完成 registry 与定向守卫，Python 全量、frontend/E2E 未启动，**不是四叶完成，不能据此放行合并**。

本页是绑定时间和 SHA 的验收快照，不承诺阅读时仍是最新 tip。补文档也会生成新提交；不再为追上文档自身的 merge SHA 重复合文档。后续主干推进不抹除历史结果，但使它不能代表新 tip。

## 发现顺序与证据

证据根目录 `~/.finance-runtime/reviews/gate-closeout-qc-20260923/`。

1. `5f35da1723f7` 干净独占树跑完正式 frontend 六步：Vitest 120 passed，E2E 34 passed / 2 skipped；`main-5f35/frontend-gate/frontend.json` 的 `complete=true`、`identity_stable=true`、`dirty=false`、`exit_code=0`。registry 5/5、定向守卫 11 passed。Python full 因资源准入未启动，见 `main-5f35/python-admission.txt`。
2. #876 合入后 main 变为 `bbd53487f4ce`。它改了数据库快照、门禁临时目录清理和测试，不能把旧 SHA 收据挪作本批次结果。
3. 在独占干净 detached 树 `trees/finance-workspace-private-bbd5` 跑 registry 五项，全部 exit 0。见 `main-bbd5/registry/`，反向台账有 98 条 warning，但正向与重号检查通过。
4. 同一 SHA 的五组定向测试 74 passed / 0 failed，覆盖门禁收据、门禁树清理、数据库快照、指针隔离及归档守卫。日志 `main-bbd5/targeted/targeted.log`；明确收据 `~/.finance-runtime/test-receipts/20260923T063034Z-bbd53487-d68615dd4b96.json`，`dirty=false`、`collected=74`。这是显式路径子集，不能因没有 ignore 或收执对平就称全量。
5. 用该明确收据跑正确 SHA 校验 exit 0、错误 SHA `5f35da17` 校验 exit 1，见 `targeted/receipt-check.log` 与 `targeted/wrong-revision-control.log`（均在 `main-bbd5/` 下）。这些是定向收据的身份对照，不是全量收据校验。
6. 临时新增 `scripts/archive/test_zz_gate_closeout_probe.py`，归档守卫 exit 1 且错误中点名该探针；删除后 exit 0，树恢复干净。见 `main-bbd5/targeted/archive-positive.log` 与 `archive-restored.log`。正例故意产生的脏树红收据不是产品回归。
7. 多轮等待后仍有其他会话不断启动全量测试。15:32 CST 观测 load1=15.13、可用磁盘约 20 GiB、其他 full pytest 2 条，见 `main-bbd5/admission-final-observation.txt`。load 超过工单的准入上限 8，本轮不再无限轮询，也不启动新 full/frontend gate。

## 旧记录订正

- `main-4315/targeted-guards.log` 实际引用 `20260923T043502Z-2439ca8a-d4dbc6e5ba91.json`。那张 11 passed 收据绑定 `2439ca8a`，不能归到 `4315d9d5`；目录名不是身份依据。
- `5f35` 首轮手工 frontend 因默认端口占用而未完成 E2E，其手写成功摘要不采用。只认后续正式 `frontend-gate/frontend.json` 六步收据。
- #881 的 Git 合入事实与 API 状态分开：merge `4315d9d5fbf2` 双亲和 tree 已核验，且它是本批次 main 的祖先；API 在 15:31 仍报 open/merged=false。已先在 PR 评论 6183 引用该合入提交和接替 #882，再关闭重复入口，回读为 closed/merged=false。没有重新合并，也没有伪称 API merged=true。证据 `merge-881-timeout-verification.json`、`pr-881-state-reconciliation.log`。

## 决策对比

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 固定 SHA、记录分叶结果和阻塞 | 留下可复核证据，不改变完成门槛 | 采用 |
| 为每次文档 merge 再追写当前 tip | 文档本身会再次推动 tip，无法收敛 | 否决，改为有时间的观察快照 |
| 把旧 frontend 或 74 条定向绿升级为全量绿 | revision 或覆盖面不成立 | 否决 |
| 高负载下再开 full，或杀其他会话测试 | 污染读数或破坏他人现场 | 否决 |
| 再合一次 #881 来修 UI 状态 | 已在 main，重复改变主干没有必要 | 否决，留指针后关闭入口 |
| 四叶未完成仍合本轮文档 | 不满足仓库门禁要求 | 否决，保留 WIP |

## 接手操作与边界

1. 先核远程 main。若已推进，旧结果归档；为实际选定 SHA 建干净独占 detached 树。不要从文档目录名推导 HEAD。
2. 按工单准入：load1 <= 8、空闲磁盘 >= 8 GiB、pytest 进程 <= 2；本轮此前采用过更保守的零并发等待，但它不是工单新增规则。运行中仍应监测争用，且不动他人的进程和目录。
3. Python 使用主树 `.venv-workbench/bin/python`，通过 `run_main_gate.sh` 跑仓根全量，显式树外 basetemp 与独立 `FWP_TEST_RECEIPT_DIR`，无 ignore/选择表达式/测试位置子集。仅使用本轮明确收据路径；校验 `--expect-revision <SHA> --require-full-scope --base-drift-max 5`，核实 target 为仓根并做错误 SHA 对照。
4. frontend 走 `run_frontend_gate.py` 正式六步，独立输出目录；18981/18984 用前核空闲。按选定 revision 重跑 registry，不跨 SHA 移签。
5. 有红按 #59 的单跑三次和低负载整文件复跑规则分诊，不用资源忙直接解释所有失败。全部合格才更新完成状态；本轮不再贴 #851 的新完成评论。
6. 临时探针已删除；已完成的 detached 门禁树可正常移除，保留树外收据。未提交文档和其他会话工作树不能批量清理。

本轮未新增运行时代码或通用工具，使用既有 runner、校验器和归档守卫。机器级排队属于跨会话协调问题，本单不临时加一把无人共同遵守的锁；WIP 阻塞信息保留给后续调度。
