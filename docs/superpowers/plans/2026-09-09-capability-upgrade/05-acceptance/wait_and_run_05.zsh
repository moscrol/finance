#!/bin/zsh
# 等网关冷却结束（拿到真正的 choices），再串行跑：候选 8798 → 基线 8797；产物在 ~/.finance-runtime/evals/05-acceptance/
set -u
LOG=/Users/a77/.finance-runtime/evals/05-acceptance/wait-and-run.log
WT=/Users/a77/fwp-wt-input-understanding-05
ACC=$WT/docs/superpowers/plans/2026-09-09-capability-upgrade/05-acceptance
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
set -a; . <(grep '^export ' /Users/a77/.local/bin/start-finance-workbench); set +a
print -- "$(date '+%F %T') waiting for gateway cooldown to end" >> $LOG
while true; do
  resp=$(curl -s -m 60 -H "Authorization: Bearer $FORESIGHT_BUILTIN_LLM_API_KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$FORESIGHT_BUILTIN_LLM_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"只回复两个字：收到\"}],\"max_tokens\":8}" \
    "$FORESIGHT_BUILTIN_LLM_BASE_URL/chat/completions")
  if print -r -- "$resp" | grep -q '"choices"'; then
    print -- "$(date '+%F %T') gateway OK" >> $LOG; break
  fi
  print -- "$(date '+%F %T') still cooling: $(print -r -- "$resp" | grep -o 'reset_time[^,}]*' | head -1 | tr -d '\\\"')" >> $LOG
  sleep 120
done
# 候选服务器须在监听；没起就起（启动器自己会再探一次网关）
if ! curl -s -m 5 -o /dev/null http://127.0.0.1:8798/api/health; then
  print -- "$(date '+%F %T') starting candidate server 8798" >> $LOG
  CAP05_JUDGE_BIN=/Users/a77/.grok/downloads/grok-1.0.13-macos-aarch64 CAP05_JUDGE_SANDBOX=off \
    nohup $ACC/start_05_server.sh $WT 8798 /Users/a77/.finance-runtime/cap05-users-candidate /tmp/cap05-candidate-8798.log >> $LOG 2>&1 &
fi
until curl -s -m 5 -o /dev/null http://127.0.0.1:8798/api/health; do sleep 10; done
# 基线服务器 8797 同理
if ! curl -s -m 5 -o /dev/null http://127.0.0.1:8797/api/health; then
  print -- "$(date '+%F %T') starting baseline server 8797" >> $LOG
  CAP05_JUDGE_BIN=/Users/a77/.grok/downloads/grok-1.0.13-macos-aarch64 CAP05_JUDGE_SANDBOX=off \
    nohup $ACC/start_05_server.sh /Users/a77/fwp-wt-input-understanding-05-baseline 8797 /Users/a77/.finance-runtime/cap05-users-baseline /tmp/cap05-baseline-8797.log >> $LOG 2>&1 &
fi
until curl -s -m 5 -o /dev/null http://127.0.0.1:8797/api/health; do sleep 10; done
sleep 60
print -- "$(date '+%F %T') candidate run start" >> $LOG
rm -rf /Users/a77/.finance-runtime/evals/05-acceptance/real-candidate
$PY $ACC/run_05_acceptance.py --base-url http://127.0.0.1:8798 --users-dir /Users/a77/.finance-runtime/cap05-users-candidate \
  --frozen $ACC/frozen_questions.json --out /Users/a77/.finance-runtime/evals/05-acceptance/real-candidate --turn-timeout 900 \
  > /Users/a77/.finance-runtime/evals/05-acceptance/real-candidate.log 2>&1
print -- "$(date '+%F %T') candidate run exit=$?" >> $LOG
print -- "$(date '+%F %T') baseline run start" >> $LOG
rm -rf /Users/a77/.finance-runtime/evals/05-acceptance/real-baseline
$PY $ACC/run_05_acceptance.py --base-url http://127.0.0.1:8797 --users-dir /Users/a77/.finance-runtime/cap05-users-baseline \
  --frozen $ACC/frozen_questions.json --out /Users/a77/.finance-runtime/evals/05-acceptance/real-baseline --turn-timeout 900 \
  > /Users/a77/.finance-runtime/evals/05-acceptance/real-baseline.log 2>&1
print -- "$(date '+%F %T') baseline run exit=$?" >> $LOG
print -- "$(date '+%F %T') ALL DONE" >> $LOG
