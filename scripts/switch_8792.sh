#!/bin/bash
# 切生产 8792 到一个已过四叶的快照：acceptance-workflow §4「链切五步」的可执行版。
# 用法：bash scripts/switch_8792.sh <完整 40 位 SHA> <切换记录目录>
#
# 它防的失败形状（都在本仓发生过）：
#   1. 快照缺 .venv-workbench：启动器用「快照/.venv-workbench/bin/python」起服务，exit 127 循环重启
#      （2026-10-06 切 f3b97499aaff，交易时段停机约 5 分钟）。
#   2. bootout 是异步的，紧跟 bootstrap 撞 `Bootstrap failed: 5: Input/output error`
#      （2026-09-27，停机约 1.5 分钟）。这里轮询到服务卸载、端口空出再 bootstrap。
#   3. 账本 record 漏 `--port`：这次切换从此判不出归属（账本里已有 16 行这样的）。
#   4. 短 SHA、快照 HEAD 不对或快照脏：切上去的不是验过的那棵树。
# 前置核验任一不过：退出 2，不 bootout、不动链接。限时内没卸载完：退出 3，链接不动。
# 四叶门禁、收据核验、切后三验不在本脚本里，仍按 §3 / §4 做。
set -u
SHA=${1:-}
RECORD_DIR=${2:-}
if [ -z "$SHA" ] || [ -z "$RECORD_DIR" ]; then
  echo "usage: $0 <40-char sha> <record dir>" >&2
  exit 2
fi
LABEL=${WORKBENCH_SERVICE_LABEL:-com.a77.finance-workbench}
PORT=${WORKBENCH_PORT:-8792}
RUNTIME_LINK=${WORKBENCH_RUNTIME_LINK:-$HOME/finance-workspace-runtime}
UNLOAD_WAIT=${WORKBENCH_UNLOAD_WAIT_SECONDS:-60}
FINANCE_WS=${FINANCE_WS:-$HOME/finance-workspace-private}
SNAP=$HOME/.finance-runtime/finance-workspace-${SHA:0:12}
PLIST=$HOME/Library/LaunchAgents/$LABEL.plist
DOMAIN=gui/$(id -u)
mkdir -p "$RECORD_DIR" || exit 2
LOG=$RECORD_DIR/switch.log
abort() {
  echo "ABORT $1" | tee -a "$LOG" >&2
  exit "${2:-2}"
}

[ "${#SHA}" -eq 40 ] || abort "need the full 40-char sha, got '$SHA'"
[ "$(git -C "$SNAP" rev-parse HEAD 2>/dev/null)" = "$SHA" ] || abort "snapshot $SNAP is not at $SHA"
[ -z "$(git -C "$SNAP" status --porcelain)" ] || abort "snapshot $SNAP is dirty"
[ -x "$SNAP/.venv-workbench/bin/python" ] || abort "snapshot has no .venv-workbench/bin/python; the launcher would exit 127"
[ -f "$SNAP/scripts/audit_deploy_ledger.py" ] || abort "snapshot has no scripts/audit_deploy_ledger.py"

echo "prev link: $(readlink "$RUNTIME_LINK")" >> "$LOG"
echo "$(date '+%F %T') bootout $DOMAIN/$LABEL" >> "$LOG"
launchctl bootout "$DOMAIN/$LABEL" >> "$LOG" 2>&1
unloaded=0
for i in $(seq 1 "$UNLOAD_WAIT"); do
  if ! launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 && ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "$(date '+%T') unloaded and port $PORT free after ${i}s" >> "$LOG"
    unloaded=1
    break
  fi
  sleep 1
done
[ "$unloaded" -eq 1 ] || abort "service not unloaded after ${UNLOAD_WAIT}s; link unchanged" 3

ln -sfn "$SNAP" "$RUNTIME_LINK"
echo "new link: $(readlink "$RUNTIME_LINK")" >> "$LOG"
FINANCE_WS=$FINANCE_WS "$SNAP/.venv-workbench/bin/python" "$SNAP/scripts/audit_deploy_ledger.py" record \
  --action switch --rev "$SHA" --snapshot-path "$SNAP" --port "$PORT" \
  --ledger "$HOME/.finance-runtime/deploy-ledger.jsonl" >> "$LOG" 2>&1
echo "ledger_record_exit=$?" >> "$LOG"
rc=1
for attempt in 1 2 3; do
  echo "$(date '+%F %T') bootstrap attempt $attempt" >> "$LOG"
  launchctl bootstrap "$DOMAIN" "$PLIST" >> "$LOG" 2>&1
  rc=$?
  echo "bootstrap_rc=$rc" >> "$LOG"
  [ "$rc" -eq 0 ] && break
  sleep 3
done
echo "SWITCH_DONE rc=$rc $(date '+%F %T')" >> "$LOG"
exit "$rc"
