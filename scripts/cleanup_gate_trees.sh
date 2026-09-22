#!/usr/bin/env bash
# 批量拆「门禁快照树」。默认 dry-run 只打印；--apply 才删。
#
# 拆两类：
#   1. detached 树：按提交号 `git worktree add --detach` 出来跑门禁 / 审查的快照，无分支。跑完就该拆，
#      重建只要一个提交号；2026-09-23 盘上静置 78 棵、15 GB。
#   2. 分支已完整进入基线（gitea/main）的树：补丁都在 main 了，树本身只是占位。
# 两类都还要同时满足：树干净（忽略 .code-review-graph 缓存被清造成的 ' D' 噪音）、根目录 N 天没动过、
# 没有进程打开它或把 cwd 放在里面、不被 ~/Library/LaunchAgents/*.plist 或 ~/.local/bin/* 引用
# （那是定时任务的代码根——`.devin-worktrees/ima-queue-auto-triage`、`kb-runtime` 都是 detached 树）。
# 主树永不动。分支引用不删（`git branch -d` 是另一件事）。
#
# 用法：
#   bash scripts/cleanup_gate_trees.sh                  # 当前仓，dry-run
#   bash scripts/cleanup_gate_trees.sh --apply          # 真删
#   bash scripts/cleanup_gate_trees.sh --days 3         # 只动 3 天没动过的（默认 2）
#   bash scripts/cleanup_gate_trees.sh --repo <path>    # 别的仓（如知识库仓）
#   bash scripts/cleanup_gate_trees.sh --base main      # 基线引用（默认 gitea/main，没有则 main）
# 退出码：0 完成；4 lsof 120 秒内拿不到「谁在用」（拒绝盲删）；5 参数错。
set -uo pipefail

APPLY=0; DAYS=2; REPO=""; BASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --days) DAYS="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --base) BASE="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 5 ;;
  esac
done
[ -z "$REPO" ] && REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -d "$REPO" ] || { echo "不是 git 仓: $REPO" >&2; exit 5; }
REPO="$(cd "$REPO" && pwd -P)"
MAIN_TREE="$(git -C "$REPO" worktree list --porcelain | awk 'NR==1{print substr($0,10)}')"
if [ -z "$BASE" ]; then
  if git -C "$REPO" rev-parse --verify -q gitea/main >/dev/null; then BASE=gitea/main; else BASE=main; fi
fi
BASE_SHA="$(git -C "$REPO" rev-parse "$BASE" 2>/dev/null)" || { echo "基线引用不存在: $BASE" >&2; exit 5; }
NOW=$(date +%s); CUTOFF=$((NOW - DAYS * 86400))

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# 「谁在用」只采样一次：所有进程打开的文件 + 每个进程的 cwd，之后做子串匹配。
# -S 2 给内核调用 2 秒超时（卡死的挂载点不至于拖住整个 lsof）；再套 120 秒看门狗，超时就拒绝删。
( lsof -S 2 -w -Fn 2>/dev/null | sed -n 's/^n//p' | grep '^/' | sort -u > "$TMP/open"; : > "$TMP/open.done" ) &
i=0; while [ ! -f "$TMP/open.done" ] && [ $i -lt 120 ]; do sleep 1; i=$((i+1)); done
if [ ! -f "$TMP/open.done" ]; then
  echo "lsof 120 秒未完成，无法判断哪些树正被使用，本轮不动任何树。" >&2; exit 4
fi
# 定时任务代码根：plist 与启动器里出现的家目录路径，任何是它们前缀的树都不能拆。
{ grep -hoE "$HOME/[^<\"' ]+" "$HOME"/Library/LaunchAgents/*.plist 2>/dev/null
  grep -hoE "($HOME|\\\$HOME|~)/[^\"' )]+" "$HOME"/.local/bin/* 2>/dev/null | sed "s#^\\\$HOME#$HOME#; s#^~#$HOME#"
} | sort -u > "$TMP/refs"

gb() { awk -v k="$1" 'BEGIN{printf "%.1f", k/1048576}'; }
TOTAL=0; N=0
consider() {   # consider <path> <why>
  local p="$1" why="$2" reason="" k
  [ "$p" = "$MAIN_TREE" ] && return 0
  [ -d "$p" ] || return 0
  if grep -qF -- "$p" "$TMP/open"; then reason="有进程打开/cwd 在里面"
  elif grep -qF -- "$p" "$TMP/refs"; then reason="被 launchd/启动器引用（定时任务代码根）"
  elif [ "$(stat -f %m "$p" 2>/dev/null || echo 0)" -gt "$CUTOFF" ]; then reason="根目录 ${DAYS} 天内有动静"
  elif [ -n "$(git -C "$p" status --porcelain 2>/dev/null | grep -v '^ D .code-review-graph' | head -1)" ]; then reason="有未提交改动"
  fi
  if [ -n "$reason" ]; then echo "  SKIP  $p  ($reason)"; return 0; fi
  k=$(du -xsk "$p" 2>/dev/null | cut -f1); TOTAL=$((TOTAL + k)); N=$((N + 1))
  if [ "$APPLY" = 1 ]; then
    if git -C "$REPO" worktree remove --force -- "$p" >/dev/null 2>&1; then echo "  RM    $(gb "$k")G  $p  [$why]"
    else echo "  FAIL  $p  (git worktree remove 失败)" >&2; fi
  else
    echo "  DRY   $(gb "$k")G  $p  [$why]"
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
[ "$APPLY" = 1 ] && git -C "$REPO" worktree prune
echo "合计 $N 棵 $(gb "$TOTAL") GB$([ "$APPLY" = 1 ] || echo '（dry-run，--apply 才删）')"
