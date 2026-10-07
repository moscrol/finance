#!/bin/bash
# 切生产 8792 到一个已过四叶的快照：acceptance-workflow §4 的停服、换链、记账、启动切换段。
# 用法：bash scripts/switch_8792.sh <完整 40 位 SHA> <切换记录目录>
#
# 它防的失败形状（都在本仓发生过）：
#   1. 快照缺 .venv-workbench：启动器用「快照/.venv-workbench/bin/python」起服务，exit 127 循环重启
#      （2026-10-06 切 f3b97499aaff，交易时段停机约 5 分钟）。
#   2. bootout 是异步的，紧跟 bootstrap 撞 `Bootstrap failed: 5: Input/output error`
#      （2026-09-27，停机约 1.5 分钟）。这里轮询到服务卸载、端口空出再 bootstrap。
#   3. 账本 record 漏 `--port`：这次切换从此判不出归属。
#   4. 短 SHA、快照 HEAD 不对或快照脏：切上去的不是验过的那棵树。
# 前置核验任一不过：退出 2，不 bootout、不动链接。切换失败尝试恢复旧版本和账本；回滚不完整退出 7。
# 四叶门禁、收据核验、切后三验不在本脚本里，仍按 §3 / §4 做。
set -u
SHA=${1:-}
RECORD_DIR=${2:-}
if [ -z "$SHA" ] || [ -z "$RECORD_DIR" ]; then
  echo "usage: $0 <40-char sha> <record dir>" >&2
  exit 2
fi
LABEL=${WORKBENCH_SERVICE_LABEL:-com.a77.finance-workbench}
[ "${WORKBENCH_PORT:-8792}" = "8792" ] || {
  echo "switch_8792.sh refuses WORKBENCH_PORT other than 8792" >&2
  exit 2
}
PORT=8792
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

[ -x "$(command -v launchctl 2>/dev/null || true)" ] || abort "launchctl is unavailable"
[ -x "$(command -v lsof 2>/dev/null || true)" ] || abort "lsof is unavailable"
[ "${#SHA}" -eq 40 ] || abort "need the full 40-char sha, got '$SHA'"
[ "$(git -C "$SNAP" rev-parse HEAD 2>/dev/null)" = "$SHA" ] || abort "snapshot $SNAP is not at $SHA"
SNAP_STATUS=$(git -C "$SNAP" status --porcelain 2>&1) || abort "cannot inspect snapshot $SNAP: $SNAP_STATUS"
[ -z "$SNAP_STATUS" ] || abort "snapshot $SNAP is dirty"
[ -x "$SNAP/.venv-workbench/bin/python" ] || abort "snapshot has no .venv-workbench/bin/python; the launcher would exit 127"
[ -f "$SNAP/scripts/audit_deploy_ledger.py" ] || abort "snapshot has no scripts/audit_deploy_ledger.py"
[ -L "$RUNTIME_LINK" ] || abort "runtime link $RUNTIME_LINK is missing"
PREV_LINK=$(readlink "$RUNTIME_LINK" 2>/dev/null) || abort "cannot read runtime link $RUNTIME_LINK"
[ -n "$PREV_LINK" ] || abort "runtime link $RUNTIME_LINK is empty"
case "$PREV_LINK" in
  /*) PREV_SNAP=$PREV_LINK ;;
  *) RUNTIME_PARENT=$(cd -P "$(dirname "$RUNTIME_LINK")" && pwd) || abort "cannot resolve runtime link parent"
     PREV_SNAP=$RUNTIME_PARENT/$PREV_LINK ;;
esac
PREV_SHA=$(git -C "$PREV_SNAP" rev-parse HEAD 2>/dev/null) || abort "previous runtime is not a Git snapshot"
PREV_STATUS=$(git -C "$PREV_SNAP" status --porcelain 2>&1) || abort "cannot inspect previous runtime snapshot: $PREV_STATUS"
[ -z "$PREV_STATUS" ] || abort "previous runtime snapshot is dirty"
[ -x "$PREV_SNAP/.venv-workbench/bin/python" ] || abort "previous runtime has no rollback interpreter"
[ -f "$PREV_SNAP/scripts/audit_deploy_ledger.py" ] || abort "previous runtime has no rollback ledger writer"

echo "prev link: $PREV_LINK" >> "$LOG"
echo "prev rev: ${PREV_SHA:-unknown}" >> "$LOG"
echo "switch_script=$0" >> "$LOG"
if command -v shasum >/dev/null 2>&1; then
  echo "switch_script_sha256=$(shasum -a 256 "$0" | awk '{print $1}')" >> "$LOG"
fi
job_is_unloaded() {
  local diagnostic rc
  diagnostic=$(launchctl print "$DOMAIN/$LABEL" 2>&1 >/dev/null)
  rc=$?
  case "$rc" in
    0) return 1 ;;
    1) [ -z "$diagnostic" ] && return 0; return 2 ;;
    113)
      case "$diagnostic" in
        *'Could not find service'*) return 0 ;;
        *) return 2 ;;
      esac ;;
    *) echo "launchctl print failed rc=$rc diagnostic=$diagnostic" >> "$LOG"; return 2 ;;
  esac
}

port_is_free() {
  local diagnostic rc
  diagnostic=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>&1 >/dev/null)
  rc=$?
  case "$rc" in
    0) return 1 ;;
    1) [ -z "$diagnostic" ] && return 0 ;;
  esac
  echo "lsof failed while checking port $PORT rc=$rc diagnostic=$diagnostic" >> "$LOG"
  return 2
}

record_revision() {
  local revision snapshot
  revision=$1
  snapshot=$2
  FINANCE_WS=$FINANCE_WS "$snapshot/.venv-workbench/bin/python" "$snapshot/scripts/audit_deploy_ledger.py" record \
    --action switch --rev "$revision" --snapshot-path "$snapshot" --port "$PORT" \
    --ledger "$HOME/.finance-runtime/deploy-ledger.jsonl" >> "$LOG" 2>&1
  return $?
}

bootstrap_runtime() {
  local rc attempt
  rc=1
  for attempt in 1 2 3; do
    echo "$(date '+%F %T') bootstrap attempt $attempt" >> "$LOG"
    launchctl bootstrap "$DOMAIN" "$PLIST" >> "$LOG" 2>&1
    rc=$?
    echo "bootstrap_rc=$rc" >> "$LOG"
    [ "$rc" -eq 0 ] && return 0
    [ "$attempt" -eq 3 ] || sleep 3
  done
  return "$rc"
}

wait_for_unload() {
  local purpose i job_rc port_rc
  purpose=$1
  for i in $(seq 1 "$UNLOAD_WAIT"); do
    job_is_unloaded
    job_rc=$?
    port_is_free
    port_rc=$?
    [ "$job_rc" -ne 2 ] || { echo "$purpose: launchctl print failed while waiting for unload" >> "$LOG"; return 4; }
    [ "$port_rc" -ne 2 ] || { echo "$purpose: lsof failed while checking port $PORT" >> "$LOG"; return 4; }
    if [ "$job_rc" -eq 0 ] && [ "$port_rc" -eq 0 ]; then
      echo "$(date '+%T') $purpose unloaded and port $PORT free after ${i}s" >> "$LOG"
      return 0
    fi
    sleep 1
  done
  echo "$purpose: service not unloaded after ${UNLOAD_WAIT}s" >> "$LOG"
  return 3
}

restore_previous() {
  local rollback_bootout_rc rollback_link_rc rollback_ledger_rc rollback_bootstrap_rc rollback_wait_rc
  echo "$(date '+%F %T') rollback to $PREV_LINK" >> "$LOG"
  launchctl bootout "$DOMAIN/$LABEL" >> "$LOG" 2>&1
  rollback_bootout_rc=$?
  echo "rollback_bootout_rc=$rollback_bootout_rc" >> "$LOG"
  # A failed bootstrap may leave no job to boot out. The observed job/port
  # state, not a discarded bootout result, decides whether restart is safe.
  wait_for_unload rollback
  rollback_wait_rc=$?
  if [ "$rollback_wait_rc" -ne 0 ]; then
    echo "ROLLBACK_WAIT_FAILED rc=$rollback_wait_rc" >> "$LOG"
    return 1
  fi
  ln -sfn "$PREV_LINK" "$RUNTIME_LINK" >> "$LOG" 2>&1
  rollback_link_rc=$?
  [ "$rollback_link_rc" -eq 0 ] || return 1
  record_revision "$PREV_SHA" "$PREV_SNAP"
  rollback_ledger_rc=$?
  echo "rollback_ledger_exit=$rollback_ledger_rc" >> "$LOG"
  [ "$rollback_ledger_rc" -eq 0 ] || echo "ROLLBACK_LEDGER_FAILED rc=$rollback_ledger_rc" >> "$LOG"
  # Restore service even when accounting fails; still report an incomplete
  # rollback so the operator reconciles the ledger before accepting it.
  bootstrap_runtime
  rollback_bootstrap_rc=$?
  if [ "$rollback_bootstrap_rc" -ne 0 ]; then
    echo "ROLLBACK_BOOTSTRAP_FAILED rc=$rollback_bootstrap_rc" >> "$LOG"
    return 1
  fi
  [ "$rollback_ledger_rc" -eq 0 ] || return 1
  echo "ROLLBACK_DONE rc=0 $(date '+%F %T')" >> "$LOG"
  return 0
}

abort_after_bootout() {
  local message code
  message=$1
  code=$2
  echo "ABORT $message" | tee -a "$LOG" >&2
  if restore_previous; then
    exit "$code"
  fi
  echo "ROLLBACK_FAILED after $message" >> "$LOG"
  exit 7
}

echo "$(date '+%F %T') bootout $DOMAIN/$LABEL" >> "$LOG"
launchctl bootout "$DOMAIN/$LABEL" >> "$LOG" 2>&1
bootout_rc=$?
[ "$bootout_rc" -eq 0 ] || abort_after_bootout "bootout failed with rc=$bootout_rc" 4
wait_for_unload switch
unload_rc=$?
[ "$unload_rc" -eq 0 ] || abort_after_bootout "service/port unload check failed rc=$unload_rc; link unchanged" "$unload_rc"

ln -sfn "$SNAP" "$RUNTIME_LINK" >> "$LOG" 2>&1
link_rc=$?
if [ "$link_rc" -ne 0 ]; then
  abort_after_bootout "cannot point runtime link at $SNAP rc=$link_rc" 5
fi
echo "new link: $(readlink "$RUNTIME_LINK")" >> "$LOG"

record_revision "$SHA" "$SNAP"
ledger_rc=$?
echo "ledger_record_exit=$ledger_rc" >> "$LOG"
if [ "$ledger_rc" -ne 0 ]; then
  abort_after_bootout "ledger record failed rc=$ledger_rc" 5
fi

bootstrap_runtime
bootstrap_rc=$?
if [ "$bootstrap_rc" -eq 0 ]; then
  echo "SWITCH_BOOTSTRAP_DONE rc=0 post_checks=required $(date '+%F %T')" >> "$LOG"
  exit 0
fi

abort_after_bootout "bootstrap failed after three attempts rc=$bootstrap_rc" 6
