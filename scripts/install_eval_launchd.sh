#!/bin/zsh
# 把仓内评估/运维 launchd 源同步到 ~/.local/bin 与 ~/Library/LaunchAgents。
# 不切 8792、不碰 com.a77.finance-workbench。
set -euo pipefail

REPO="${FINANCE_OPS_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"
AGENTS="${HOME}/Library/LaunchAgents"
LOCAL_BIN="${HOME}/.local/bin"
KICKSTART=0
if [[ "${1:-}" == "--kickstart" ]]; then
  KICKSTART=1
fi

mkdir -p "$LOCAL_BIN" "${HOME}/.finance-runtime/logs"

install_script() {
  local src="$1"
  local dest="$2"
  cp "$src" "$dest"
  chmod +x "$dest"
}

install_script "$REPO/scripts/lib/ops_python.sh" "$LOCAL_BIN/ops_python.sh"
install_script "$REPO/scripts/run_fidelity_daily_agent.sh" "$LOCAL_BIN/run_fidelity_daily_agent.sh"
install_script "$REPO/scripts/run_fidelity_forward_acceptance.sh" "$LOCAL_BIN/run_fidelity_forward_acceptance.sh"
install_script "$REPO/scripts/freeze_daily_pit_snapshot.sh" "$LOCAL_BIN/freeze_daily_pit_snapshot.sh"
install_script "$REPO/scripts/run_checkpoint_recheck.sh" "$LOCAL_BIN/run_checkpoint_recheck.sh"
install_script "$REPO/skills/daily-full-review/scripts/nightly_full_review.sh" "$LOCAL_BIN/nightly_full_review.sh"
install_script "$REPO/skills/daily-full-review/scripts/nightly_full_review_s7.sh" "$LOCAL_BIN/nightly-full-review-s7.sh"

PLISTS=(
  "$REPO/intelligence/eval/com.financeworkspace.fidelity-daily-agent.plist"
  "$REPO/intelligence/eval/com.financeworkspace.fidelity-forward-acceptance.plist"
  "$REPO/intelligence/eval/com.financeworkspace.pit-snapshot.plist"
  "$REPO/intelligence/eval/com.financeworkspace.checkpoint-recheck.plist"
  "$REPO/intelligence/dream/com.financeworkspace.daily-full-review-sync.plist"
  "$REPO/intelligence/dream/com.financeworkspace.daily-full-review-finalize.plist"
)

JOBS=(
  com.financeworkspace.fidelity-daily-agent
  com.financeworkspace.fidelity-forward-acceptance
  com.financeworkspace.pit-snapshot
  com.financeworkspace.checkpoint-recheck
  com.financeworkspace.daily-full-review-sync
  com.financeworkspace.daily-full-review-finalize
)

for plist in "${PLISTS[@]}"; do
  dest="$AGENTS/$(basename "$plist")"
  plutil -lint "$plist" >/dev/null
  cp "$plist" "$dest"
done

for job in "${JOBS[@]}"; do
  dest="$AGENTS/${job}.plist"
  launchctl bootout "$DOMAIN/$job" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$dest"
  if (( KICKSTART )); then
    launchctl kickstart -k "$DOMAIN/$job"
  fi
done

print -- "installed ${#JOBS[@]} jobs from $REPO (kickstart=$KICKSTART); 8792 untouched"
