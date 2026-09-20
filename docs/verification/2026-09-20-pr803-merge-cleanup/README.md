# PR #803 合入与保守工作树清理（2026-09-20）

## 身份、授权与结论

用户在 K3 两轴审核通过后要求「你来接手执行」，覆盖 #803 合 main、#789 接替评论及分批保守清树；不含生产部署或删除未认领内容。

- #803 已通过 Gitea `fast-forward-only` 合入：`e51c5157c9ea9aa86491c486663700e7d7696a6f` → **`728f327160bbd2485cb635e7ef09d040d718d7b5`**。`head_commit_id` 锁头、`force_merge=false`，来源分支保留。
- 本轮全叶重新测试的就是 728f3271；合后远程 main 与它完整相等，不把 d95b706e 的历史读数移签过来，也没有另造未测试 merge commit。
- #789 已补接替评论 [5050](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/789#issuecomment-5050)。正文原有 #801 说明，缺的是评论；祖先关系再次验证成立。
- 已有 80 份封存原件 + 2 份外部 K3 事件流重算哈希全符。只核继承证据，不宣称第三次独立审核。
- 8792 前后均 healthy、`bf662e9310ff751a4c31763815ee78fb7d6d5122`、dirty=false、code_matches_repo=true。未切代码根、未改 launchd/L2/索引、未写生产数据库。

外部原件目录：`~/.finance-runtime/reviews/pr803-merge-cleanup-20260920/`。本目录的 `manifest.json` 逐字节绑定复制原件；执行脚本存 `.py.txt`，不是新增生产入口。二进制元数据/浏览器附件仅在外部保留，以哈希登记，不提交数据库或压缩包。

## 最终提交的完整门禁

两棵独占检出首尾 revision=728f3271、全树 status 为空、identity_stable=true；解释器为主树 `.venv-workbench/bin/python`。白名单环境与 umask022，KB 固定 `1254224be89e2c4974350b7f3e985dbedb5dc043`、研究站固定 `f606583867fe1cad8de96b06be1dd6cfe2b57e51`。

| 检查 | 本轮实跑 | 原件 |
|---|---|---|
| Python 全量 | 11913 passed / 85 skipped / 2 xfailed，rc0 | `python/pytest.log.txt`、`python/python-registry.json` |
| Ruff | rc0 | `python/ruff.log.txt` |
| registry parse/check/tables/views + ledger-crosswalk | 五项 rc0 | `python/*log.txt` |
| 前端 install/lint/typecheck/test/build/E2E | 六项 rc0；单测110P，E2E34P/2S | `frontend/frontend.json`、逐步日志 |
| 合前严格收据 | revision/依赖/解释器一致，干净，base-drift=0，rc0 | `receipt-check-premerge.*` |
| 合后严格收据 | 对新 fetch 的 gitea/main 完整SHA校验，base-drift=0，rc0 | `receipt-check-postmerge.*` |
| 文档工作区窄扫描（提交前） | 39个扫描型测试文件，927 passed；Ruff通过 | `docs-scanner-command.json`、`docs-scanner-tests.log.txt`、`docs-ruff.log.txt` |

前端端口19181/19184，不借生产8792。完整 pytest 510.07秒；17条警告保留。文档收尾提交前另跑39个会扫描全树路径/AST/目录的测试文件，128.59秒、927 passed；命令记录明确绑定待提交文档工作区，不是干净文档提交的完整门禁。原始 Python 收据为 `python/receipts/20260920T102128Z-728f3271.json`。后续文档分支不继承这份全量签字。

## 清理过程与保全

看板初始336棵；两棵本轮门禁树建立后338棵。初筛125棵：98棵干净已合开发树、27棵干净已合生产快照。这里要求**全树干净**，不沿用看板“只要没有代码脏文件就可拆”的宽口径。

删除前逐棵检查：

1. 固定HEAD/分支，全树tracked与untracked为空，拒绝隐藏index标记、子模块、锁和进行中的Git操作。
2. HEAD及私有reflog的old/new提交都是固定main祖先，不仅仅补丁等价；近期两小时的Git事件或受控文件改写也拒绝。
3. 每个受控文件原始Git blob哈希与index逐字节核对；ignored仅允许pycache、pytest/ruff缓存。未知忽略文件一律保留。
4. `ps`、`lsof`、loaded launchd、启动器/配置及顶层软链引用复查，删除前再核一次。不保存无关进程完整参数或凭证。
5. 先封存私有Git元数据、缓存及逐文件清单/恢复命令，再 `git worktree remove`，不加force、不删分支。

结果：

- 开发批次：29候选，**28移除、1跳过**。`fwp-wt-acceptance-tests` 的HEAD已合，但reflog含未被main保留的提交，拒删；没有因HEAD已合而丢历史。
- 旧生产快照批次：**16移除**。保留当前bf662e93、紧邻旧切换ce009718（未记port）和上一条明确8792的db2963d4；不猜无port记录归属。活跃40fd5a84 sidecar亦保留。
- 两批共44棵旧树；各批refs逐字节不变，注册表差集恰等于删除清单，其他注册项逐字段未变。
- 74棵初筛候选含未知ignored内容（用户库、方法收据、代码地图、依赖等），全保留；23棵已合但脏的开发树也全保留，其中10棵只是非代码内容，仍未认领。
- 剩余生产快照21棵，不为了凑“只留两棵”删除有数据或不明用途的树。
- 抽一棵已移除快照0399b980重建，3549个受控文件blob与保存清单一致、status干净，再正常移除演练树。这是一次恢复抽验，不冒称44棵全演练。
- 本轮自建前端树的Playwright结果和Git元数据另行归档，只有刚安装的可再生node_modules丢弃，再无force拆树；Python树复用为文档交接树，测试生成的ignored用户文件仍留在本地。
- 最终注册树 **293棵**：336旧树 − 44旧树 + 1本轮留存文档树。与初始清单的路径差集再次精确核对。

外部`worktree-metadata/`保存44棵的元数据压缩件与tracked清单；两个`removal-*.json`含精确恢复命令。文件不存在不等于提交丢失，所有44个revision对象及封存哈希再次校验成功。

空间：删除批次前22.47 GiB，收尾三次约28.96 GiB，观测净增约6.49 GiB；期间有测试和其他进程并发，不把整机净变化全部归因给本轮，也不加总目录逻辑大小。

## 失败/阻断也保留

- Python/前端本轮未失败；其他历史红读数未覆盖。
- 自建前端树首次清理被引用扫描挡住：通用basename `finance-workspace-private`误命中其他路径，0删除。仅对本轮通用树名改为完整路径匹配；44旧树的独特basename判据未变，原批次脚本逐字节另封存。见`own-frontend-cleanup-first-stop.json`。
- `git status`的干净承诺不覆盖ignored，更不覆盖reflog可恢复性。本轮并未证明被保留的库都是生产数据，也没有读其正文来猜用途；未知即保留。

## 不成立的推论 / 后续

R2跨午夜、原夜跑恢复全链、真实行情采集、无人值守下一夜、生产回填和自然模型回答质量均未因本次工程合入获认证。#802以及#797/#798/#800仍按各自合同推进。继续清理需先认领脏文件/忽略库、决定归档策略，不能直接复跑一次性删除器。

本次文档封存属于新文档分支；其门禁与728f3271源码门禁分账。封存提交 `d2a72bb688cacf8bc1d8ee9e2fbe685290d172e1` 已推gitea；文档 [PR #804](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/804) 保持待审，#803已补收尾评论 [5056](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/803#issuecomment-5056)。发布时再次只读查询 `/api/health`，生产身份仍与上述一致。

提交钩子实际无失败，不适用项按配置跳过。首次提交因未提供`-m`而打开编辑器、超时未提交；确认无持锁进程后，仅清理本工作树遗留`index.lock`再提交成功。原始日志的结尾空行保留，不为了消除`diff --check`提示改写证据。合入状态以PR和看板为准，不维护另一张分支已合清单。
