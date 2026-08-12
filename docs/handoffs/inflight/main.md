# 在途交接 · main
更新：2026-08-12 · Claude

## 这个分支做什么
main 是共享基线。本轮工作（测试套件归零、工具包三件套、hook 修缮）**全部已合并并推送**
（`94157bd1`），无我的在途改动。本文件记的是**接手要知道的地雷与待决事项**。

## 当前状态
main 与 origin/main 同步，未推送 0。
⚠ 工作区 44 个脏文件，**其中 5 个代码文件不是本轮的活**，别提交、别 stash：
`scripts/check_daily_review_data.py`、`scripts/moneyflow/{run_l2_pipeline.sh,write_to_duckdb.py}`、
`market_feature_store/trading_days.py`、`scripts/verify_l2_recovery_artifacts.py`。
其余 39 个是每日 ingest 产物，正常。

## 未验证 / 已知边界
- **SessionEnd hook 在真实会话的触发时机始终未实测**。本轮所有验证都是直接调脚本。
  下次会话若看到本文件被注入，那就是读侧的验收。
- **`import intelligence.api.app` 有文件系统副作用**（导入即初始化用户态存储）。
  这是测试污染真人数据的**根因**，本轮只在测试侧挡住（conftest 模块级清 env），**生产码未改**。
  任何导入该模块的工具（CLI、脚本、IDE 分析）都会碰用户数据目录。建议改惰性初始化。
- **两个大脑目录数据分裂**：交互式 shell 走 `~/agent-memory/.foresight/`（12M），
  服务走 `~/.local/share/finance-workbench/users/`（33M）。同一 user id 两份互不相通。
- 负载敏感偶发：`test_continuous_episode_citations_survive_run_context_reload`
  在一次 564 秒（平时 2.3 倍）的全量跑里失败一次，此后 5 次均过。**成因未定，未修。**
- `scripts/agent_review/` 约 2300 行**无人读过语义**，故未进任何工具包清单。

## 下一步
1. `~/kb-ingest-tx-archive/` 216MB 待用户决定去留（README 写了删除条件）
2. 三件套的「设计」那件仍未收口 → `~/harness-reference/KIT.md` 第一节有材料清单
3. 上面那条 `api.app` 导入副作用值得单独开一支修

## 踩过的坑
- **worktree 里 `.git` 是文件不是目录**：标记路径写死 `$REPO/.git/` 会 `Not a directory`，
  且门禁照样 exit 0 —— 该门禁曾在**所有附属 worktree 里完全失效**。已修（走 `--git-common-dir`）。
- **`git status` 的「干净」是相对 gitignore 的**：删目录类操作必须带 `--ignored`，
  否则会连唯一数据一起删。判据的作用域必须匹配动作的作用域。
- **这个 shell 是 zsh，无引号变量不做词分割**（bash 会）。同一坑本轮犯两次，
  一次导致 pytest `no tests ran` 却被 `diff` 报成「零回归」。**A/B 差分先断言两侧非空。**
- 门禁自噬：「产物必须跟上源」的门禁要把「更新产物」这个动作排除在「源变动」之外。

## 已验证
全量 4513 → 4508 passed / 0 failed（收据 `dirty: False`）；跑完真人数据目录零变化；
四道门禁全绿；四仓 main 均同步。详见 `docs/handoffs/2026-08-12-*.md`。
