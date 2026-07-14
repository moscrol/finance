#!/bin/zsh
# 双盲晨汇/卖方流答卷链（launchd 工作日早间；脚本内再挡周末；缺上游原料当天跳过）。
# 用法：dual_blind_flows.sh <briefing|sellside> [date]
# 链路：复用当日 manifest（09:10 盘面链已冻结）→ codex / claude 各落
#       <date>.answer.<agent>.<source>.json → validate 收卷 → index 重建。
# 冻结口径：与盘面流同一 manifest_sha（DuckDB 截止=前一交易日）；
#   briefing 额外允许读当日晨汇产物；sellside 额外允许读视角日晚间 raw 研报。
# 模型：codex 固定 -m gpt-5.5（勿用 5.6 控额度；勿用 5.4 过弱）。
set -uo pipefail

WORKSPACE="/Users/a77/finance-workspace-private"
export FORESIGHT_USER="linxiaoqi5111"
export FORESIGHT_USERS_DIR="/Users/a77/agent-memory/.foresight"
export KNOWLEDGE_WIKI="/Users/a77/knowledge-base-private/wiki"
export SUBCONSCIOUS_VAULT="/Users/a77/agent-memory"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:/Users/a77/.local/bin:$PATH"

CODEX_BIN="${CODEX_BIN:-/Applications/ChatGPT.app/Contents/Resources/codex}"
CLAUDE_BIN="/Users/a77/.local/bin/claude"
CODEX_DUAL_BLIND_MODEL="${CODEX_DUAL_BLIND_MODEL:-gpt-5.5}"
LEDGER="docs/learning/forecast-review-ledger"

SOURCE="${1:?用法: dual_blind_flows.sh <briefing|sellside> [date]}"
D="${2:-$(date +%F)}"
dow=$(date +%u)
if [ "$dow" -ge 6 ]; then
  echo "[$(date '+%F %T')] $D 周末（dow=$dow），无盘面增量，跳过 $SOURCE 流"
  exit 0
fi
if [ ! -x "$CODEX_BIN" ]; then
  echo "[$(date '+%F %T')] CODEX_BIN 不可执行: $CODEX_BIN"
  exit 1
fi

cd "$WORKSPACE" || exit 1

if [ ! -f "$LEDGER/$D.manifest.json" ]; then
  echo "[$(date '+%F %T')] $D manifest 不存在（盘面链未跑），跳过 $SOURCE 流"
  exit 0
fi
P=$(/usr/bin/python3 -c "import json;print(json.load(open('$LEDGER/$D.manifest.json'))['perspective_date'])")
MSHA=$(/usr/bin/python3 -c "import json;print(json.load(open('$LEDGER/$D.manifest.json'))['manifest_sha'])")

# 上游原料检查
if [ "$SOURCE" = "briefing" ]; then
  # 晨汇标注日期 = 材料日（盘后电话会等，$P 盘后产出），用来预判次日（$D）日内
  MATERIAL="$KNOWLEDGE_WIKI/briefings/$P.md"
  if [ ! -f "$MATERIAL" ]; then
    echo "[$(date '+%F %T')] 视角日 $P 晨汇产物缺（$MATERIAL），跳过 briefing 流"
    exit 0
  fi
  MATERIAL_DESC="视角日盘后晨汇产物 $MATERIAL（三维交叉结果，$P 盘后材料，用于预判 $D 日内）"
  QSECTION="第二节（晨汇事件流）"
  EXTRA="回检窗口 T+1（当日收盘）：兑现形态（直接涨停/高开低走/盘中脉冲/不反应）判断要写进 hypotheses 的 falsify_when。"
elif [ "$SOURCE" = "sellside" ]; then
  raws=$(ls "$KNOWLEDGE_WIKI/raw/sellside/$P-"*.md 2>/dev/null)
  if [ -z "$raws" ]; then
    echo "[$(date '+%F %T')] 视角日 $P 无卖方 raw 研报，跳过 sellside 流"
    exit 0
  fi
  MATERIAL_DESC="视角日晚间卖方 raw 研报：$(echo $raws | tr '\n' ' ')"
  QSECTION="第三节（晚间卖方流）"
  EXTRA="回检窗口 T+3：thresholds 的 t3 与 falsify 必须给可查数的确认/衰竭信号（板块双红、龙头新高、成交额放大到多少）。"
else
  echo "未知 source: $SOURCE"
  exit 1
fi

echo "[$(date '+%F %T')] === $SOURCE 流双盲开始 date=$D 视角=$P ==="

prompt_for() {
  local agent="$1"
  cat <<EOF
你是双盲同题答卷的考生「$agent」。今天是 $D，观察视角日 $P（只能用截至 $P 收盘的行情数据）。本卷是 source=$SOURCE 流。

严格按 docs/learning/dual-blind-forecast-template.md 与 docs/learning/forecast-question-templates.md $QSECTION 执行：
1. 冻结输入 = $LEDGER/$D.manifest.json（DuckDB db/market_feature_store.duckdb 截至 $P）＋ $MATERIAL_DESC。可用 /usr/bin/python3 + duckdb 查询任何表，但不得使用 $P 之后的行情数据。
2. 按 $QSECTION 的问句模板独立作答，同时保持答卷 JSON schema 与盘面流一致（schema_version "1.1"，agent "$agent"，source "$SOURCE"，manifest_sha "$MSHA"；先建 evidence_catalog 登记 L1-L4/source/source_time/field/value/direction；stage_features、标的、threshold_provenance、hypotheses 都引用 catalog id；hypotheses 带 id/category/claim/horizon/confidence/confidence_probability/evidence_as_of/falsify_when；recheck 留空对象）。$EXTRA
3. 落盘到 $LEDGER/$D.answer.$agent.$SOURCE.json，然后跑 /usr/bin/python3 scripts/dual_blind_forecast.py validate $LEDGER/$D.answer.$agent.$SOURCE.json，必须 OK，不 OK 就修到 OK。
4. 双盲纪律：禁止读取或参考另一位考生的任何答卷（$LEDGER/$D.answer.*.json 中非你名下的文件），禁止对比、批注、裁决。
5. 除答卷 JSON 外不要改动仓库任何文件，不要 git commit。
EOF
}

run_agent() {
  local agent="$1" rc=0
  if [ -f "$LEDGER/$D.answer.$agent.$SOURCE.json" ]; then
    echo "[$(date '+%F %T')] $agent $SOURCE 答卷已存在，跳过"
    return 0
  fi
  echo "[$(date '+%F %T')] --- $agent $SOURCE 开始答卷 ---"
  if [ "$agent" = "codex" ]; then
    echo "[$(date '+%F %T')] codex model=$CODEX_DUAL_BLIND_MODEL"
    "$CODEX_BIN" exec -m "$CODEX_DUAL_BLIND_MODEL" --skip-git-repo-check \
      "$(prompt_for codex)" >> "logs/dual-blind.$D.codex.$SOURCE.log" 2>&1
    rc=$?
  else
    # claude 网关（open.bigmodel.cn）早高峰常返回 529，未落答卷则间隔重试
    local attempt=1
    while :; do
      "$CLAUDE_BIN" -p "$(prompt_for claude)" \
        --allowedTools "Read,Glob,Grep,Write,Edit,Bash(python3:*),Bash(/usr/bin/python3:*)" \
        >> "logs/dual-blind.$D.claude.$SOURCE.log" 2>&1
      rc=$?
      [ -f "$LEDGER/$D.answer.claude.$SOURCE.json" ] && { rc=0; break; }
      [ "$attempt" -ge 3 ] && break
      echo "[$(date '+%F %T')] claude $SOURCE 第 $attempt 次未落答卷（rc=$rc，疑似网关高峰），600s 后重试"
      attempt=$((attempt+1))
      sleep 600
    done
  fi
  echo "[$(date '+%F %T')] --- $agent $SOURCE 结束 rc=$rc ---"
  return $rc
}

mkdir -p logs
run_agent codex
run_agent claude

ok=0
for agent in codex claude; do
  f="$LEDGER/$D.answer.$agent.$SOURCE.json"
  if [ -f "$f" ]; then
    /usr/bin/python3 scripts/dual_blind_forecast.py validate "$f" && ok=$((ok+1)) \
      || echo "[$(date '+%F %T')] $agent $SOURCE 答卷 validate 失败"
  else
    echo "[$(date '+%F %T')] $agent $SOURCE 未落答卷"
  fi
done
/usr/bin/python3 scripts/dual_blind_forecast.py index --html
echo "[$(date '+%F %T')] === $SOURCE 流双盲结束 通过答卷数=$ok/2 ==="
