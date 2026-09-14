#!/bin/zsh
# 全量复盘夜间定时入口（收尾段）。
# 链路：独立 L2 分支 → 同步守卫 → 生成段 → 方法飞轮。
# 同步段**不在本脚本里**：它要做 staging 克隆 / 过闸 / 原子换名，只有 S7 入口走得到。
# 周末直接跳过；非交易日由质检闸门拦截。
#
# 定时拆分（L2 逐笔数据 ~20:30 才到，18:30 跑必空）：
#   nightly-full-review-s7.sh <date>       → 仅同步段（@18:30，走 staging）
#   nightly_full_review.sh finalize <date> → L2 + 生成段 + 方法飞轮（@20:40）
# 两条分开跑、都要跑，别用 && 串：同步失败时 finalize 不启动，L2 会跟着一起丢，
# 而 L2 不依赖同步段产物（工单 #51）。finalize 自己按守卫决定要不要生成。
#
# sync / all 两个 phase 已于 2026-09-12 关闭（绕开 staging 直写生产库），见下方拒绝块。
# 本脚本只接受 finalize；日期缺省今天。
set -uo pipefail

_HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "${_HERE}/ops_python.sh" ]]; then
  source "${_HERE}/ops_python.sh"
elif [[ -f "${_HERE}/lib/ops_python.sh" ]]; then
  source "${_HERE}/lib/ops_python.sh"
elif [[ -f "${_HERE}/../../../scripts/lib/ops_python.sh" ]]; then
  source "${_HERE}/../../../scripts/lib/ops_python.sh"
elif [[ -f /Users/a77/.local/bin/ops_python.sh ]]; then
  source /Users/a77/.local/bin/ops_python.sh
else
  print -u2 -- "missing ops_python.sh"
  exit 1
fi

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_DATA_ROOT:-/Users/a77/finance-workspace-private}"
WORKSPACE="$DATA_ROOT"

# 质检闸门从 CODE_ROOT 取，不是 WORKSPACE（2026-09-12）。
#
# 三处调用原本写裸相对路径 `scripts/check_daily_review_data.py`，而下面会
# `cd "$WORKSPACE"`——WORKSPACE=DATA_ROOT=各 agent 共用的主检出树，它停在任意
# detached 提交上。实测那份检查器还没有 `--plan`，表清单写死在模块级，于是
# plan=local 下必然少 theme_flow / limit_advance 两张它设计上就不抓的表。
# 同一天、同一库、同一 REVIEW_SYNC_PLAN=local：
#   主检出树那份  exit=2 RESULT: INCOMPLETE（卡 fact_theme_flow_daily）
#   CODE_ROOT 那份 exit=0 RESULT: COMPLETE
# 闸门读错树 = 数据齐了也被宣布不完整，20:40 守卫中止，方法飞轮永远轮不到。
# 计划口径不用在这里传：CODE_ROOT 那份的 `--plan` 缺省读 REVIEW_SYNC_PLAN，
# 两个 plist 都已带该变量。
#
# 缺了就停，不回退到 WORKSPACE 那份顶替：顶替会以「看起来合理的理由」判红，
# 比缺闸门更难发现（这正是 09-10~09-11 两天没人察觉的形状）。
REVIEW_CHECKER="$CODE_ROOT/scripts/check_daily_review_data.py"
# 档位缺省在脚本里给全，不靠 plist（plist 的 EnvironmentVariables 只作用于 launchd
# 启动的进程，人在终端手敲拿不到）。要 export：三道质检闸门的 plan 参数都读它。
export REVIEW_SYNC_PLAN="${REVIEW_SYNC_PLAN:-local}"
if [ ! -f "$REVIEW_CHECKER" ]; then
  echo "[$(date '+%F %T')] 质检闸门不在 CODE_ROOT=$CODE_ROOT（运行快照过旧）；" \
       "拒绝用主检出树那份顶替（它不认 --plan，会把 plan=local 判成断档），中止"
  exit 2
fi
export FINANCE_CODE_ROOT="$CODE_ROOT"
export FINANCE_DATA_ROOT="$DATA_ROOT"
export FINANCE_WS="$DATA_ROOT"
# Python 的 -m 会优先把 cwd 放进 sys.path；生成段及其所有子步骤都必须看到
# CODE_ROOT 的包，而 direct script 的 ROOT 仍按脚本文件位置指向 DATA_ROOT。
# PYTHONSAFEPATH（等价于 -P）移除 cwd/script 目录这个隐式优先项，PYTHONPATH
# 再显式钉住代码根；两根职责因此不混：import 读 CODE_ROOT，数据路径读 FINANCE_WS。
export PYTHONSAFEPATH=1
export PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export MARKET_FEATURE_STORE_DB="${MARKET_FEATURE_STORE_DB:-$DATA_ROOT/db/market_feature_store.duckdb}"
export MONEYFLOW_OUTPUT_DIR="${MONEYFLOW_OUTPUT_DIR:-$DATA_ROOT/scripts/moneyflow/outputs}"
export FORESIGHT_USER="linxiaoqi5111"
export FORESIGHT_USERS_DIR="${FORESIGHT_USERS_DIR:-/Users/a77/.local/share/finance-workbench/users}"
export KNOWLEDGE_WIKI="/Users/a77/knowledge-base-private/wiki"
export SUBCONSCIOUS_VAULT="/Users/a77/agent-memory"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:$PATH"

# LOG_DIR 必须在这里就位：下面解析 active 指针时要往它里面写 stderr，而 `set -u` 下
# 引用未赋值变量会让**整条命令**在 shell 层失败（rc=1、输出为空），恰好被 case 归进
# 「1 = 从未配置」，于是静默回退旧协议——指针链一次都没跑过（09-12 跨会话质检实测：
# `zsh:6: LOG_DIR: parameter not set`）。原来的赋值在第 75 行，晚了 20 行。
LOG_DIR="$DATA_ROOT/logs"
mkdir -p "$LOG_DIR"

# 方法飞轮日步（cap07 / 集成 spec I5）的生产三元组：study / 旁路库 / 主库 + 用户显式绑定。
# study 目录是 register 按协议指纹生成的（生产用户目录下），不要手改目录名。
# 绑定优先级：显式环境变量 > active 指针（`method_validation.py activate` 写的）> 内置默认。
# 为什么要有指针：**登记新协议不会切换消费者**。旧写法把协议 id 写死在这里，迁移照方案
# 登记完成后夜跑仍选旧协议（09-12 质检）。指针缺失或指向已封存协议时 `active --print-dir`
# 返回非零且输出为空，这里回退到内置默认，行为与改动前一致。
METHOD_STUDY_DEFAULT="$FORESIGHT_USERS_DIR/$FORESIGHT_USER/method_validation/475597e2e017a2eedd3886700cd41d394d3694eba3487e205b8ddc91723b5a2f"
METHOD_BINDING_ERROR=""
if [ -z "${METHOD_STUDY_DIR:-}" ] && [ -f "$CODE_ROOT/scripts/method_validation.py" ]; then
  # 先探**能力**再谈退出码。守卫 `[ -f … ]` 只证明文件在，不证明它有 active 子命令：
  # 运行快照的 scripts/ 不随 deploy_workbench_runtime.sh 更新（它只 rsync intelligence/），
  # 所以「新 wrapper + 旧 CLI」是链切完成前的常态。旧 CLI 遇到 active 是 argparse
  # `invalid choice` → exit 2，若直接按退出码解释，就会把「这份 CLI 没有 active」误报成
  # 「指针已配置但失效」，还叫人去 activate——那份 CLI 同样没有 activate（09-12 跨会话质检）。
  #
  # 探针要分三种情况，**不能只看 grep 命中与否**：help 跑通且有该命令 / help 跑通但没有 /
  # help 自己就没跑成。第三种若也算「没有该命令」，一次临时故障就会让有效指针在场时
  # 照样回退默认协议且不告警（质检故障注入复现）。故先取 help 的退出码，再判断能力。
  METHOD_HELP_OUT="$("$OPS_PYTHON" "$CODE_ROOT/scripts/method_validation.py" --help 2>&1)"
  METHOD_HELP_RC=$?
  if [ "$METHOD_HELP_RC" -ne 0 ]; then
    METHOD_BINDING_ERROR="无法查询 CLI 能力：--help 退出码 $METHOD_HELP_RC；拒绝回退到内置默认"
    printf '[method-validation] --help 失败 rc=%s，原文：\n%s\n' \
      "$METHOD_HELP_RC" "$METHOD_HELP_OUT" >>"$LOG_DIR/method-validation-daily.log"
  elif printf '%s' "$METHOD_HELP_OUT" | grep -qE '[{,]active[,}]'; then
    # active 的业务退出码（见 scripts/method_validation.py 的 ACTIVE_* 常量）：
    #   0=有效绑定 / 4=从未配置 / 3=配置过但失效。
    # **4 和 3 的正确处置相反**：没配过可以兼容内置默认；配过却坏了（指针损坏、目标缺失、
    # 协议加载失败、指向已封存协议）绝不能静默换回旧实验。
    # 「从未配置」刻意不用 1：Python 未捕获异常正好退 1，用 1 表达业务含义就会把
    # 进程崩溃读成「没配过」而静默回退（质检用 active.json 写成 `[]` 复现）。
    # 因此这里**只认 4**，其余非 0 一律停。
    METHOD_STUDY_DIR="$("$OPS_PYTHON" "$CODE_ROOT/scripts/method_validation.py" active \
      --user "$FORESIGHT_USER" --print-dir 2>>"$LOG_DIR/method-validation-daily.log")"
    case "$?" in
      0) : ;;
      4) METHOD_STUDY_DIR="$METHOD_STUDY_DEFAULT" ;;
      3) METHOD_BINDING_ERROR="active 指针已配置但失效（损坏/目标缺失/协议坏/已封存）；拒绝回退到内置默认" ;;
      *) METHOD_BINDING_ERROR="active 查询异常退出（见 $LOG_DIR/method-validation-daily.log）；拒绝回退到内置默认" ;;
    esac
  else
    # 按「从未配置」走内置默认——链切之前行为与改动前一致；但原因写真话，不复用
    # 「已配置但失效」那句，也不给一个这份 CLI 做不到的补救动作。
    METHOD_STUDY_DIR="$METHOD_STUDY_DEFAULT"
    echo "[method-validation] CODE_ROOT 的 CLI 没有 active 子命令（链切未做，见迁移方案 §4.1）；" \
      "本次按「从未配置」使用内置默认协议 $(basename "$METHOD_STUDY_DEFAULT")" \
      >>"$LOG_DIR/method-validation-daily.log"
  fi
fi
# 兜底只在**没有绑定错误**时生效。否则「拒绝回退到内置默认」就只是下游闸门的一句话,
# 变量本身仍握着默认协议 id, 任何别的消费者或日后重构都会照着它跑（新回归实测）。
if [ -n "$METHOD_BINDING_ERROR" ]; then
  METHOD_STUDY_DIR=""
else
  [ -n "${METHOD_STUDY_DIR:-}" ] || METHOD_STUDY_DIR="$METHOD_STUDY_DEFAULT"
fi
METHOD_LABELS_DB="${METHOD_LABELS_DB:-$DATA_ROOT/db/history_labels.duckdb}"

# 参数：phase (sync|finalize|all) + date。date 缺省今天。
PHASE="all"
D="$(date +%F)"
for arg in "$@"; do
  case "$arg" in
    sync|finalize|all) PHASE="$arg" ;;
    *) D="$arg" ;;
  esac
done

# sync / all 已关闭（2026-09-12）。这两个 phase 直调 run_review_sync.py，而同步器
# 自己**不做** staging——写的就是 MARKET_FEATURE_STORE_DB 指向的那个库，也就是生产库。
# 「克隆 staging → 过闸 → 原子换名」全在 nightly-review-sync-staged.py 里，只有走 S7
# 入口才走得到；实测中途失败会留下改了一半的生产库。
# 上一版只把文档推荐改走 S7，代码路径没关——**改了推荐不等于关了旁路**，
# 而缺省 PHASE 就是 all，`nightly_full_review.sh <日期>` 一句就落回旁路。
#
# 这里拒绝，不在本脚本里套 S7：本脚本下面会持 daily-full-review.lock，
# 而 S7 脚本抢同一把锁，套进来就是自己抢自己的锁（它会看到父进程活着直接 exit 75）。
#
# 放在加锁与任何写入之前，所以拒绝不留锁、不进 ops-health（这是用法错误不是运维故障）。
# launchd 两个 job 都不受影响：sync 走 nightly-full-review-s7.sh，finalize 走本脚本。
if [ "$PHASE" != "finalize" ]; then
  cat >&2 <<EOF
[$(date '+%F %T')] 拒绝执行 phase=$PHASE：这条路径绕开 staging，直写生产库。
  同步段请走 S7 入口（它做克隆 / 过闸 / 原子换名）：
    /bin/zsh /Users/a77/.local/bin/nightly-full-review-s7.sh $D
  收尾另跑一条，**两条都要跑、别用 && 串**（工单 #51）：
    /bin/zsh /Users/a77/.local/bin/nightly_full_review.sh finalize $D
  用 && 串的话，同步一失败 finalize 就根本不启动，L2 跟着一起丢——而 L2 读的是
  逐笔日包，不依赖同步段产物。finalize 自己先跑 L2、再按守卫决定要不要生成，
  所以同步失败时照跑它是安全的：它只跳过生成段，不会拿半拉数据出报告。
  finalize 覆盖 L2 + 生成段 + 方法飞轮；同步段只由 S7 负责，两段各自报退出码。
EOF
  exit 2
fi

# LOG_DIR 已在上面（绑定解析之前）赋值并建目录
LOCK_PARENT="${FINANCE_LOCK_DIR:-$DATA_ROOT/state/locks}"
LOCK_DIR="$LOCK_PARENT/daily-full-review.lock"
mkdir -p "$LOG_DIR" "$LOCK_PARENT"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -z "$old_pid" ] || ! kill -0 "$old_pid" 2>/dev/null; then
    echo "[$(date '+%F %T')] 清理 stale lock pid=$old_pid"
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" || exit 75
  else
    echo "[$(date '+%F %T')] 已有全量复盘/L2 进程在运行，跳过本次 date=$D phase=$PHASE pid=${old_pid:-unknown}"
    exit 75
  fi
fi
echo "$$" > "$LOCK_DIR/pid"
_review_exit() {
  local rc=$?
  rm -rf "$LOCK_DIR"
  ops_health_log "daily-full-review-${PHASE}" "$rc"
}
trap _review_exit EXIT INT TERM

# 按目标日期 $D 判周末（不能用 `date +%u`，那是「今天」的星期——
# 手动跨日补跑时今天可能是周末而 $D 是工作日，会被误跳过）
dow=$(date -j -f "%Y-%m-%d" "$D" +%u)
if [ "$dow" -gt 5 ]; then
  echo "[$(date '+%F %T')] $D 周末，跳过全量复盘"
  exit 0
fi

# 生成段也必须从显式代码根加载，不依赖 WORKSPACE 的 cwd。
# `python -m` 会把当前目录放进 sys.path[0]；因此仅设置 PYTHONPATH 不够——当
# WORKSPACE 本身是另一份检出树时，cwd 仍可能优先加载它的 intelligence。
# 生成段在自身启动前校验代码快照；FINANCE_WS / MARKET_FEATURE_STORE_DB 继续把
# DuckDB、exports、用户态和 episode 指向 DATA_ROOT。L2 分支保持独立，不被这道生成门连坐。
cd "$WORKSPACE" || exit 1
REV=$(git -C "$CODE_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
WORKSPACE_REV=$(git -C "$WORKSPACE" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
echo "[$(date '+%F %T')] === 全量复盘开始 phase=$PHASE date=$D l2_code=$CODE_ROOT l2_rev=$REV workspace=$WORKSPACE workspace_rev=$WORKSPACE_REV db=$MARKET_FEATURE_STORE_DB moneyflow_out=$MONEYFLOW_OUTPUT_DIR ==="

# 失败告警两条腿：内联 osascript 弹窗（零依赖、必达本机）+ notify_ops.py 落盘
# ~/.finance-runtime/alerts.log（--no-desktop 免得重复弹）；告警自身失败不影响退出码
notify() {
  osascript -e "display notification \"$1\" with title \"全量复盘告警\" sound name \"Basso\"" 2>/dev/null || true
  "$OPS_PYTHON" "$WORKSPACE/scripts/notify_ops.py" --no-desktop "$1" 2>/dev/null || true
}

run_moneyflow() {
  L2_LOCK_HELD=1 "$CODE_ROOT/scripts/moneyflow/run_l2_pipeline.sh" "$D"
}

# run_sync() 已删除（2026-09-12）：它直调 run_review_sync.py，绕开 S7 的 staging。
# 同步段只有一条路——nightly-full-review-s7.sh。留着函数就还有人会去调它。

# L2 是独立 DAG 分支：同步段即使失败也会尝试，避免 SW-L1/复盘会故障截断资金流。
# 返回 moneyflow_rc / l2_rc 两个全局变量。
# L2 挂账暂停：state/l2-paused.flag 存在 → 不抓取、L2 门放行（check 脚本读 L2_PAUSED=1
# 会跳过并留痕）。删除 flag 文件即恢复；欠账日期用 run_l2_pipeline.sh 按日回补。
L2_PAUSED_FLAG="$WORKSPACE/state/l2-paused.flag"
run_l2_branch() {
  if [ -f "$L2_PAUSED_FLAG" ]; then
    export L2_PAUSED=1
    echo "[$(date '+%F %T')] L2 已挂账暂停（存在 $L2_PAUSED_FLAG），跳过资金流段与 L2 质量门"
    moneyflow_rc=0
    l2_rc=0
    return 0
  fi
  run_moneyflow
  moneyflow_rc=$?
  if [ "$moneyflow_rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] 资金流段失败 rc=$moneyflow_rc"
    # --fail 仅在实际交易日落 failed；非交易日由 write_to_duckdb.py 内部保护跳过，
    # 避免把历史 complete 或空跑降级成失败（8.6 覆写事故根因）。
    "$OPS_PYTHON" "$CODE_ROOT/scripts/moneyflow/write_to_duckdb.py" --fail "$D" "nightly moneyflow rc=$moneyflow_rc" \
      || echo "[$(date '+%F %T')] L2 失败状态回写未成功"
    notify "❌ 全量复盘 $D 资金流段失败 rc=$moneyflow_rc；日志 logs/daily-full-review.out.log"
  fi
  "$OPS_PYTHON" "$REVIEW_CHECKER" "$D" --phase l2
  l2_rc=$?
  # rc=3：闸门被 duckdb 写锁挡住没跑成，结果未知——与「质量门未通过」是两回事
  if [ "$l2_rc" -eq 3 ]; then
    echo "[$(date '+%F %T')] L2 质量门未能执行：duckdb 写锁占用超重试窗 rc=3，结果未知"
    notify "⚠️ 全量复盘 $D L2 质量门没跑成（duckdb 写锁占用，非质量问题）；等写进程收工后重跑 finalize；日志 logs/daily-full-review.out.log"
  elif [ "$l2_rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] L2 质量门未通过 rc=$l2_rc"
    notify "❌ 全量复盘 $D L2 质量门未通过；日志 logs/daily-full-review.out.log"
  fi
}

# 生成段 + 收尾（KB 时效 / 最终硬门）。前置：sync 与 L2 均已通过。
run_generation_and_finalize() {
  if [ ! -f "$CODE_ROOT/intelligence/__init__.py" ] || [ ! -f "$CODE_ROOT/intelligence/cli.py" ]; then
    echo "[$(date '+%F %T')] 生成段代码根无效：缺少 intelligence 包/CLI（CODE_ROOT=$CODE_ROOT）；拒绝回退到 WORKSPACE=$WORKSPACE" >&2
    notify "❌ 全量复盘 $D 生成段代码根校验失败；未生成报告"
    return 2
  fi

  # 这是生成段的根验收，不只检查文件存在：用和 daily 相同的解释器/安全路径实际
  # import，并把加载位置写入日志。任何 cwd 抢包或代码根失效都在产物生成前失败。
  local generation_import
  generation_import=$("$OPS_PYTHON" -P -c 'import intelligence; print(intelligence.__file__)' 2>&1)
  local import_rc=$?
  echo "[$(date '+%F %T')] generation_import=$generation_import"
  if [ "$import_rc" -ne 0 ] || [[ "$generation_import" != "$CODE_ROOT/intelligence/"* ]] || [[ "$generation_import" == "$WORKSPACE/intelligence/"* ]]; then
    echo "[$(date '+%F %T')] 生成段加载代码根不符：expected CODE_ROOT=$CODE_ROOT actual=$generation_import；拒绝生成" >&2
    notify "❌ 全量复盘 $D 生成段代码根校验失败；未生成报告"
    return 2
  fi

  "$OPS_PYTHON" -P -m intelligence.cli daily --date "$D" --skip-sync --from-step daily-review \
    --summary-json "market_feature_store/exports/$D-daily-workflow-summary.json"
  local rc=$?

  # 幂等兜底：20:05 fidelity 或 daily 步已写出的 kb-ingest-queue 归档进 wiki/raw。
  # 只 receive，不 apply。daily 计划里也有同一步；重复跑按 payload hash 去重。
  local RECEIVE_SH="$WORKSPACE/skills/daily-full-review/scripts/receive_kb_ingest_queue.sh"
  if [ -f "$RECEIVE_SH" ]; then
    /bin/zsh "$RECEIVE_SH" "$D" "$WORKSPACE" "$KNOWLEDGE_WIKI" \
      || echo "[$(date '+%F %T')] kb ingest receive 失败（不阻断）"
  fi

  if [ "$rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] 生成段失败 rc=$rc"
    notify "⚠️ 全量复盘 $D 生成段失败 rc=$rc（同步已完成，可手动重跑 intelligence.cli daily --skip-sync）；日志 logs/daily-full-review.out.log"
    return "$rc"
  fi

  # 双盲答卷回检已退役（2026-08-20）：不再随 finalize 跑 recheck / auto_verdict。
  # 脚本仍留在 scripts/，可手动调用；不要接回夜跑。

  # 知识库证据断更监控（超 7 天未 ingest 新批次则告警；不阻断收尾）
  local kb_msg
  kb_msg=$("$OPS_PYTHON" "$WORKSPACE/scripts/check_kb_freshness.py" --max-age 7)
  if [ $? -eq 2 ]; then
    notify "$kb_msg——研报证据需要补 ingest（PDF 批次）"
  fi

  # 最终硬门：数据/报告/L2 全部通过才允许宣布完成
  "$OPS_PYTHON" "$REVIEW_CHECKER" "$D" --phase all
  local all_rc=$?
  if [ "$all_rc" -eq 3 ]; then
    echo "[$(date '+%F %T')] === 最终硬门未能执行 date=$D（duckdb 写锁占用 rc=3，完整性未知）==="
    notify "⚠️ 全量复盘 $D 最终质量门没跑成（duckdb 写锁占用，非缺数）；等写进程收工后重跑 finalize；日志 logs/daily-full-review.out.log"
    return "$all_rc"
  elif [ "$all_rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] === 全量复盘失败 date=$D all gate rc=$all_rc ==="
    notify "❌ 全量复盘 $D 未通过最终质量门；日志 logs/daily-full-review.out.log"
    return "$all_rc"
  fi

  echo "[$(date '+%F %T')] === 全量复盘完成 date=$D phase=$PHASE l2_code=$CODE_ROOT l2_rev=$REV workspace=$WORKSPACE workspace_rev=$WORKSPACE_REV ==="
  return 0
}

# 方法飞轮日步：只在最终硬门通过后跑（数据到位才动作）。
# 它有自己的条件门（前向起点、15:00、旁路库水位），不满足就写原因与下一次既有执行机会；
# 失败不改变 nightly 退出码（收据带失败原因，留给白天人查），深夜不打断后续段。
skip_method_flywheel() {
  # 数据未完成的夜：如实记录原因与下一次既有执行机会（spec I5），不硬跑 capture。
  echo "[$(date '+%F %T')] method daily 跳过 date=$D 原因=$1 下一次机会=明日 20:40 finalize / 手动 nightly_full_review.sh finalize $D / 到期回检另有 03:50 checkpoint-recheck" \
    >> "$LOG_DIR/method-validation-daily.log"
}

run_method_flywheel() {
  local method_rc=0
  # 脚本从 CODE_ROOT 取，不是 WORKSPACE。WORKSPACE=DATA_ROOT=主检出，那是**数据**仓——
  # 它常年停在别人的任务分支/detached HEAD 上，不保证有任何一个新脚本。method_validation.py
  # 是代码，只在被部署验证过的运行快照里（与本文件 moneyflow 那几条同一个根，也与日志里
  # 报的 l2_code/l2_rev 是同一棵树）。此前写 WORKSPACE 的后果：合进 main 之后飞轮**仍然**
  # 每夜跳过，而跳过原因写着「合入后自动生效」——一条读起来完全合理的假话。
  if [ ! -f "$CODE_ROOT/scripts/method_validation.py" ]; then
    skip_method_flywheel "scripts/method_validation.py 不在 CODE_ROOT=$CODE_ROOT（运行快照早于 cap07/I5，链切后自动生效）"
    return 0
  fi
  if [ -n "$METHOD_BINDING_ERROR" ]; then
    # 绑定失效不是「今晚数据没齐」那类可跳过的情况：继续跑就是拿错协议写新观察。
    skip_method_flywheel "$METHOD_BINDING_ERROR；请 activate 到继任协议后重跑 finalize $D"
    echo "[$(date '+%F %T')] 方法飞轮日步停止：$METHOD_BINDING_ERROR"
    notify "⚠️ 全量复盘 $D 方法飞轮绑定失效：$METHOD_BINDING_ERROR"
    return 0
  fi
  echo "[$(date '+%F %T')] === method daily 开始 date=$D study=$METHOD_STUDY_DIR labels_db=$METHOD_LABELS_DB db=$MARKET_FEATURE_STORE_DB user=$FORESIGHT_USER ===" \
    >> "$LOG_DIR/method-validation-daily.log"
  "$OPS_PYTHON" "$CODE_ROOT/scripts/method_validation.py" daily \
    --study-dir "$METHOD_STUDY_DIR" \
    --labels-db "$METHOD_LABELS_DB" \
    --db-path "$MARKET_FEATURE_STORE_DB" \
    --user "$FORESIGHT_USER" \
    >> "$LOG_DIR/method-validation-daily.log" 2>&1
  method_rc=$?
  if [ "$method_rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] 方法飞轮日步失败 rc=$method_rc；日志 $LOG_DIR/method-validation-daily.log"
    notify "⚠️ 全量复盘 $D 方法飞轮日步失败 rc=$method_rc；日志 logs/method-validation-daily.log"
  else
    echo "[$(date '+%F %T')] 方法飞轮日步完成（日收据见 $LOG_DIR/method-validation-daily.log）"
  fi
  return $method_rc
}

# 只剩 finalize 一个分支：sync / all 在加锁前就被拒（见上），它们绕开 staging。
case "$PHASE" in
  finalize)
    # 工单 #51：L2（资金流 + 质量门）不读同步段的产物，所以它排在同步守卫**之前**——
    # 同步失败不该连坐它。这条不变量原先只钉在已删除的 all) 分支的测试里，生产路径
    # （sync plist + finalize plist 两个独立 job）从未满足过，实际后果是
    # feature_l2_* 两表在 9-10 / 9-11 整整两天没有行。
    # run_l2_branch 自带各失败态的 notify，提前跑不会丢告警。
    run_l2_branch
    l2_branch_rc=0
    if [ "$moneyflow_rc" -ne 0 ] || [ "$l2_rc" -ne 0 ]; then
      l2_branch_rc=1
      echo "[$(date '+%F %T')] L2 段失败 date=$D 资金流 rc=$moneyflow_rc L2门 rc=$l2_rc；继续查同步守卫（生成段另行守门）"
    fi

    # 定时 @20:40。守卫只管生成段：18:30 sync 必须已通过 same-day-gate，否则不生成报告。
    "$OPS_PYTHON" "$REVIEW_CHECKER" "$D" --phase data
    guard_rc=$?
    if [ "$guard_rc" -eq 3 ]; then
      # 闸门被写锁挡住没跑成 ≠ 数据不完整；如实播报，别引导人去补数
      echo "[$(date '+%F %T')] finalize 守卫未能执行：duckdb 写锁占用超重试窗（rc=3），完整性未知，中止生成段（L2 段已跑，rc=$l2_branch_rc）"
      notify "⚠️ 全量复盘 $D finalize 中止：质检闸门被 duckdb 写锁挡住没跑成（非缺数）；等写进程收工后重跑 finalize；日志 logs/daily-full-review.out.log"
      echo "[$(date '+%F %T')] === finalize 中止 date=$D sync 守卫 rc=$guard_rc L2段 rc=$l2_branch_rc ==="
      skip_method_flywheel "finalize 守卫未能执行（duckdb 写锁 rc=3，完整性未知）"
      exit "$guard_rc"
    elif [ "$guard_rc" -ne 0 ]; then
      echo "[$(date '+%F %T')] finalize 守卫未通过：$D 同步段数据不完整（same-day-gate rc=$guard_rc），中止生成段（L2 段已跑，rc=$l2_branch_rc）"
      notify "⚠️ 全量复盘 $D finalize 中止：18:30 sync 段未成功（same-day-gate fail），未生成报告；L2 段已独立跑过（rc=$l2_branch_rc）；需先补跑 sync；日志 logs/daily-full-review.out.log"
      echo "[$(date '+%F %T')] === finalize 中止 date=$D sync 守卫 rc=$guard_rc L2段 rc=$l2_branch_rc ==="
      skip_method_flywheel "same-day-gate rc=$guard_rc 数据不完整"
      exit "$guard_rc"
    fi

    # 守卫过了再结算 L2：L2 失败仍然挡住生成段（与原 all) 一致），退出码不吞它。
    if [ "$l2_branch_rc" -ne 0 ]; then
      echo "[$(date '+%F %T')] === 全量复盘失败 date=$D 资金流 rc=$moneyflow_rc L2门 rc=$l2_rc ==="
      skip_method_flywheel "资金流 rc=$moneyflow_rc / L2 门 rc=$l2_rc"
      exit 1
    fi
    run_generation_and_finalize
    gen_rc=$?
    if [ "$gen_rc" -eq 0 ]; then
      run_method_flywheel || true
    else
      skip_method_flywheel "生成段或最终硬门 rc=$gen_rc"
    fi
    exit "$gen_rc"
    ;;
esac
