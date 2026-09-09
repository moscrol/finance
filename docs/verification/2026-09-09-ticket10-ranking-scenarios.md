# 10 号单 · 排序与情景表达契约 · 验证记录（2026-09-09）

范围合同：`docs/superpowers/plans/2026-09-09-capability-upgrade/10-ranking-scenarios-goal-brief.md`；冻结题与判卷点：同目录 `10-frozen-questions.md`；进度：`progress/10.md`；范围外：`blocked/10.md`。

## 1. 版本边界

| 项 | 值 |
|---|---|
| 基线臂 | `/Users/a77/fwp-wt-ranking-baseline-10`，detached `gitea/main 5eb24515`，`source_dirty=false`，端口 8815 |
| 候选臂 | `/Users/a77/fwp-wt-ranking-scenarios-10`，分支 `feat/ranking-scenarios-10`（基 5eb24515），端口 8816 |
| users 目录 | `~/.local/share/finance-workbench-ticket10/users`（隔离；生产 users 目录未写） |
| 生产 8792 | 未触碰。生产进程 cwd `~/.finance-runtime/finance-workspace-0060da5c1a08`，与两臂都不同 |
| 模型 / 网关 | 沿生产 launcher 的 export（gpt-5.6-sol @ cockpit-cliproxy:57244）；判官 `LLM_JUDGE_BACKEND=grok-cli`，两臂都把不存在的钉死路径换成 `~/.grok/bin/grok`（见 §3） |
| 解释器 | 主树 `.venv-workbench/bin/python` |

## 2. 任务 0 · 现状（[实测]）

- 六题离线路由（`understand_query` + `build_task_frame`）：Q1/Q2/Q4/Q5/Q6 → `theme_analysis`（direct_assessment / chain_mapping / counterpoint；Q5 另带 historical_analogs）；Q3 → `news_impact`，subject 抓成「优先级」。真实 run 里 Q2 落到 `financial_analysis`（subject 华正新材）、Q5 落到 `comparison_analog`、Q1 落到 `stock_deep_dive`——TaskFrame 的 LLM 对齐会改题型，离线路由只是下界。六题在旧版都没有公司矩阵 / 竞争解释 / 改判条件的结构要求。
- 已有同构件：`scenario_tree.py`、`track_contract.py`（表达层契约 + 程序核对 + checkpoints 登记）；`comparison` 算子/题型；`market_analogs`（D8）；`researcher-valuation` 五段契约；`serenity-alpha` 技能桥。
- 生产 `answer.md` 里 Markdown 表格能完整保留（22 个 run 含表格）。

## 3. 基线首跑作废：两处运行环境故障

首跑 14:32–14:37（`/tmp/ticket10/baseline/`）：

| 题 | 结果 | 根因 |
|---|---|---|
| Q1 | 261 s，`outcome.status=partial`，97 条证据、808 字草稿，公开答案 63 字「复核服务不可用」 | `semantic_verifier.exc_class=FileNotFoundError`：`LLM_JUDGE_GROK_BIN=~/.grok/downloads/grok-1.0.5-macos-aarch64` 已被自动更新清掉 |
| Q2/Q6/Q3/Q4 | 10 s 内 `failed`，「模型服务不可用」 | 事件 `model_error: LLM 调用 HTTP 429`，`provider_attempts=2` |
| Q5 | 10 s，`partial`，「现有证据不足」 | 同上，`planning_model_unavailable` |

直接探网关（同凭证，`max_tokens=3`）：

```
HTTP 429  {"error":{"code":"rate_limited","message":"{\"error\":{\"code\":\"model_cooldown\",
\"message\":\"All credentials for model gpt-5.6-sol are cooling down\",\"model\":\"gpt-5.6-sol\",
\"reset_seconds\":4490,\"reset_time\":\"1h14m50s\"}}"}}
```

两处都不是代码问题（基线树是干净的 gitea/main），已记 `blocked/10.md` 交运行底座。

## 4. 配对验收（待填）

驱动：`/tmp/ticket10/paired_batch.sh 8815 8816 /tmp/ticket10/paired`（每题先探网关、冷却则睡到 `reset_seconds+60`；基线→候选交替；Q6 为 Q2 同会话追问；`skill_mode=hybrid` 与 UI 默认一致）。

| 题 | 臂 | run_id | 状态 / 耗时 | 矩阵行 | 改判行 | 竞争解释 | 下一步 | 缺件 | 判官 |
|---|---|---|---|---|---|---|---|---|---|
| （待填） | | | | | | | | | |

## 5. 单测与门禁（待补全量读数）

- 新增 `intelligence/tests/test_ranking_contract.py`：意图门（六题正样本、九条负样本、两对象强词面、自足问法、再排序追问）、契约文本（固定表头、纪律句、legacy/episode 记号隔离）、解析（矩阵/改判/竞争解释/下一步/代码/证据号/缺数计数）、缺件核对与 `missing_outputs` 合并、`is_contract_rewrite_only` 认 ranking id、机械再排序四例（成本条件改排序、反向不触发、未覆盖不变、公司级订单 ↑↑ 上两位）、行序打乱 + 文案改动推导不变、无优先级拒算、收据形状、checkpoints 登记去重 + 渲染 + 终态裁决过滤、episode 规则注入 / 非排序题不变、`expression_slot_binding` FORMAT 回灌、修复说明（跟踪-only 文本逐字节不变）、跨轮上一轮矩阵选取、机械基线注入、`rerank_consistent` 三态。
- 门禁：ruff 全仓通过；`check_unread_fields` 无新增；`layer_audit` ERROR 0；`check_path_literals` 无新增。

## 6. 四项报告（待填）

| 项 | 状态 |
|---|---|
| 已实现 | |
| 已进默认入口 | |
| 真实验收 | |
| 生产生效 | 否（不合 main、不切生产，按合同） |

## 附录 · 验收脚本全文（/tmp 不持久，此处为唯一存档）

### /tmp/ticket10/sidecar.sh

```zsh
#!/bin/zsh
# 10 号单验收用 Workbench 旁路实例：源生产 launcher 的 export（模型/数据配置），
# 只替换代码根、PYTHONPATH、users 目录与端口。不碰 8792，不写生产 users 目录。
# 用法：zsh /tmp/ticket10/sidecar.sh <PORT> <REPO_ROOT> <USERS_DIR>
set -euo pipefail
PORT="$1"; REPO="$2"; USERS="$3"
LAUNCHER="$HOME/.local/bin/start-finance-workbench"
case "$PORT" in 8792|8793|8795|8799|8801) echo "refused reserved port $PORT" >&2; exit 2;; esac
set -a
if [[ -f "$LAUNCHER" ]]; then
  . <(grep '^export ' "$LAUNCHER")
fi
set +a
export WORKBENCH_REPO_ROOT="$REPO"
export PYTHONPATH="$REPO"
export FORESIGHT_USERS_DIR="$USERS"
export FORESIGHT_USER="probe-rank10"
# launcher 把判官二进制钉在带版本号的下载件上，自动更新清掉后判官恒 FileNotFoundError
#（2026-09-09 基线首跑实测）。旁路实例：钉的文件不存在时改用 ~/.grok/bin/grok 符号链接。
if [[ -n "${LLM_JUDGE_GROK_BIN:-}" && ! -x "$LLM_JUDGE_GROK_BIN" && -x "$HOME/.grok/bin/grok" ]]; then
  echo "judge bin $LLM_JUDGE_GROK_BIN missing → using $HOME/.grok/bin/grok" >&2
  export LLM_JUDGE_GROK_BIN="$HOME/.grok/bin/grok"
fi
mkdir -p "$USERS"
cd "$REPO"
exec /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m uvicorn \
  intelligence.api.app:app --host 127.0.0.1 --port "$PORT" --log-level info
```

### /tmp/ticket10/drive.py

```python
#!/usr/bin/env python3
"""10 号单真实入口驱动：建会话 → 发问 → 等 assistant 答案 →（可选）同会话追问。

复用 scripts/workbench_probe.py 钉死的字段名（user / skill_mode），只多一件事：
同一会话第二条消息（催化反转后的再排序必须在上一轮排序之后问）。

用法：
  python3 drive.py --port 8815 --user probe-x --out /tmp/x.json \
      --question "..." [--followup "..."] [--skill-mode auto] [--timeout 1500]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def _call(base, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _assistant_messages(base, cid, user):
    messages = _call(base, f"/api/conversations/{cid}/messages?user={user}")
    items = messages.get("messages", messages) if isinstance(messages, dict) else messages
    return [m for m in items if m.get("role") == "assistant"]


RATE_LIMIT_MARKERS = ("模型服务不可用", "HTTP 429")
RATE_LIMIT_BACKOFF_SECONDS = 120
RATE_LIMIT_ATTEMPTS = 4


def _ask_once(base, cid, user, question, skill_mode, timeout, poll):
    before = len(_assistant_messages(base, cid, user))
    t0 = time.time()
    _call(
        base,
        f"/api/conversations/{cid}/messages",
        {"content": question, "skill_mode": skill_mode, "user": user},
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(poll)
        items = _assistant_messages(base, cid, user)
        if len(items) > before:
            last = items[-1]
            status = last.get("status")
            content = (last.get("content") or "").strip()
            if content and status in (None, "completed", "failed", "partial", "degraded"):
                return {
                    "question": question,
                    "elapsed_seconds": round(time.time() - t0, 1),
                    "status": status,
                    "run_id": last.get("run_id"),
                    "content": content,
                    "raw_keys": sorted(last.keys()),
                }
    return {
        "question": question,
        "elapsed_seconds": round(time.time() - t0, 1),
        "status": "TIMEOUT",
        "run_id": None,
        "content": "",
    }


def _ask(base, cid, user, question, skill_mode, timeout, poll):
    """网关 429（共享 cockpit-cliproxy，生产与其他旁路实例同源）：退避后同会话重发，
    记录每次尝试的 run_id，最终结果取最后一次。"""
    attempts = []
    for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
        result = _ask_once(base, cid, user, question, skill_mode, timeout, poll)
        attempts.append({"attempt": attempt, "status": result["status"], "run_id": result.get("run_id"),
                         "elapsed_seconds": result["elapsed_seconds"]})
        rate_limited = any(marker in result.get("content", "") for marker in RATE_LIMIT_MARKERS)
        if not rate_limited or attempt == RATE_LIMIT_ATTEMPTS:
            result["attempts"] = attempts
            return result
        print(f"  rate-limited (attempt {attempt}), backing off {RATE_LIMIT_BACKOFF_SECONDS}s", flush=True)
        time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
    result["attempts"] = attempts
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--user", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--followup", default=None)
    p.add_argument("--skill-mode", default="auto")
    p.add_argument("--timeout", type=int, default=1500)
    p.add_argument("--poll", type=int, default=10)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    conv = _call(base, "/api/conversations", {"user": a.user, "title": a.question[:24]})
    cid = conv["conversation_id"]
    result = {"conversation_id": cid, "port": a.port, "user": a.user, "turns": []}
    result["turns"].append(_ask(base, cid, a.user, a.question, a.skill_mode, a.timeout, a.poll))
    if a.followup:
        result["turns"].append(_ask(base, cid, a.user, a.followup, a.skill_mode, a.timeout, a.poll))
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    for turn in result["turns"]:
        print(f"[{turn['status']}] {turn['elapsed_seconds']}s run={turn.get('run_id')} chars={len(turn['content'])}")
    return 0 if all(t["status"] != "TIMEOUT" for t in result["turns"]) else 1


if __name__ == "__main__":
    sys.exit(main())
```

### /tmp/ticket10/run_batch.sh

```zsh
#!/bin/zsh
# 10 号单冻结六题批跑：Q6 作为 Q2 同会话的追问（催化反转后的再排序必须接在上一轮排序之后）。
# 用法：zsh /tmp/ticket10/run_batch.sh <PORT> <USER> <OUTDIR>
set -uo pipefail
PORT="$1"; USER_ID="$2"; OUT="$3"
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
DRV=/tmp/ticket10/drive.py
mkdir -p "$OUT"
Q1='液冷板块里英维克、申菱环境、高澜股份、同飞股份谁更值得优先研究？排个序，并说明什么变化会改排序'
Q2='高速覆铜板涨价，生益科技、南亚新材、华正新材谁的利润传导最强？排序并给出兑现节奏'
Q6='如果铜价回落20%且高速CCL涨价落空，生益科技、南亚新材、华正新材的排序会怎么变？观察点怎么改'
Q3='英维克、申菱环境、高澜股份这三家液冷公司，谁的客户集中风险最大？这怎么影响研究优先级'
Q4='PCB里世运电路、兴森科技、东山精密、光华科技，哪家已经被市场定价、哪家还没兑现？按预期差排序'
Q5='这轮液冷和2023年光模块行情在机制上有哪些相似和不同？对英维克、申菱环境、高澜股份的排序有什么影响'
echo "batch start $(date '+%F %T') port=$PORT user=$USER_ID" | tee "$OUT/batch.log"
"$PY" "$DRV" --skill-mode hybrid --port "$PORT" --user "$USER_ID" --out "$OUT/q1.json" --question "$Q1" 2>&1 | tee -a "$OUT/batch.log"
"$PY" "$DRV" --skill-mode hybrid --port "$PORT" --user "$USER_ID" --out "$OUT/q2_q6.json" --question "$Q2" --followup "$Q6" 2>&1 | tee -a "$OUT/batch.log"
"$PY" "$DRV" --skill-mode hybrid --port "$PORT" --user "$USER_ID" --out "$OUT/q3.json" --question "$Q3" 2>&1 | tee -a "$OUT/batch.log"
"$PY" "$DRV" --skill-mode hybrid --port "$PORT" --user "$USER_ID" --out "$OUT/q4.json" --question "$Q4" 2>&1 | tee -a "$OUT/batch.log"
"$PY" "$DRV" --skill-mode hybrid --port "$PORT" --user "$USER_ID" --out "$OUT/q5.json" --question "$Q5" 2>&1 | tee -a "$OUT/batch.log"
echo "batch end $(date '+%F %T')" | tee -a "$OUT/batch.log"
```

### /tmp/ticket10/paired_batch.py

```python
#!/usr/bin/env python3
"""10 号单配对验收驱动：每题先探网关（共享 cockpit-cliproxy 会整模型冷却），再基线臂 → 候选臂。

- 网关 429/model_cooldown：读 reset_seconds，睡到冷却结束再继续（不空转重试烧尝试）。
- 两臂交替按题推进：中途再被冷却，已完成的题仍成对可比。
- Q6 作为 Q2 同会话追问；每臂每题落 JSON（问题、状态、run_id、公开答案、耗时、尝试）。

用法（需先 source launcher 的 export 以拿到网关地址与凭证，见 paired_batch.sh）：
  python3 paired_batch.py --base-port 8815 --cand-port 8816 --out /tmp/ticket10/paired [--only q1,q2]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drive import _ask, _call  # noqa: E402

QUESTIONS = {
    "q1": ("液冷板块里英维克、申菱环境、高澜股份、同飞股份谁更值得优先研究？排个序，并说明什么变化会改排序", None),
    "q2": (
        "高速覆铜板涨价，生益科技、南亚新材、华正新材谁的利润传导最强？排序并给出兑现节奏",
        "如果铜价回落20%且高速CCL涨价落空，生益科技、南亚新材、华正新材的排序会怎么变？观察点怎么改",
    ),
    "q3": ("英维克、申菱环境、高澜股份这三家液冷公司，谁的客户集中风险最大？这怎么影响研究优先级", None),
    "q4": ("PCB里世运电路、兴森科技、东山精密、光华科技，哪家已经被市场定价、哪家还没兑现？按预期差排序", None),
    "q5": ("这轮液冷和2023年光模块行情在机制上有哪些相似和不同？对英维克、申菱环境、高澜股份的排序有什么影响", None),
}


def gateway_state() -> tuple[str, int]:
    """返回 (状态, 建议等待秒数)。状态 ok / cooldown / error。"""
    base = os.environ.get("FORESIGHT_BUILTIN_LLM_BASE_URL") or os.environ.get("LLM_BASE_URL") or ""
    model = os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL") or os.environ.get("LLM_MODEL") or ""
    key = os.environ.get("FORESIGHT_BUILTIN_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not base or not key:
        return "error", 300
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps({"model": model, "messages": [{"role": "user", "content": "回复 ok"}], "max_tokens": 3}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60):
            return "ok", 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        if exc.code == 429:
            found = re.search(r"reset_seconds\\?\"?:\s*(\d+)", body)
            wait = int(found.group(1)) + 60 if found else 300
            return "cooldown", wait
        return "error", 300
    except Exception:
        return "error", 300


def wait_for_gateway(log) -> None:
    while True:
        state, wait = gateway_state()
        if state == "ok":
            return
        log(f"gateway {state}: sleeping {wait}s")
        time.sleep(wait)


def run_arm(port: int, user: str, key: str, question: str, followup: str | None, out_dir: str, log, skill_mode: str) -> dict:
    base = f"http://127.0.0.1:{port}"
    conv = _call(base, "/api/conversations", {"user": user, "title": question[:24]})
    cid = conv["conversation_id"]
    result = {"conversation_id": cid, "port": port, "user": user, "key": key, "turns": []}
    result["turns"].append(_ask(base, cid, user, question, skill_mode, 1500, 10))
    log(f"  {key}@{port} turn1 [{result['turns'][-1]['status']}] {result['turns'][-1]['elapsed_seconds']}s run={result['turns'][-1].get('run_id')} chars={len(result['turns'][-1]['content'])}")
    if followup:
        wait_for_gateway(log)
        result["turns"].append(_ask(base, cid, user, followup, skill_mode, 1500, 10))
        log(f"  {key}@{port} turn2 [{result['turns'][-1]['status']}] {result['turns'][-1]['elapsed_seconds']}s run={result['turns'][-1].get('run_id')} chars={len(result['turns'][-1]['content'])}")
    path = os.path.join(out_dir, f"{key}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-port", type=int, required=True)
    p.add_argument("--cand-port", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--only", default=None, help="逗号分隔题号，如 q1,q2")
    p.add_argument("--skill-mode", default="hybrid")
    p.add_argument("--gap-seconds", type=int, default=45, help="两次 episode 之间的间隔，给网关喘气")
    a = p.parse_args()
    keys = [k.strip() for k in a.only.split(",")] if a.only else list(QUESTIONS)
    for arm in ("base", "cand"):
        os.makedirs(os.path.join(a.out, arm), exist_ok=True)
    log_path = os.path.join(a.out, "paired.log")

    def log(msg: str) -> None:
        line = f"{time.strftime('%F %T')} {msg}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    log(f"paired batch start keys={keys} base={a.base_port} cand={a.cand_port}")
    for key in keys:
        question, followup = QUESTIONS[key]
        for arm, port, user in (("base", a.base_port, "probe-rank10-base"), ("cand", a.cand_port, "probe-rank10-cand")):
            wait_for_gateway(log)
            log(f"{key} {arm}: start")
            try:
                run_arm(port, user, key, question, followup, os.path.join(a.out, arm), log, a.skill_mode)
            except Exception as exc:  # 记录并继续下一臂，不让一题失败拖死整批
                log(f"{key} {arm}: ERROR {type(exc).__name__}: {exc}")
            time.sleep(a.gap_seconds)
    log("paired batch end")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### /tmp/ticket10/paired_batch.sh

```zsh
#!/bin/zsh
# 配对验收批跑：source 生产 launcher 的 export（只为拿网关地址/凭证做冷却探针），再跑 paired_batch.py。
# 用法：zsh /tmp/ticket10/paired_batch.sh <BASE_PORT> <CAND_PORT> <OUTDIR> [only]
set -uo pipefail
set -a
. <(grep '^export ' "$HOME/.local/bin/start-finance-workbench")
set +a
ONLY=${4:-}
ARGS=(--base-port "$1" --cand-port "$2" --out "$3")
[[ -n "$ONLY" ]] && ARGS+=(--only "$ONLY")
exec /Users/a77/finance-workspace-private/.venv-workbench/bin/python /tmp/ticket10/paired_batch.py "${ARGS[@]}"
```
