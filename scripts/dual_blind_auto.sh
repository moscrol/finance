#!/bin/zsh
# 每日四问自动链（launchd 09:10 调用，周末跳过）。
# 链路：manifest 冻结（DuckDB 截止=库内最新交易日）→ codex / claude 双盲各落一份答卷 JSON
#       → validate 收卷 → index 重建状态总表。
# 双盲纪律：两考生互不可见（prompt 中禁止读对方答卷），对比/裁决归用户。
set -uo pipefail

WORKSPACE="/Users/a77/finance-workspace-private"
export FORESIGHT_USER="linxiaoqi5111"
export FORESIGHT_USERS_DIR="/Users/a77/agent-memory/.foresight"
export KNOWLEDGE_WIKI="/Users/a77/knowledge-base-private/wiki"
export SUBCONSCIOUS_VAULT="/Users/a77/agent-memory"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:/Users/a77/.local/bin:$PATH"

CODEX_BIN="/Applications/Codex.app/Contents/Resources/codex"
CLAUDE_BIN="/Users/a77/.local/bin/claude"
LEDGER="docs/learning/forecast-review-ledger"

D="${1:-$(date +%F)}"
dow=$(date +%u)
if [ "$dow" -gt 5 ]; then
  echo "[$(date '+%F %T')] $D 周末，跳过每日四问"
  exit 0
fi

cd "$WORKSPACE" || exit 1
echo "[$(date '+%F %T')] === 每日四问自动链开始 date=$D ==="

# 视角日 = DuckDB 最新交易日（deltapull 09:00 先跑）
P=$(/usr/bin/python3 -c "import duckdb;c=duckdb.connect('db/market_feature_store.duckdb',read_only=True);print(c.execute('select max(trade_date) from fact_market_daily').fetchone()[0])")
if [ -z "$P" ] || [ "$P" = "None" ]; then
  echo "[$(date '+%F %T')] DuckDB 无交易日数据，退出"
  exit 1
fi
if [ "$P" = "$D" ]; then
  echo "[$(date '+%F %T')] DuckDB 截止日已到当日（$P），视角日异常，退出"
  exit 1
fi
echo "[$(date '+%F %T')] 视角日（DuckDB 截止）=$P"

# 1. manifest 冻结（幂等：已存在则复用，保证双考生同一 manifest_sha）
if [ ! -f "$LEDGER/$D.manifest.json" ]; then
  /usr/bin/python3 scripts/dual_blind_forecast.py manifest --date "$D" --perspective "$P" \
    --kb-root /Users/a77/knowledge-base-private || exit 1
else
  echo "[$(date '+%F %T')] manifest 已存在，复用"
fi
MSHA=$(/usr/bin/python3 -c "import json;print(json.load(open('$LEDGER/$D.manifest.json'))['manifest_sha'])")

prompt_for() {
  local agent="$1"
  cat <<EOF
你是双盲同题答卷的考生「$agent」。今天是 $D，观察视角日 $P（只能用截至 $P 收盘的数据）。

严格按 docs/learning/dual-blind-forecast-template.md 与 docs/learning/forecast-question-templates.md 执行：
1. 只用 $LEDGER/$D.manifest.json 冻结的输入（DuckDB db/market_feature_store.duckdb 截至 $P、知识库 commit）。可用 /usr/bin/python3 + duckdb 查询任何表，但不得使用 $P 之后的数据。
2. 独立完成 §0-§5 答卷，落机器可读 JSON 到 $LEDGER/$D.answer.$agent.json，schema_version "1.0"，agent 填 "$agent"，manifest_sha 填 "$MSHA"。阶段/量能/广度/双红/涨停/新高/核心股全部落数值；主判断一句话；方向排序；标的池 5 只（绑定 §1 字段证据）；thresholds 给 T+1/T+3 强制数值阈值与 falsify 证伪信号；recheck 留空对象。
3. 落盘后跑 /usr/bin/python3 scripts/dual_blind_forecast.py validate $LEDGER/$D.answer.$agent.json，必须 OK，不 OK 就修到 OK。
4. 双盲纪律：禁止读取或参考另一位考生的答卷（$LEDGER/$D.answer.*.json 中非你名下的文件），禁止做对比、批注、裁决。
5. 除答卷 JSON 外不要改动仓库任何文件，不要 git commit。
EOF
}

run_agent() {
  local agent="$1" rc=0
  if [ -f "$LEDGER/$D.answer.$agent.json" ]; then
    echo "[$(date '+%F %T')] $agent 答卷已存在，跳过"
    return 0
  fi
  echo "[$(date '+%F %T')] --- $agent 开始答卷 ---"
  if [ "$agent" = "codex" ]; then
    "$CODEX_BIN" exec --skip-git-repo-check "$(prompt_for codex)" >> "logs/dual-blind.$D.codex.log" 2>&1
    rc=$?
  else
    # claude 网关（open.bigmodel.cn）早高峰常返回 529，未落答卷则间隔重试
    local attempt=1
    while :; do
      "$CLAUDE_BIN" -p "$(prompt_for claude)" \
        --allowedTools "Read,Glob,Grep,Write,Edit,Bash(python3:*),Bash(/usr/bin/python3:*)" \
        >> "logs/dual-blind.$D.claude.log" 2>&1
      rc=$?
      [ -f "$LEDGER/$D.answer.claude.json" ] && { rc=0; break; }
      [ "$attempt" -ge 3 ] && break
      echo "[$(date '+%F %T')] claude 第 $attempt 次未落答卷（rc=$rc，疑似网关高峰），600s 后重试"
      attempt=$((attempt+1))
      sleep 600
    done
  fi
  echo "[$(date '+%F %T')] --- $agent 结束 rc=$rc ---"
  return $rc
}

mkdir -p logs
run_agent codex
run_agent claude

# 3. 收卷校验 + 状态总表
ok=0
for agent in codex claude; do
  f="$LEDGER/$D.answer.$agent.json"
  if [ -f "$f" ]; then
    /usr/bin/python3 scripts/dual_blind_forecast.py validate "$f" && ok=$((ok+1)) \
      || echo "[$(date '+%F %T')] $agent 答卷 validate 失败"
  else
    echo "[$(date '+%F %T')] $agent 未落答卷"
  fi
done
/usr/bin/python3 scripts/dual_blind_forecast.py index --html
echo "[$(date '+%F %T')] === 每日四问自动链结束 通过答卷数=$ok/2 ==="
[ "$ok" -ge 1 ] || exit 1
