# 2026-09-23 · #63 质检整改与分叉内容保全

## 背景与授权

此前只读质检确认188个目标历史已保全、market-cutoff归档完整，但发现方法笔记临时索引作用域错误、脚本失败只打印、inflight超预算、并发推同少算1个。用户随后授权“你来推进”。本轮只做这些整改和两份仍未保全的分叉内容留存；不合main、不强推、不删枝、不重写历史、不部署、不写生产数据、不重跑独立模型审查。

主树为他人混合树，未在其上改源码或跑全量。新工具从最新已获取的 `gitea/main@8e79893729da43c6e66f707ee28cbca99abb0c74` 开 `fix/push-preservation-qc-0923`，独占工作树 `~/fwp-wt-push-preservation-qc-0923`。原cutoff树经重新核对干净且两端相同，那里只改一份交接。

## 发现顺序与完成项

1. 重新查询代码地图与仓内源码，复用 `check_evidence_archive.py`，补 `preview_evidence_archive.py` 两阶段工具，而不是继续散写shell。临时索引环境明确传给每个子进程；拒绝继承重定向。正式校验要求同一父提交和完整tree，并对两版归档重验；非零退出是真拒绝，不再仅打印。
2. 一次性小仓44条定向回归通过。撤掉索引隔离、树身份、父身份、非零退出、实际归档复核五处，具名测试均断言失败。未用导入失败充当捕获。
3. 重读全部远端head，确认两分叉仍有1/10个仅本地提交；固定tip按新名字原子推送，再回读新头和原头。没有复活其他8条已包含在main的枝名，也没接管后来其他会话推进的分支。
4. 方法笔记改为明确作用域/唯一临时目录，历史账统一为 **173新建 + 11快进 + 4并发推同 = 188目标**。这不是今天的活分支计数；初始1011/290和最终枚举分开。旧/tmp执行脚本保留原件后换成exit2的退役提示，不留第二条可误跑的写入链。
5. cutoff inflight由3488压到2601字节；用新工具真实预览、显式提交、正式完整SHA复核。提交 `4a6e18da6f1469da2df9f79438d26ce8d2759e5f` 已推，tree相同、181/181，唯一改动是该交接。独立候选快照未动且干净。
6. 工具、回归、流程和教训提交 `fdaf35251235958b34314a0df74344b0f571e4fa` 已推；干净提交再跑44P，并以精确收据/JUnit交叉核对。harness的KIT/BUILD同步编目，`7effba042aae14fe7597b422c37d2cc76d24a4db` 已推至 `docs/evidence-preview-qc-0923`，注明候选未合入。共享记忆自动同步 `9c5aae5413e95fbd7619f6650f44e966666255cd` 已回读远端，不吞他人索引。

## 两份保全身份

| 原本地枝 | 固定tip | 新远端保全枝 | 仅本地提交数（推前） |
|---|---|---|---:|
| feat/grok-cli-judge | a354d2651d238839b9bafb068ca7456be58cc9a5 | salvage/grok-cli-judge-local-20260923 | 1 |
| feat/reading-rules-baseline-r2 | 9c2fff08c76de663ce909bd6eabccf72f5721e4a | salvage/reading-rules-baseline-r2-local-20260923 | 10 |

原远端仍分别是 `20c5b8d58b174d8422427fb6551fb199bfb6e4b3`、`ad3f417215928dd14a29bb0c8d0ccfbede489fb7`。本轮不修改原枝upstream，不建PR来要求合入这些保全枝。

## 关键取舍

| 方案 | 评价 | 结果 |
|---|---|---|
| 只修方法笔记一行 | 易被复制时再漏env或退出码，没有可执行回归 | 否 |
| 固定/tmp路径继续维护一次性脚本 | 并发互撞，职责含真实commit，易误跑旧树 | 否；原件归档、入口退役 |
| 校验工具自动提交/推送 | 校验同时获得写refs权限，难区分谁认领了路径 | 否；只给prepare/verify，副作用由显式命令承担 |
| 提交后checker红再amend | 改历史且可能碰别人的新提交 | 否 |
| 临时index + 无引用commit + 正式身份比对 | 可在副作用前校验，提交后拒绝身份漂移 | 选；不是写锁，优先独占树 |
| 对10条分叉一律换名推 | 8条内容已在main，重复留枝无保全收益 | 否；只保留仍缺的两份 |
| 把181/181写成验收通过 | 它只证明失败报告也完整保存 | 否；保持产品BLOCKED |

## 收据与验证边界

所有pytest/ruff用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

- 干净工具提交：`20260922T165950Z-fdaf3525-5f1010728da5.json`，44P、0F/0E、dirty=false；JUnit和exit0一致，收据checker明确指定完整revision通过。
- 首次脏树44P另存：`20260922T164222Z-8e798937-30c00ecdd866.json`，不能拿基线SHA认领未提交代码。
- 五处变异原件与代码SHA256同一，全部具名assert红；正式代码恢复后已用干净44P验证。
- cutoff提交预览 `8030332c9d5af56ea995fcefeb17b0cb94c1f4e9` 与正式 `4a6e18da6` 一致；verify实际读取两个commit的blob。
- harness check_refs exit0，但有存量行数漂移和缺席仓，不称全量引用绿。
- vault lint前后均33 errors/17 warnings；ERROR集合无新增。保持原问题，不顺手改其他agent笔记或规则。
- 新证据包 `docs/verification/2026-09-23-push-preservation-qc/`：36份原件逐字节保存、来源/长度/哈希在sources.json；生成sha256-manifest后另查Git revision，不靠本地hash自证。

**没跑本仓全量pytest/前端/E2E/完整registry叶，没做新工具独立外审，不满足合main条件。** 没启动模型、服务、真实Workbench、K3或生产写入。market-cutoff仍 `AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED`；最近保存的Spec/Quality retry-01是usage limit无verdict，本轮未重试，不宣称当前额度已测。

## 接手动作 / 不要做

1. 新工具待独立复核和用户合入确认；先重查最新main，跑规定等价CI各叶，不能用44P替全量或借别枝绿灯。
2. cutoff候选仍为 `53054bfd4336bebd0d570273a58e92758fb623be`；额度可用、独立审查与主线组合核对完成后，再按其原交接重绑准确SHA做真实两原题验收。不要执行旧身份runner。
3. 两个salvage头只作内容保全，不为它们自动合并、清理原枝或工作树。
4. 原质检目录保持原样，整改证据另存 `~/.finance-runtime/reviews/push-s1-63-followup-20260923/`；历史失败、初始快照和后来并发变化分账。
