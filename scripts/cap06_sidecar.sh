#!/bin/zsh
# 06 号单（自适应研究）验收旁车：从任意工作树起一个与生产同形的 Workbench 实例。
#
# 与 intelligence/eval/live_probe.py 的 sidecar 差别（刻意）：
#   - 不切 marker lane（WORKBENCH_GROUNDED_PRESENTER 沿生产），验收看的是用户真实看到的答案；
#   - RAG worker 沿生产开（RAG_WORKER_ENABLED=1）——跳过预热会让健康的 kb_search 看起来慢 4 倍
#     （.claude memory: harness-must-reproduce-production-runtime-warmup）；
#   - durable 事件流落独立目录（FORESIGHT_EPISODE_STORE），读数要看 tool_budget_state 这类
#     投影里没有的事件；
#   - 判官二进制改指 ~/.grok/bin/grok 软链：生产启动器钉的带版本号下载件会被自动更新清掉
#     （.claude memory: judge-binary-pinned-to-versioned-autoupdating-download）。
#
# 用法：
#   scripts/cap06_sidecar.sh start <repo_root> <port> <label>
#   scripts/cap06_sidecar.sh stop <label>
#   scripts/cap06_sidecar.sh status <label>
# 不碰 8792 / 8793 / 8795 / 8799 / 8801。

set -euo pipefail

ROOT="${CAP06_ROOT:-$HOME/.finance-runtime/cap06-20260909}"
LAUNCHER="$HOME/.local/bin/start-finance-workbench"
PYTHON="${CAP06_PYTHON:-$HOME/finance-workspace-private/.venv-workbench/bin/python}"
RESERVED=(8792 8793 8795 8799 8801)

die() { print -u2 -- "✗ $*"; exit 1; }

cmd="${1:-}"
case "$cmd" in
  start)
    repo="${2:-}"; port="${3:-}"; label="${4:-}"
    [[ -n "$repo" && -n "$port" && -n "$label" ]] || die "start <repo_root> <port> <label>"
    [[ -d "$repo/intelligence" ]] || die "不是仓库树：$repo"
    for r in "${RESERVED[@]}"; do [[ "$port" == "$r" ]] && die "端口 $port 是保留端口"; done
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then die "端口 $port 已有监听"; fi
    [[ -x "$LAUNCHER" ]] || die "缺启动器 $LAUNCHER"
    mkdir -p "$ROOT"
    pidfile="$ROOT/$label.pid"; log="$ROOT/$label.log"
    if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then die "$label 已在跑（pid $(cat "$pidfile")）"; fi
    users="$ROOT/users-$label"; episodes="$ROOT/episodes-$label"
    mkdir -p "$users" "$episodes"
    # 只取启动器的 export 行（含 Keychain 取 key），不执行它的 exec uvicorn。
    set -a
    . <(grep '^export ' "$LAUNCHER")
    set +a
    [[ -n "${FORESIGHT_BUILTIN_LLM_API_KEY:-}${OPENAI_API_KEY:-}" ]] || die "启动器 export 里取不到模型 key"
    export WORKBENCH_REPO_ROOT="$repo"
    export PYTHONPATH="$repo"
    export FORESIGHT_USERS_DIR="$users"
    export FORESIGHT_USER="cap06-$label"
    export FORESIGHT_EPISODE_STORE="$episodes"
    export WORKBENCH_PERSIST_LLM_CONTEXT=1
    if [[ -x "$HOME/.grok/bin/grok" ]]; then export LLM_JUDGE_GROK_BIN="$HOME/.grok/bin/grok"; fi
    print -- "cap06 sidecar[$label]: repo=$repo port=$port users=$users episodes=$episodes"
    print -- "  rev=$(git -C "$repo" rev-parse --short HEAD) judge_bin=${LLM_JUDGE_GROK_BIN:-unset} rag_worker=${RAG_WORKER_ENABLED:-unset} tier=${WORKBENCH_RESEARCH_TIER:-unset}"
    # 06 号单两个开关随调用方环境透传（启动器不设它们）：候选臂用 stall_finalize=3 采读数。
    print -- "  research_progress=${WORKBENCH_RESEARCH_PROGRESS:-on(default)} stall_finalize=${WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES:-0(default)}"
    cd "$repo"
    nohup "$PYTHON" -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port "$port" >"$log" 2>&1 &!
    print -- "$!" >"$pidfile"
    print -- "  pid=$! log=$log"
    ;;
  stop)
    label="${2:-}"; [[ -n "$label" ]] || die "stop <label>"
    pidfile="$ROOT/$label.pid"
    [[ -f "$pidfile" ]] || die "没有 $pidfile"
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then kill "$pid"; sleep 1; kill -0 "$pid" 2>/dev/null && kill -9 "$pid" || true; fi
    rm -f "$pidfile"; print -- "stopped $label (pid $pid)"
    ;;
  status)
    label="${2:-}"; [[ -n "$label" ]] || die "status <label>"
    pidfile="$ROOT/$label.pid"
    if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
      pid="$(cat "$pidfile")"
      port="$(lsof -nP -a -p "$pid" -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $9}' | head -1)"
      print -- "$label running pid=$pid listen=$port"
      [[ -n "$port" ]] && curl -s -m 5 "http://${port}/api/health" | head -c 400; print
    else
      print -- "$label not running"
    fi
    ;;
  *)
    die "用法：start <repo_root> <port> <label> | stop <label> | status <label>"
    ;;
esac
