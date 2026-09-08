#!/usr/bin/env bash
# Codex SessionStart hook：委托给 .claude/hooks/load-memory.sh，不再维护第二份实现。
#
# 之前这里是一份早期拷贝：无预算、`cat` 整篇项目笔记（300KB+，其中 7 成是交接流水），
# 与 .claude 版在 2026-08-10 收窄到 12000 字节预算后分道扬镳——同一份逻辑存两处必漂。
# 退出码恒 0：观测设施故障不该阻断会话。
set -uo pipefail

ROOT="${CODEX_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-}}"
[ -n "$ROOT" ] || ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] || ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"

SH="$ROOT/.claude/hooks/load-memory.sh"
[ -f "$SH" ] && bash "$SH"
exit 0
