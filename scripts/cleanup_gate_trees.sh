#!/usr/bin/env bash
# 批量拆「门禁快照树」。默认 dry-run 只打印；--apply 才删。
#
# 拆两类：
#   1. detached 树：按提交号 `git worktree add --detach` 出来跑门禁 / 审查的快照，无分支。跑完就该拆，
#      重建只要一个提交号；2026-09-23 盘上静置 78 棵、15 GB。
#   2. 分支已完整进入基线（gitea/main）的树：补丁都在 main 了，树本身只是占位。
# 两类都还要同时满足：树干净（忽略 .code-review-graph 缓存被清造成的 ' D' 噪音）、树内 N 天没动过、
# 没有进程打开它或把 cwd 放在里面、不被 ~/Library/LaunchAgents/*.plist 或 ~/.local/bin/* 引用；
# 任何其他 ignored/untracked 内容、状态采样失败或扫描超时都跳过/停止，不真删。
# （那是定时任务的代码根——`.devin-worktrees/ima-queue-auto-triage`、`kb-runtime` 都是 detached 树）。
# 主树永不动。分支引用不删（`git branch -d` 是另一件事）。
#
# 用法：
#   bash scripts/cleanup_gate_trees.sh                  # 当前仓，dry-run
#   bash scripts/cleanup_gate_trees.sh --apply          # 真删
#   bash scripts/cleanup_gate_trees.sh --days 3         # 只动 3 天没动过的（默认 2）
#   bash scripts/cleanup_gate_trees.sh --repo <path>    # 别的仓（如知识库仓）
#   bash scripts/cleanup_gate_trees.sh --base main      # 基线引用（默认 gitea/main，没有则 main）
# 环境变量：LSOF_TIMEOUT（默认 120 秒）、CLEANUP_STATUS_TIMEOUT（默认 30 秒/树）、CLEANUP_TIMEOUT（默认 120 秒/轮）。
# 退出码：0 完成；4 无法完成安全审计（拒绝盲删）；5 参数错。
set -uo pipefail

APPLY=0; DAYS=2; REPO=""; BASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --days)
      [ $# -ge 2 ] || { echo "--days 缺少参数" >&2; exit 5; }
      case "$2" in ''|*[!0-9]*) echo "--days 必须是非负整数: $2" >&2; exit 5 ;; esac
      DAYS="$2"; shift 2 ;;
    --repo|--base)
      [ $# -ge 2 ] || { echo "$1 缺少参数" >&2; exit 5; }
      if [ "$1" = --repo ]; then REPO="$2"; else BASE="$2"; fi
      shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 5 ;;
  esac
done
[ -z "$REPO" ] && REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -d "$REPO" ] || { echo "不是 git 仓: $REPO" >&2; exit 5; }
REPO="$(cd "$REPO" && pwd -P)"
canonical_dir() {
  (cd "$1" 2>/dev/null && pwd -P)
}
MAIN_TREE_RAW="$(git -C "$REPO" worktree list --porcelain | awk 'NR==1{print substr($0,10)}')" || exit 5
[ -n "$MAIN_TREE_RAW" ] || { echo "无法读取主工作树" >&2; exit 5; }
MAIN_TREE="$(canonical_dir "$MAIN_TREE_RAW")" || { echo "无法解析主工作树" >&2; exit 5; }
if [ -z "$BASE" ]; then
  if git -C "$REPO" rev-parse --verify -q gitea/main >/dev/null; then BASE=gitea/main; else BASE=main; fi
fi
BASE_SHA="$(git -C "$REPO" rev-parse "$BASE" 2>/dev/null)" || { echo "基线引用不存在: $BASE" >&2; exit 5; }
NOW=$(date +%s); CUTOFF=$((NOW - DAYS * 86400))

TMP="$(mktemp -d)" || { echo "无法创建临时目录" >&2; exit 5; }
trap 'rm -rf "$TMP"' EXIT
CUTOFF_MARKER="$TMP/cutoff"
: > "$CUTOFF_MARKER" || { echo "无法建立 mtime 阈值" >&2; exit 5; }
python3 - "$CUTOFF" "$CUTOFF_MARKER" <<'PY' || { echo "无法建立 mtime 阈值" >&2; exit 5; }
import os
import sys

cutoff = float(sys.argv[1])
os.utime(sys.argv[2], (cutoff, cutoff))
PY
# 「谁在用」只采样一次：所有进程打开的文件 + 每个进程的 cwd。
# -d '^mem' 排除内存映射；-nP 不反查 DNS/端口名；-S 2 给内核调用 2 秒超时。
# 只有完整 pipeline 成功才写 open.done；拿不到「谁在用」时必须拒绝删除。
LIMIT="${LSOF_TIMEOUT:-120}"
case "$LIMIT" in ''|*[!0-9]*) echo "LSOF_TIMEOUT 必须是正整数: $LIMIT" >&2; exit 5 ;; esac
[ "$LIMIT" -gt 0 ] || { echo "LSOF_TIMEOUT 必须大于 0" >&2; exit 5; }
STATUS_LIMIT="${CLEANUP_STATUS_TIMEOUT:-30}"
case "$STATUS_LIMIT" in ''|*[!0-9]*) echo "CLEANUP_STATUS_TIMEOUT 必须是正整数: $STATUS_LIMIT" >&2; exit 5 ;; esac
[ "$STATUS_LIMIT" -gt 0 ] || { echo "CLEANUP_STATUS_TIMEOUT 必须大于 0" >&2; exit 5; }
(
  if lsof -nP -S 2 -w -d '^mem' -Fn 2>/dev/null \
      | sed -n 's/^n//p' \
      | awk '/^\// { print }' \
      | sort -u > "$TMP/open"; then
    : > "$TMP/open.done"
  else
    : > "$TMP/open.failed"
  fi
) >/dev/null 2>&1 &
LSOF_JOB=$!
i=0
while [ ! -f "$TMP/open.done" ] && [ ! -f "$TMP/open.failed" ] && [ "$i" -lt "$LIMIT" ]; do
  sleep 1
  i=$((i+1))
done
if [ -f "$TMP/open.failed" ]; then
  echo "lsof 采样失败，无法判断哪些树正被使用，本轮不动任何树。" >&2
  exit 4
fi
if [ ! -f "$TMP/open.done" ]; then
  pkill -P "$LSOF_JOB" 2>/dev/null; kill "$LSOF_JOB" 2>/dev/null
  echo "lsof ${LIMIT} 秒未完成，无法判断哪些树正被使用，本轮不动任何树（可设 LSOF_TIMEOUT 放宽）。" >&2
  exit 4
fi
echo "lsof 采样 ${i}s，$(wc -l < "$TMP/open" | tr -d ' ') 条打开路径"
# 定时任务代码根：先收集字面路径，再统一 canonical 化，避免 plist 引用软链接时漏守卫。
RAW_REFS="$TMP/refs.raw"
: > "$RAW_REFS"
for file in "$HOME"/Library/LaunchAgents/*.plist; do
  [ -f "$file" ] || continue
  grep -hoE "$HOME/[^<\"' ]+" "$file" >> "$RAW_REFS"
  rc=$?
  [ "$rc" -le 1 ] || { echo "无法读取启动项: $file" >&2; exit 4; }
done
for file in "$HOME"/.local/bin/*; do
  [ -f "$file" ] || continue
  grep -IhoE "($HOME|\\\$HOME|~)/[^\"' )]+" "$file" > "$TMP/ref.matches"
  rc=$?
  if [ "$rc" -gt 1 ]; then
    echo "无法读取启动器: $file" >&2; exit 4
  elif [ "$rc" -eq 0 ]; then
    sed "s#^\\\$HOME#$HOME#; s#^~#$HOME#" "$TMP/ref.matches" >> "$RAW_REFS" || exit 4
  fi
done
python3 - "$RAW_REFS" "$TMP/refs" <<'PY' || { echo "无法解析启动器引用" >&2; exit 4; }
import os
import sys

with open(sys.argv[1], encoding="utf-8") as source, open(sys.argv[2], "w", encoding="utf-8") as target:
    for line in source:
        raw = line.rstrip("\r\n")
        if raw:
            target.write(os.path.realpath(raw) + "\n")
PY
sort -u "$TMP/refs" -o "$TMP/refs" || exit 4
CLEANUP_LIMIT="${CLEANUP_TIMEOUT:-120}"
case "$CLEANUP_LIMIT" in ''|*[!0-9]*) echo "CLEANUP_TIMEOUT 必须是正整数: $CLEANUP_LIMIT" >&2; exit 5 ;; esac
[ "$CLEANUP_LIMIT" -gt 0 ] || { echo "CLEANUP_TIMEOUT 必须大于 0" >&2; exit 5; }
CLEANUP_DEADLINE=$(( $(date +%s) + CLEANUP_LIMIT ))
check_deadline() {
  if [ "$(date +%s)" -ge "$CLEANUP_DEADLINE" ]; then
    echo "清理扫描超过 ${CLEANUP_LIMIT} 秒，无法完成安全审计，本轮不动任何树。" >&2
    exit 4
  fi
}

path_is_same_or_child() {
  case "$1" in
    "$2"|"$2"/*) return 0 ;;
    *) return 1 ;;
  esac
}
is_open() {
  awk -v root="$1" '$0 == root || index($0, root "/") == 1 { found=1 } END { exit !found }' "$TMP/open"
}
is_referenced() {
  local ref
  while IFS= read -r ref; do
    [ -n "$ref" ] || continue
    if path_is_same_or_child "$1" "$ref" || path_is_same_or_child "$ref" "$1"; then
      return 0
    fi
  done < "$TMP/refs"
  return 1
}
git_status_safe() {
  python3 - "$1" "$STATUS_LIMIT" <<'PY'
import subprocess
import sys

try:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--ignored"],
        cwd=sys.argv[1], capture_output=True, text=True,
        timeout=float(sys.argv[2]), check=False,
    )
except subprocess.TimeoutExpired:
    print(f"git status 超过 {sys.argv[2]} 秒: {sys.argv[1]}", file=sys.stderr)
    raise SystemExit(124)
if result.returncode:
    sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)
sys.stdout.write(result.stdout)
PY
}
has_recent_activity() {
  local recent
  [ "$(stat -f %m "$1" 2>/dev/null || echo 0)" -gt "$CUTOFF" ] && return 0
  recent="$(find "$1" \( -type f -o -type d \) -newer "$CUTOFF_MARKER" -print -quit 2>/dev/null)" || return 0
  [ -n "$recent" ]
}

gb() { awk -v k="$1" 'BEGIN{printf "%.1f", k/1048576}'; }
TOTAL=0; N=0; FAILURES=0
consider() {   # consider <registered-path> <why>
  local raw="$1" why="$2" p reason="" k status kept_status
  check_deadline
  p="$(canonical_dir "$raw")" || { echo "  SKIP  $raw  (无法解析路径)"; return 0; }
  [ "$p" = "$MAIN_TREE" ] && return 0
  [ -d "$raw" ] || return 0
  if is_open "$p"; then reason="有进程打开/cwd 在里面"
  elif is_referenced "$p"; then reason="被 launchd/启动器引用（定时任务代码根）"
  elif ! status="$(git_status_safe "$raw")"; then
    echo "  FAIL  $raw  (Git 状态采样失败，整轮停止)" >&2
    exit 4
  else
    kept_status="$(printf '%s\n' "$status" | grep -vE '^.. \.code-review-graph(/|$)' || true)"
    [ -n "$kept_status" ] && reason="有未提交或 ignored 内容"
  fi
  [ -n "$reason" ] || { has_recent_activity "$raw" && reason="树内 ${DAYS} 天内有动静"; }
  if [ -n "$reason" ]; then echo "  SKIP  $raw  ($reason)"; return 0; fi
  k=$(du -xsk "$raw" 2>/dev/null | cut -f1); TOTAL=$((TOTAL + k)); N=$((N + 1))
  if [ "$APPLY" = 1 ]; then
    if git -C "$REPO" worktree remove --force -- "$raw" >/dev/null 2>&1; then echo "  RM    $(gb "$k")G  $raw  [$why]"
    else echo "  FAIL  $raw  (git worktree remove 失败)" >&2; FAILURES=1; fi
  else
    echo "  DRY   $(gb "$k")G  $raw  [$why]"
  fi
}

echo "仓 $REPO  基线 $BASE=${BASE_SHA:0:12}  阈值 ${DAYS} 天  模式 $([ "$APPLY" = 1 ] && echo 真删 || echo dry-run)"
git -C "$REPO" worktree list --porcelain \
  | awk '/^worktree /{p=substr($0,10)} /^branch /{print p"\t"substr($0,8)} /^detached/{print p"\tDETACHED"}' > "$TMP/wts"
while IFS=$'	' read -r p b; do
  if [ "$b" = DETACHED ]; then consider "$p" "detached"
  elif git -C "$REPO" merge-base --is-ancestor "$b" "$BASE_SHA" 2>/dev/null; then consider "$p" "已合 ${b#refs/heads/}"
  fi
done < "$TMP/wts"
if [ "$APPLY" = 1 ]; then
  git -C "$REPO" worktree prune || FAILURES=1
fi
echo "合计 $N 棵 $(gb "$TOTAL") GB$([ "$APPLY" = 1 ] || echo '（dry-run，--apply 才删）')"
exit "$FAILURES"
