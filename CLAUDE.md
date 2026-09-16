@AGENTS.md

## Claude Code 备注

- `.claude/skills/` 是 `skills/` 的软链视图（人工策划的子集），规范源永远是 `skills/<name>/SKILL.md`；视图漂移用 `python3 scripts/build_registry.py generate-views` 修；不要在 `.claude/skills/` 里放实目录。
- 标了 `disable-model-invocation: true` 的技能（`daily-full-review`、`duckdb-backfill`、`sector-data`、`serenity-alpha`、`strategy-evolve`、`checkpoint-recheck-mac-setup`）不出现在你的技能列表里，因为它们有副作用（写库、写飞书、打上游 API、装 launchd）。用户用触发词提到时，提示对方输入 `/<skill>` 手动调用，不要绕开它用别的方式复现步骤。
- 项目 hooks 在 `.claude/settings.json`：SessionStart 注入记忆底座（`.claude/hooks/load-memory.sh`）与工作区事实（`scripts/session_facts.sh`），SessionEnd 检测交接过期。用户级 `~/.claude/settings.json` 另有危险 git 命令拦截、共享仓陈旧树拦截、编辑后 ruff。hook 退出码恒 0，观测设施故障不阻断会话。
