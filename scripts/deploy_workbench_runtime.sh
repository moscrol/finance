#!/bin/zsh
# 把仓库的 intelligence/ 部署到生产运行快照，并在事后校验一致性。
#
# 为什么需要这个脚本：生产不是从仓库工作树运行的。launchd 启动器把
# PYTHONPATH 指向 /Users/a77/finance-workspace-runtime（symlink ->
# ~/.finance-runtime/finance-workspace-<id>-standalone），而 git merge 只动仓库，
# **不会**碰快照。于是「合并了」与「生产跑上了」是两件事，中间没有任何自动衔接。
#
# 2026-08-08 实测过这个缺口的代价：health 报 9380b3b9，而快照缺 14 个模块 +
# 整个 intelligence/runtime/ 包，三个已验证的修复在生产里一行都没生效。更糟的是
# 合并会让 health 的 source_revision **前进**——版本号恰好在最可能出错的时刻
# 显得最可信。
#
# 为什么不在服务启动时硬失败（另一个候选方案）：launchd 配置是
# KeepAlive=true + ThrottleInterval=10。启动时 sys.exit 不会「拒绝启动」，
# 会变成每 10 秒重启一次的无限崩溃循环，生产彻底不可用且日志被刷爆。
# 闸门必须放在部署这一侧——这里失败只是「没部署成」，可回退、可重试。
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO="${WORKBENCH_REPO_ROOT:-/Users/a77/finance-workspace-private}"
RUNTIME_LINK="${WORKBENCH_RUNTIME_DIR:-/Users/a77/finance-workspace-runtime}"
SERVICE="${WORKBENCH_SERVICE_LABEL:-com.a77.finance-workbench}"
PYTHON="$REPO/.venv-workbench/bin/python"

die() { print -u2 -- "✗ $1"; exit 1; }

[[ -d "$REPO/intelligence" ]] || die "仓库缺 intelligence/：$REPO"
[[ -x "$PYTHON" ]] || die "缺 venv 解释器：$PYTHON（别用宿主 python3，它没有依赖）"

# symlink 要解析到真实目录再 rsync：直接对 symlink 用 --delete 会删错东西。
SNAP="$(cd "$RUNTIME_LINK" 2>/dev/null && pwd -P)" || die "运行快照不可达：$RUNTIME_LINK"
[[ -d "$SNAP/intelligence" ]] || die "快照缺 intelligence/：$SNAP"

print -- "仓库    : $REPO"
print -- "快照    : $SNAP"
print -- "服务    : $SERVICE"

# 部署前先报告仓库是否干净。不阻断：本仓常有多个 agent 同树作业，未提交改动是
# 常态而非异常。但要说出来——部署的是**工作树当前内容**，不是某个 commit。
if [[ -n "$(git -C "$REPO" status --porcelain 2>/dev/null)" ]]; then
  print -- "revision: $(git -C "$REPO" rev-parse --short HEAD) ⚠️ 工作区有未提交改动（部署的是工作树当前内容）"
else
  print -- "revision: $(git -C "$REPO" rev-parse --short HEAD)（干净）"
fi

# 全量 rsync，不做逐文件补丁。
#
# 逐文件 cp 在这里是陷阱：2026-08-08 那次先补 episode_protocol.py + llm_refine.py
# → 起不来（缺 intelligence/runtime/ 整个包）；补上 runtime/ → 还是起不来
# （缺 services/tool_result_budget.py）；services/ 实际缺 14 个模块。
# 模块重组后「差哪些文件」无法靠读 diff 推断，只能整棵树同步。
# --delete 是必需的：快照里的陈旧模块会被 import 到，留着比缺着更危险。
print -- "\n[1/3] rsync intelligence/ ..."
rsync -a --delete \
  --exclude='__pycache__' --exclude='*.pyc' \
  "$REPO/intelligence/" "$SNAP/intelligence/"
find "$SNAP/intelligence" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
print -- "      done"

# 闸门。rsync 之后两棵树按构造必然一致，所以这里不一致 == 部署真的失败了
# （权限、磁盘满、rsync 被中断、symlink 指向了别处）。此时报错是可行动的，
# 与 readiness 那一格的取舍不同：那里为假可能只是「有人正在改仓库」。
print -- "\n[2/3] 校验加载树与仓库树一致 ..."
# 必须先 cd 到快照，不能只设 PYTHONPATH。
#
# `python - <<PY` 从 stdin 读脚本时 sys.path[0] 是 ''（当前目录），它的优先级
# **高于** PYTHONPATH。脚本原本在仓库根下运行，于是 `intelligence` 从仓库导入，
# 校验退化成「仓库自己跟自己比」——实测首次自部署就撞上这个：
#   loaded_code_root : …/finance-workspace-private/intelligence   ← 不是快照
#   code_matches_repo: True                                       ← 恒真且无意义
# 那次是下面的前置断言（loaded 必须在快照内）把它拦住的，否则这次部署会
# 「成功」，而校验对象从头到尾不是生产真正加载的那棵树。
#
# cd 到快照后 sys.path[0] 解析成快照本身，与 launchd 启动器（`cd "$RUNTIME_DIR"`
# 后再 exec uvicorn）的加载形状一致——校验环境必须复刻生产环境，否则校验的
# 是另一个东西。PYTHONPATH 保留作为双保险。
(cd "$SNAP" && PYTHONPATH="$SNAP" "$PYTHON" - "$REPO" "$SNAP" <<'PY'
import sys
from pathlib import Path

from intelligence.services.runtime_provenance import build_runtime_provenance

repo, snap = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
payload = build_runtime_provenance(repo)
loaded = Path(str(payload["loaded_code_root"])).resolve()
matches = payload["code_matches_repo"]
print(f"      loaded_code_root : {loaded}")
print(f"      loaded_fingerprint: {str(payload['loaded_tree_fingerprint'])[:16]} ({payload['loaded_module_count']} 模块)")
print(f"      repo_fingerprint  : {str(payload['repo_tree_fingerprint'])[:16]} ({payload['repo_module_count']} 模块)")
print(f"      code_matches_repo : {matches}")

# 先断言「加载的确实是快照」，再看两棵树是否一致。顺序不能反。
#
# 少了这条前置断言，本校验会在 PYTHONPATH 没生效时**退化成仓库自己跟自己比**：
# 那种情况恒为 True、稳定通过、且完全无意义——正是这轮要消灭的那类
# 「仪表全绿但没接线」。校验必须先证明自己测的是目标对象。
if not loaded.is_relative_to(snap):
    print(f"      ✗ 加载树不在快照内（PYTHONPATH 未生效？）：{loaded}", file=sys.stderr)
    raise SystemExit(1)
if matches is not True:
    print("      ✗ 两棵树不一致", file=sys.stderr)
    raise SystemExit(1)
raise SystemExit(0)
PY
) || die "一致性校验失败：快照与仓库不一致，未重启服务"
print -- "      ✓ 一致"

print -- "\n[3/3] 重启 $SERVICE ..."
launchctl kickstart -k "gui/$(id -u)/$SERVICE"

# 等服务真的起来再宣布成功。kickstart 是异步的，立刻返回不代表进程健康——
# 直接结束会把「起不来」误报成部署成功。
for i in $(seq 1 30); do
  sleep 2
  if health="$(curl -fsS --max-time 3 localhost:8792/api/health 2>/dev/null)"; then
    print -- "      ✓ 服务已就绪"
    # heredoc 传脚本、argv 传数据，两者不能都走 stdin。
    #
    # 踩过的两个坑，都在这几行里：
    # 1) `-c '...'` 被单引号包裹时，里面再写 \" 是 Python 非法转义
    #    （SyntaxError: unexpected character after line continuation character）。
    # 2) 改成 heredoc 后又写成 `print "$health" | python <<'PY'`：管道与 heredoc
    #    争同一个 stdin，Python 把 health JSON 当脚本读，报
    #    `NameError: name 'true' is not defined`——那个 true 是 JSON 里的字面量。
    # 所以数据只能从 argv 进来。
    "$PYTHON" - "$health" <<'PY'
import json, sys

r = json.loads(sys.argv[1])["runtime"]
rev = str(r.get("source_revision") or "")[:12]
mode = (r.get("continuous_agent") or {}).get("mode")
print(f"      source_revision  : {rev}")
print(f"      loaded_code_root : {r.get('loaded_code_root')}")
print(f"      code_matches_repo: {r.get('code_matches_repo')}")
print(f"      continuous mode  : {mode}")
PY
    print -- "\n✅ 部署完成"
    exit 0
  fi
done
die "服务在 60s 内未就绪，检查 ~/.local/share/finance-workbench/workbench.err.log"
