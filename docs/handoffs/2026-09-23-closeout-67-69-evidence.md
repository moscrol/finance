# #67 / #69 合入与收据归属核验

## 范围与结论

本次从远端 `main@9a02279863733c9b9f60fd92fcc7e840fa83f878` 新建独立工作树，修正工单 INDEX 和 #75 候选队列。未移植旧台账工作树的整份 diff，未修改产品代码、其他分支的 inflight、生产服务或数据，未删除分支、工作树或测试临时目录。

结论分三层：#863/#870/#865 已合入；下表读数只证明各自固定版本；#75 独立事后审与 #76 自然金融验收未由本次完成。文档 PR #858 已于 #879 之前合入，不能再作为待合入 PR 推进。

## 核验过程

1. 以 `git ls-remote gitea` 回读主干和 PR head，再以 Git 双父、合并树及保存的合入 JSON 交叉核对，不用陈旧 `gitea-pr/*` 引用。
2. 复核 #870 三叶的 `revision`、退出码、`complete` 和 `source_unchanged`。变异结果实际在 `b674e54b6`；到最终 head 只有一份交接文档变化。1361P 广域回归原件则明确 `dirty=true`，两者不可合并成“最终 head 干净回归”。
3. 使用现有 `check_test_receipt.py` 验 #865 合后及 #873 后的完整 Python 收据；用后者冒充本轮 main 基线的反例被拒绝。
4. Gitea API 本轮已可用：#843/#864 均 closed、merged=false，标题保留 #865 接替指针。#865/#870/#858/#879 的 API 合并身份与 Git 对得上。

## 合入身份

时间统一为 Git 合并提交时间（+08:00），不是 API `merged_at` 或评论发布时间。

| PR | 最终 head | 合并提交 | 时间 |
|---|---|---|---|
| #863 | `65fde6171e15d3a73c493b2808d076ae6c45cb7c` | `8e79893729da43c6e66f707ee28cbca99abb0c74` | 09-23 00:31:19 |
| #870 | `f5cfc353ff093a2ea9d5aebc6e7499764712e545` | `99c2ff28ba5f2bc9bfc7484d05216bee5a7adbab` | 09-23 03:34:23 |
| #865 | `2d5942e07f54506b075a06cdbba9f7fb032e0836` | `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4` | 09-23 09:38:22 |
| #873 | `d18921e0f77ee6ee9de86ef00cc15e43841edbbe` | `760248ecebc79fbe4f2686ddd42255c1a00ec862` | 09-23 10:20:49 |
| #858 | `cb52e97182ae777f2aa29b07222924412657d077` | `86d3e558e3b12d8f64b5babdc0a18e865814921c` | 09-23 11:21:10 |
| #879 | `971e804a17a18d636f224df8d9a52ede2d099681` | `9a02279863733c9b9f60fd92fcc7e840fa83f878` | 09-23 11:27:32 |

#870 合入原件：`~/.finance-runtime/reviews/pr870-gates-20260923/merge-870.json`，SHA256 `b074a7b089ab15df59ce41fb762334eba3b133ce2aaea1ca87367c4fa50cd5dd`。其中 `head_is_parent`、`base_points_at_merge_commit`、`tree_matches_preview` 均 true；它记录的是当时合入，不代表当前 main 仍停在该提交。

#865 原件：`~/.finance-runtime/reviews/runtime-identity-effects-20260922/merge-865-authorized-20260923.json`；基座 `da761024ed54`、最终 head `2d5942e07f54` 为合并提交双父，原件三项核验均 true。旧 `698f689b0` 是历史前向候选，不是最终 head。三层已通过栈顶合一，不能再让 #843/#864 单独合入，也不能用底层分支单独前向的冲突推翻栈顶合入事实。

## 收据分账

缩写：P=通过，F=失败，E=错误，S=跳过，X=预期失败。以下均为既有证据核验，不是本次重跑测试。

| 对象 | 固定版本 | 读数 / 证据 | 适用边界 |
|---|---|---|---|
| S2 基线 | `72be60059f2e3e5dc9cb0ebe70c51c906ed5f33e` | 14363P/0F/0E/85S/2X；collected=14450，dirty=false，exit 0 | 含 #863，尚不含 #870；不是 #870 合后读数 |
| #870 三叶 | `f5cfc353ff093a2ea9d5aebc6e7499764712e545` | registry 5/5；frontend 六步含 E2E exit 0、128.644s；Python Ruff 通过，14272P/0F/0E/85S/2X、exit 0 | 三份 run.json 均 complete=true、source_unchanged=true；pytest 收据旧格式没有 scope，X 与总数辅以日志/JUnit 核实，不声称通过新版完整收集面校验 |
| #870 变异 | `b674e54b6b41eeaf7c00956c13039308a725bab1` | 5/5 改坏即红、还原即绿；suite=custom | `git diff --name-only b674e54b6 f5cfc353f` 仅 `docs/handoffs/inflight/fix-cutoff-single-source-0923.md`；代码等价不是执行 revision 相同 |
| #870 广域定向 | `8e79893729da` 上的提交前工作树 | 1361P/0F/0E/7S，dirty=true | 保留为作者诊断证据；不能移签为 b674/f5cfc 或干净全量 |
| #865 合后 main | `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4` | 14515P/0F/0E/85S/2X，collected=14602，dirty=false，exit 0 | 精确 revision、环境、完整收集面均通过校验 |
| #873 后 main | `760248ecebc79fbe4f2686ddd42255c1a00ec862` | 14568P/0F/0E/85S/2X，collected=14655，dirty=false，exit 0 | 同上；原产出树已不在，以同 revision 的干净检出复核收据，不伪称在新树重跑 |
| 本轮 main 基线 | `9a02279863733c9b9f60fd92fcc7e840fa83f878` | 本次未跑全量 | 与 760248ece 的差分仅 docs，但现有校验器仍拒绝 revision 转签 |

### 原件路径与指纹

公共根：`R=~/.finance-runtime/reviews`，`T=~/.finance-runtime/test-receipts`。SHA256 用于识别本次读过的具体内容。S2 原始编号收据与该树 `latest-*` 内容指纹相同，下表引用原件；`latest-*` 是可变指针，不可只凭文件名采信。

| 原件 | SHA256 |
|---|---|
| `T/gate-Ja9g87Sx/pytest.json` | `dffe377116eff827419841957628c85080e1e148958c3a6d48a96e3e1a9f4da2` |
| `R/pr870-gates-20260923/gates/python/receipts/gate-mnt3M8W0/pytest.json` | `19eb2ea6ccfed60e2f1af0d81fe42ff7f916ad1a041d55802a07666b05679c3d` |
| `R/research-tail-union-postmerge-20260923/cutoff-mutations-b674e54b6/results.json` | `f196acbceaddab9f8f94c08b95b022d7e6d3701cf21e334f8aebc99b55cf3155` |
| `T/20260922T165156Z-8e798937-6d08956bfb4a.json` | `6b741980e9d0bc51c5519e2ce8bd61514a1ec4be652cceab8c604e9c39b78a9d` |
| `T/gate-uJI0y7Me/pytest.json` | `734d7a700ee34508bebaed35c1c1e6ec212656644a19ea32fb585c9e1caade07` |
| `T/gate-8gJX3FS8/pytest.json` | `f17231e7e658ca672602d46f83b5f94a816c7c74f87f663226f82ba6e33478cb` |

#870 三叶原件位于 `R/pr870-gates-20260923/gates/{registry,frontend,python}/run.json`；Python 汇总另见 `gates/python/0.stdout.log.txt` 和 `gates/python/junit.xml`。本轮未能读取旧记录中的 `R/main-tip-gate-20260922/postmerge/gates/python/run.json`，S2 结论以表内仍可读的收据为准。

### 本次实际运行的校验

均使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`：

- 在干净 `R/runtime-identity-effects-20260922/post-merge-main` 的校验器上，对 `T/gate-uJI0y7Me/pytest.json` 指定 `--expect-revision 3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4 --require-full-scope --base-drift-max 5`，exit 0；执行/收集对账 14602，基座漂移 4。
- 在干净 `R/runtime-identity-effects-20260922/latest-main-760248ecebc7` 的校验器上，对 `T/gate-8gJX3FS8/pytest.json` 指定 `--expect-revision 760248ecebc79fbe4f2686ddd42255c1a00ec862 --require-full-scope --base-drift-max 5`，exit 0；执行/收集对账 14655，基座漂移 2。
- 在本分支基座 `9a0227986` 的校验器上，把同一份 760248ece 收据的期望版本改为 `9a02279863733c9b9f60fd92fcc7e840fa83f878`，其余标志不变，exit 1，明确拒绝“revision 一致”和“revision 与期望相符”两项。该反例是适用性检查，不是新一轮变异测试，也不是产品测试失败。

## 决策与被否方案

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 最新 main 上独立文档分支，仅改本次核实字段 | 沿旧 #858 分支继续提交或整份复制旧 INDEX diff | #858 已合入，旧树另有在途修改；整份移植会重放过期状态 |
| 保留每份收据真实 revision，另证代码等价 | 把 S2、广域回归或变异统一写成最终 head 验证 | 合入、执行、适用性是不同证据合同 |
| 只更新本单队列指针与自己的交接 | 顺手覆盖三条 runtime inflight | 其他分支有自己的写者与历史；其“未合 / 按序合”旧状态应由独立收口处理 |
| 文档推送供审，不合 main、不部署、不清理 | 把历史授权解释为本轮自动合并或资源回收授权 | 本轮续做的是证据收口，未得到新的清理授权 |

工具沉淀：复用现有 Gitea CLI、Git 和收据校验器；错误版本反例已证明现有校验能拦，未发现需要本单新增脚本或修改门禁的缺口。这里没有新增通用框架，也不重复建立能力清单。

## 后续边界

- #75 对固定 #863/#870/#865 合并提交事后审，#76 自然八题、#66 前向 #855 均未由本轮完成，不因台账变绿而注销。
- 三份 runtime inflight 仍有旧候选/WIP/按序合措辞，需由所属分支写者另做文档收口；本次队列已给出正确合并目标。
- 跨进程续跑、费用对账执行者、实际部署与真实金融质量不能由工程测试总数证明。本轮未切换、重启或检查生产服务。
- 若要证明后来 main 的完整门禁，另在干净固定版本重跑；本次只做文档检查，不将历史收据冒充本分支门禁。
- 已合分支、旧工作树和 basetemp 均未由本轮清理；不得据本文件推导清理授权或认领并行修改。
