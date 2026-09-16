#!/usr/bin/env bash
# 外部拨测：从 VPS（或任何不在 Mac 上的机器）定时打 Workbench 健康检查。
#
# 为什么要在机器外面拨：Mac 睡眠、隧道断线、launchd 没拉起来——这些故障发生时
# Mac 上的任何自检都跟着一起死，只有外部视角能发现「用户打不开」。
#
# 状态机：连续失败 PROBE_FAIL_THRESHOLD 次才判 down（抗单次抖动）；只在
# up→down / down→up 翻转那一刻各通知一次，不每分钟刷屏。状态落在 PROBE_STATE_FILE。
#
# 用法（VPS crontab，每分钟）：
#   * * * * * PROBE_URL=https://beta.example.com/api/health \
#             PROBE_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx PROBE_WEBHOOK_FORMAT=feishu \
#             /opt/finance/probe_workbench_health.sh >> /var/log/workbench-probe.log 2>&1
#
# 前提：Cloudflare Access 里给 /api/health 建了 Bypass 策略，否则拿到的是 302 登录页，
# 脚本会在阈值后报 down——这本身就是「Bypass 没配」的信号。
# 探 /api/health 是存活；想探「真能服务」换 /api/health/ready（盘后 DuckDB 同步窗口会 503，
# 阈值要相应放宽）。
set -u

URL="${PROBE_URL:?需要 PROBE_URL}"
STATE_FILE="${PROBE_STATE_FILE:-${TMPDIR:-/tmp}/workbench-probe.state}"
WEBHOOK="${PROBE_WEBHOOK_URL:-}"
WEBHOOK_FORMAT="${PROBE_WEBHOOK_FORMAT:-generic}"   # generic | feishu
TIMEOUT="${PROBE_TIMEOUT_SEC:-10}"
FAIL_THRESHOLD="${PROBE_FAIL_THRESHOLD:-3}"

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$URL" 2>/dev/null || echo 000)"
prev_state="$(sed -n '1p' "$STATE_FILE" 2>/dev/null)"
prev_state="${prev_state:-up}"
fails="$(sed -n '2p' "$STATE_FILE" 2>/dev/null)"
fails="${fails:-0}"

if [ "$code" = "200" ]; then
  new_state=up
  fails=0
else
  fails=$((fails + 1))
  if [ "$fails" -ge "$FAIL_THRESHOLD" ]; then
    new_state=down
  else
    new_state="$prev_state"
  fi
fi
printf '%s\n%s\n' "$new_state" "$fails" > "$STATE_FILE"

notify() {
  msg="$1"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $msg"
  [ -n "$WEBHOOK" ] || return 0
  if [ "$WEBHOOK_FORMAT" = "feishu" ]; then
    body="{\"msg_type\":\"text\",\"content\":{\"text\":\"$msg\"}}"
  else
    body="{\"text\":\"$msg\"}"
  fi
  curl -sS --max-time 10 -H 'Content-Type: application/json' -d "$body" "$WEBHOOK" > /dev/null \
    || echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) webhook 发送失败" >&2
}

if [ "$new_state" != "$prev_state" ]; then
  if [ "$new_state" = down ]; then
    notify "Workbench DOWN: $URL http=$code consecutive_failures=$fails"
  else
    notify "Workbench RECOVERED: $URL http=$code"
  fi
fi

[ "$new_state" = up ]
