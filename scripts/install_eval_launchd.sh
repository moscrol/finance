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
NIGHTLY_ONLY=0
DRY_RUN=0
while (( $# )); do
  case "$1" in
    --kickstart) KICKSTART=1 ;;
    --nightly-only) NIGHTLY_ONLY=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      print -- "usage: $0 [--nightly-only] [--dry-run] [--kickstart]"
      print -- "--dry-run: validate and list selected files/jobs; no copies or launchctl calls"
      print -- "--nightly-only: only sync/finalize; shared ops_python.sh must already match"
      exit 0 ;;
    *) print -u2 -- "unknown argument: $1"; exit 2 ;;
  esac
  shift
done
# 预览不能暗藏执行请求；不依赖参数顺序。
if (( DRY_RUN && KICKSTART )); then
  print -u2 -- "--dry-run cannot be combined with --kickstart"
  exit 2
fi

SOURCES=(
  "$REPO/scripts/lib/ops_python.sh"
  "$REPO/scripts/run_fidelity_daily_agent.sh"
  "$REPO/scripts/run_fidelity_forward_acceptance.sh"
  "$REPO/scripts/freeze_daily_pit_snapshot.sh"
  "$REPO/scripts/run_checkpoint_recheck.sh"
  "$REPO/skills/daily-full-review/scripts/nightly_full_review.sh"
  "$REPO/skills/daily-full-review/scripts/nightly_full_review_s7.sh"
)
DESTINATIONS=(
  ops_python.sh
  run_fidelity_daily_agent.sh
  run_fidelity_forward_acceptance.sh
  freeze_daily_pit_snapshot.sh
  run_checkpoint_recheck.sh
  nightly_full_review.sh
  nightly-full-review-s7.sh
)

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

if (( NIGHTLY_ONLY )); then
  # ops_python.sh 也被其余四个任务 source；不同则拒绝，不能以窄发布静默更新它。
  if ! cmp -s "$REPO/scripts/lib/ops_python.sh" "$LOCAL_BIN/ops_python.sh"; then
    print -u2 -- "nightly-only requires an identical installed ops_python.sh; review the shared helper separately"
    exit 2
  fi
  SOURCES=("${SOURCES[6]}" "${SOURCES[7]}")
  DESTINATIONS=("${DESTINATIONS[6]}" "${DESTINATIONS[7]}")
  PLISTS=("${PLISTS[5]}" "${PLISTS[6]}")
  JOBS=("${JOBS[5]}" "${JOBS[6]}")
fi

# 所有选中文件先验完，再开始任何写入；dry-run 同样走预检。
for src in "${SOURCES[@]}"; do
  /bin/zsh -n "$src"
done
for plist in "${PLISTS[@]}"; do
  plutil -lint "$plist" >/dev/null
  expected_label="$(basename "$plist" .plist)"
  if [[ "$(plutil -extract Label raw -o - "$plist")" != "$expected_label" ]]; then
    print -u2 -- "plist Label does not match selected job: $plist"
    exit 2
  fi
  if [[ "$(plutil -extract RunAtLoad raw -o - "$plist")" != "false" ]]; then
    print -u2 -- "scheduled jobs must not run during bootstrap: $plist"
    exit 2
  fi
done
for (( i=1; i<=${#SOURCES[@]}; i++ )); do
  print -- "script ${SOURCES[$i]} -> $LOCAL_BIN/${DESTINATIONS[$i]}"
done
for plist in "${PLISTS[@]}"; do
  print -- "plist $plist -> $AGENTS/$(basename "$plist")"
done
for job in "${JOBS[@]}"; do
  print -- "job $job (kickstart=$KICKSTART)"
done
if (( DRY_RUN )); then
  print -- "dry-run: ${#JOBS[@]} jobs validated; no files copied or services changed"
  exit 0
fi

mkdir -p "$LOCAL_BIN" "$AGENTS" "${HOME}/.finance-runtime/logs"
for (( i=1; i<=${#SOURCES[@]}; i++ )); do
  cp "${SOURCES[$i]}" "$LOCAL_BIN/${DESTINATIONS[$i]}"
  chmod +x "$LOCAL_BIN/${DESTINATIONS[$i]}"
done
for plist in "${PLISTS[@]}"; do
  cp "$plist" "$AGENTS/$(basename "$plist")"
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
