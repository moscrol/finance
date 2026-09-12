#!/usr/bin/env bash
# Codex SessionStart hook：委托给 .claude/hooks/load-memory.sh，不再维护第二份实现。
#
# 之前这里是一份早期拷贝：无预算、`cat` 整篇项目笔记（300KB+，其中 7 成是交接流水），
# 与 .claude 版在 2026-08-10 收窄到 12000 字节预算后分道扬镳——同一份逻辑存两处必漂。
# 退出码恒 0：观测设施故障不该阻断会话。
set -uo pipefail

# 候选仓根逐个验证，而不是「第一个非空就算数」：
# 环境变量非空但指向错目录（例如父目录）会让 `[ -n "$ROOT" ]` 短路掉后面的回退，
# 结果是找不到脚本、静默 exit 0、注入为空。只有「该目录下真有被委托脚本」才算命中。
pick_root() {
  local cand
  for cand in "${CODEX_PROJECT_DIR:-}" "${CLAUDE_PROJECT_DIR:-}" \
              "$(git rev-parse --show-toplevel 2>/dev/null)" \
              "$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"; do
    [ -n "$cand" ] || continue
    [ -f "$cand/.claude/hooks/load-memory.sh" ] || continue
    printf '%s\n' "$cand"
    return 0
  done
  return 1
}

ROOT="$(pick_root)" || exit 0

# 必须在目标仓里执行：被委托脚本用 cwd 找 git（load-memory.sh:76 的
# `git rev-parse --show-toplevel`、:102 的 `--abbrev-ref HEAD`）。
# 只把路径拼对、却在别处（如 /tmp）跑它，会注入到「当前分支：?」且没有项目笔记。
( cd "$ROOT" && bash .claude/hooks/load-memory.sh )
exit 0
