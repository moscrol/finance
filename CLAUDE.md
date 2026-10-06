@AGENTS.md

## Claude Code 备注

- `.claude/skills/` 是 `skills/` 的软链视图（人工策划的子集），规范源永远是 `skills/<name>/SKILL.md`；视图漂移用 `python3 scripts/build_registry.py generate-views` 修；不要在 `.claude/skills/` 里放实目录。
- 某个技能你看不到，有三种**不同**成因，可执行路径也不同，别给同一种建议：
  - **没软链进 `.claude/skills/`**：`daily-full-review`、`sector-data`、`stock-deep-dive`、`researcher-valuation`、`opinion-cross`、`strategy1-matrix`、`disclosure-archive`、`serenity-alpha`、`strategy-evolve`、`checkpoint-recheck-mac-setup`、`dispatcher`；以及 2026-09-30 撤出视图的 `up-line`、`watchlist-ma`、`top-gainers-feishu`——这三个**已被 `stock-technicals` 取代**（飞书退役后跑不通，目录按 #729 保留作口径参考），**不要重新软链**，UP 线 / 偏离度 / 自选股均线 / 强势股回踩一律走 `stock-technicals`（`tests/test_skill_view_supersession.py` 会拦）。**它们没有斜杠命令，别让用户输入 `/<skill>`**——那条命令不存在。正确说法是：技能存在但未对你暴露，规范源在 `skills/<name>/SKILL.md`；要启用得**手建相对软链再重扫注册表**（需用户同意）：`ln -s ../../skills/<name> .claude/skills/<name> && python3 scripts/build_registry.py scan`。**别拿 `generate-views` 当启用命令**——它只规范**已存在**的条目（修错目标、把物理拷贝换回软链），不创建缺失的软链；对着空视图目录跑它会 exit 0 且什么都不建，入口依然不存在（已实测）。用户不想启用时，你按 SKILL.md 的步骤代跑，但先把它的副作用讲清楚（写库 / 打上游 API / 装 launchd）。
  - **标了 `disable-model-invocation: true`**：`checkpoint-recheck-mac-setup`、`dispatcher`、`serenity-alpha`、`strategy-evolve`。这条只在该技能**同时已软链**时才有意义——你不能自动调、用户可以 `/<skill>`。当前本仓两个条件无交集（这四个都不在视图里），所以**没有任何技能处于「只能用户手动 `/` 调」的状态**。
  - **运行时确定性注入**：`finance-longtail-baseline` / `finance-degraded-fallback` 由 `ASK_LONGTAIL_BASELINE` / `ASK_DEGRADED_FALLBACK` 注入，不可路由也不可手动调，上面两条都不适用。
  **三份名单都会漂，以 frontmatter 与 `ls .claude/skills` 为准，别抄这里的。**
- **`duckdb-backfill` 2026-09-07 起已暴露、可被你直接触发**，别再当它是隐藏件。此前它既标 `disable` 又不在软链里，回补任务从来读不到它，agent 只能硬跑 `daily-full` 过历史日——而那正是回补红线第一条禁止的：`daily-full` 是「取最新」语义，写到历史日等于把今天盘中价写成那天收盘。
- 项目 hooks 在 `.claude/settings.json`：SessionStart 注入记忆底座（`.claude/hooks/load-memory.sh`）与工作区事实（`scripts/session_facts.sh`），SessionEnd 检测交接过期。hook 退出码恒 0，观测设施故障不阻断会话。用户级 `~/.claude/settings.json` 目前不注册任何 hook（2026-10-06 查，用户决定暂不恢复）：`~/.claude/hooks/` 里的 6 个 hook（危险 git 命令拦截、共享仓陈旧树拦截、编辑后 ruff，以及 `session-context.sh` 等 3 个 SessionStart 注入）只在 `settings.json.bak-*` 里注册过，当前既不拦截也不注入。所以 git 操作按 AGENTS.md「Git 与合并」自律，改完 Python 自己跑 `.venv-workbench/bin/python -m ruff check <文件>`。
