#!/bin/zsh
# 起一份验收用 Workbench sidecar：同一套生产 LLM / 判官 / KB 配置，隔离代码、用户与 Episode 存储，不碰 8792。
#
# 用法:
#   zsh scripts/launch_workbench_sidecar.sh <port> <repo_root> <users_dir> <probe_user>
#   例: zsh scripts/launch_workbench_sidecar.sh 8822 /Users/a77/fwp-wt-xxx ~/.finance-runtime/xxx-users probe-xxx-0909
#
# 防的失败形状（2026-09-09 判官修复 01 验收实测）：
# 1. 在别的树上「顺手」起 uvicorn 却没换 PYTHONPATH/WORKBENCH_REPO_ROOT → health 报的是那棵树、跑的是另一棵。
#    这里三者一起覆盖，并打印 `git rev-parse` 让日志自证。
# 2. 只 source 生产 launcher 会把它的 `cd runtime && exec uvicorn` 一起跑起来 → 抢生产口。这里只取 `export` 行
#    （抄 scripts/v6_deadline_budget_ab.py::sidecar_zsh），保留端口 8792/8793/8795/8799/8801 一律拒绝。
# 3. 端口已被占时 uvicorn 会绑失败但日志晚出 → 先 lsof 拒绝。
#
# 起来之后先做两件事再发题：`lsof -nP -iTCP:57244 -sTCP:LISTEN`（LLM 网关在不在——/api/health 不探它，网关掉线
# 时每题 ~15s 回 gap 模板且 events 里是 HTTP 429）；再单发一题看 draft_chars>0，两臂对照务必串行。
set -euo pipefail
PORT="$1"; REPO="$2"; USERS="$3"; USER_NAME="$4"
LAUNCHER="${WORKBENCH_LAUNCHER:-$HOME/.local/bin/start-finance-workbench}"
PY="${WORKBENCH_PYTHON:-/Users/a77/finance-workspace-private/.venv-workbench/bin/python}"
for reserved in 8792 8793 8795 8799 8801; do
  if [[ "$PORT" == "$reserved" ]]; then print -u2 -- "refused reserved port $PORT"; exit 2; fi
done
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then print -u2 -- "port $PORT already listening"; exit 3; fi
[[ -d "$REPO/intelligence" ]] || { print -u2 -- "no intelligence/ under $REPO"; exit 4; }
[[ -x "$PY" ]] || { print -u2 -- "missing interpreter $PY（别用宿主 python3）"; exit 5; }
set -a
if [[ -f "$LAUNCHER" ]]; then
  . <(grep '^export ' "$LAUNCHER")
fi
set +a
export WORKBENCH_REPO_ROOT="$REPO"
export PYTHONPATH="$REPO"
export FORESIGHT_USERS_DIR="$USERS"
export FORESIGHT_USER="$USER_NAME"
# Episode 默认随 FINANCE_WS 落生产 state，不能只隔离用户目录。
export FORESIGHT_EPISODE_STORE="$USERS/.episodes"
mkdir -p "$USERS"
cd "$REPO"
print -- "sidecar port=$PORT repo=$REPO users=$USERS user=$USER_NAME rev=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
exec "$PY" -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port "$PORT" --log-level info
