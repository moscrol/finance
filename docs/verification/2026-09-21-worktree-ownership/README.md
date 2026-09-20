# Worktree 归属与未收口增量盘点

固定基准 `gitea/main=728f327160bbd2485cb635e7ef09d040d718d7b5`。这是 2026-09-21 03:02 +08:00 的历史采样，不是随时可执行的合入或删除清单。其他 agent 此后仍在产生提交与验收检出。

## 原件与判读

- `inventory.json`：该次看板的全部 322 条注册记录，加人工处置分组；不丢弃失效路径、脏树或 detached 检出。
- `decisions.json`：按功能线记录依据和下一步。`active_lane_and_related_predecessors` 表示主线有近期推进、旧枝属于相关输入，不表示每条旧枝都有独立活跃作者，也不表示已吸收。
- 五条 `unresolved_preserve_not_claimed_complete` 仍保持未决：continuous-depth 设计树、optimization 审计树、ReAct 旁路检出、OPC salvage、8792 K3 旧评审检出。最后一项含财务前提旧代码，不是可丢弃的纯文档。
- 看板采样有 18 条查询异常、53 条脏树、125 条 cherry+。按 `in_main && !dirty && error==""` 得到的 136 只是当时的粗筛数，不能当删除数；ignored 内容、reflog、进程/定时任务引用和授权都未由该谓词检查。
- 脏文件来源只做保留，不替别人提交。主树仍是 detached 的混合现场。

## 本轮实际接手

1. 修复 `scripts/worktree_board.py`：查询失败显式未知，保留 locked/prunable 元数据；失效目录不能借父仓结果；任何未提交文件都阻止进入可拆候选；保留 porcelain 状态列前导空格；全扫描绑定同一个基准 SHA。
2. 将 302132 离线回填线从 `1fd34dc7` 前向整合到当前 main，独立候选 `400d02dd`。仅四个源码/测试文件，不复用原脏树，不覆盖 main CLI 后续功能，不执行回填。
3. Arena 固定提交 `7162a6cb` 已推至 Gitea，并建立 [WIP PR811](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/811)。详见 `arena-followup.md`；这是保全与待办，不是验收。

## 看板验证

- 实现提交：`b6a333a8`、`6a9cb527`、`10b1e275`。
- `board-6a9cb527-targeted.json`：中间固定版本的干净 32P 收据，不能给最后新增的基准固定测试签字。
- 最后一次实现迭代的定向测试 33P、Ruff 通过；当时文档尚未提交，只作局部迭代读数。最终文档提交后另在其 SHA 复验，记录于分支交接/PR。
- `board-before-final.log.txt`：用 main `728f3271` 的旧脚本运行本轮完整测试文件，18P/9F；九个新增反例全部能使旧脚本变红。没有改动任何原工作树做变异。
- 仓内消费者检索只发现 SessionStart 调用 `--this` 和测试；JSON 新增字段是兼容扩展，但外部消费者必须把 `error/locked/prunable` 视为不可清理，把 `cherry_plus=-1` 视为未知。
- 未运行此看板候选的全仓合流门禁，不能用定向 33P 声称已可合 main。

## 回填候选验证

- `backfill-400d02dd-frontend.json`：固定 `400d02dd890af165095ceeea1c95e143ab555f5c`，首尾 clean、身份不变；安装、lint、typecheck、test、build、E2E 六命令均 0，前端 110P、E2E 34P/2S。
- `backfill-frontend-wrong-identity-refused.json`：首次启动参数把完整 SHA 写错，入口以 rc2 拒绝、未执行任何检查；原失败保留，后续从 Git 解析完整 SHA 在新目录重跑。不能覆盖成成功记录。
- registry 五项在 `git archive 400d02dd` 的独立 finance-only 目录检查全 0，范围与 `.github/workflows/registry-check.yml` 只 checkout 本仓一致，不是跨仓全量校验。日志在外部验证根的 `registry-finance-only/`。
- 初次 104P 是整合过程中未提交树的局部读数，不是最终干净候选的全量结论。
- Python 全量的最终结果、最终文档 SHA 与代码 SHA 的关系见日期交接和 PR；本文件不将旧源分支读数移签新候选。

外部验证根：`/Users/a77/.finance-runtime/reviews/ownership-closeout-20260921/backfill-400d02dd/`。

## 残项边界

- 复盘会 `c06a66f3` 仍有真实增量。三个主要源码与其父版本在 main 上无差异；整枝合入会冲突当前指令和两份 nightly plist。旧补丁的批量调用、熔断传播与并发等待后重检仍需离线审查，绝不以保全为由解除停抓。
- Workbench premium / research journey 保留原件。旧文件整体覆盖 main 会删除新功能；8899 服务存活不代表有人继续开发。
- 历史 PR800 的整合预演无冲突，不等于合流全叶通过；运行恢复 PR798 与 main 仍有八处冲突，财务片亦需保留 R6 与单位守卫。
- 活跃线不重复接管。尚未观察到活跃推进的线也不自动判定“没人拥有”；先登记待办并保留原件。
- 本轮没有合 main、切 8792、改定时任务、访问复盘会、执行生产回填、删树或强推。所有 PR 的合入仍需用户确认及完整验收。

## 沉淀

机器层漏洞已修进原看板并补可证伪测试，不新建平行清理器。归属和语义吸收仍需交叉核验会话、提交、源码及 PR，不能仅靠进程存活或 `git cherry` 自动推断。通用方法补充到已有 `git-clean-is-not-deletion-safe.md`；harness-reference 的 `BUILD.md` 有他人改动，本轮不覆盖。
