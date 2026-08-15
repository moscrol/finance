"""验收台账：28 道题的进度只从这里生成，不从记忆里写。

三个子命令：
  board   读最近一次 run 记录，打印看板（题 / 期望 / 实测 / 通过 / 失败分类 / 证据路径）
  run     走用户真实点击的那条路径（POST /api/conversations/{id}/messages），落 trace
  freeze  冻结 codex / knevo 的参照答案快照（人工粘贴，禁止被测方自己生成）

设计取舍：
- **不内联评分逻辑。** 判定沿用 intelligence/eval/agent_eval.py 的确定性闸；这里只负责
  「跑真实路径 + 落证据 + 出看板」。分数是可复算的数，不是叙述。
- **trace 落成 JSONL 而不是接 OpenTelemetry。** 当前瓶颈是"用户看不到中间过程"，
  不是"查询不方便"；等题量上规模再换 Langfuse / OTel 这类带 UI 的方案。
- **参照快照必须外部冻结。** 被测方不得重新生成自己的基准，否则考生兼出题人。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from intelligence.eval.acceptance_observations import (
    ObservationArtifactError,
    REFERENCE_ELIGIBILITY_PATH,
    load_observation_artifact,
)
from intelligence.eval.acceptance_axes import (
    AxisState,
    InformationComparison,
    project_axes,
)
from intelligence.eval.acceptance_comparison import (
    ComparisonArtifactError,
    build_comparison_queue,
    load_comparison_queue,
    load_comparison_result,
    write_comparison_queue,
)
from intelligence.eval.acceptance_runs import (
    RunArtifactError,
    load_validated_run,
    select_latest_case_runs,
)
from intelligence.eval.acceptance_verdict import (
    ExperienceState,
    OperationalState,
    VerdictState,
    VERDICT_OVERLAY_PATH,
    compile_case_contract,
    evaluate_case,
    load_verdict_overlay,
)

REPO = Path(__file__).resolve().parents[2]
CASES_PATH = REPO / "intelligence/eval/cases/acceptance_cases.json"
RUNS_DIR = REPO / "intelligence/eval/runs"
SNAPSHOT_DIR = REPO / "intelligence/eval/cases/reference_snapshots"
DEFAULT_BASE = "http://127.0.0.1:8799"
DEFAULT_USER = "linxiaoqi5111"


def load_cases() -> dict[str, Any]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    """相对仓库根显示；路径在仓库外时退回绝对路径而不是抛异常。"""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


@dataclass
class TurnTrace:
    """一次真实回答的完整轨迹 —— 用户不用问我，打开这个文件就能看到发生了什么。

    字段名对齐 runtime 真实返回的形状，别自创：
    - 消息体给 ``invoked_skill_ids`` / ``citations`` / ``degrades``，**没有**
      ``tools_called``。早先版本读 ``tools_called``，于是每条轨迹的工具信息
      恒为空 —— 看板显示 tools=0 却不是真没调工具，是探针探错了地方。
    - 真正能区分「取到证据后回答」和「取不到证据而降级」的是
      ``/api/runs/{run_id}/context`` 的 ``evidence[]``：C1 绑定 6 条证据正常
      作答，A4 绑定 0 条直接降级拒答。这是判空答/假拒答的唯一可靠信号。
    """

    question: str
    answer: str | None = None
    run_id: str | None = None
    invoked_skill_ids: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    degrades: list[str] = field(default_factory=list)
    evidence_bound: int = 0
    evidence: list[dict[str, Any]] = field(default_factory=list)
    trace_steps: list[str] = field(default_factory=list)
    synthesis_diagnostic: dict[str, Any] = field(default_factory=dict)
    # 结构化判缺（哪一格 output 缺、成因码是什么）。此前只有 ``gaps`` 里那句
    # 「最终回答未完成任务契约」——11 个 turn 命中过它，没有一个能回答缺哪一格。
    fulfillment: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    status: str = "unknown"
    error: str | None = None
    # --- 运行态三元组（R-20260815-01）---------------------------------------
    # ``evidence_bound`` 是**交付层**计数，它把至少四种互不相同的运行态压成同一个
    # ``0``：没执行 / 没取到 / 取到没合成 / 合成了但绑定被判缺而丢弃。2026-08-14
    # 那份诊断正是被这个同码读数带偏，把 9 个 ``Connection refused`` 读成了业务
    # 行为。下面三个字段把「取回多少」「绑上多少」「交付多少」拆开各自可见。
    #
    # ⚠️ 这三个字段来自 episode 产物（``continuous-episode.json``），不是公共 API
    # ——公共 ``/trace`` 是脱敏展示投影（step_id 为哈希、name 只有 research/
    # understanding），拿不到结构化判据。取不到产物时**不猜**：三个字段留 None、
    # ``execution_state`` 落 ``undetermined``、``execution_state_source`` 记
    # ``api_only``，让读者知道这一格没有证据支撑，而不是看到一个像样的默认值。
    evidence_retrieved: int | None = None
    bindings_count: int | None = None
    outputs_missing: int | None = None
    outputs_fulfilled: int | None = None
    execution_state: str = "unknown"
    execution_state_source: str = "unknown"
    # R-20260815-07：逐格形状（output_id → clean / gap_zeroed / no_hash）。
    # 混合形的 turn 只靠 `execution_state` 一个标量表达不了，必须留明细。
    slot_shapes: dict[str, str] = field(default_factory=dict)
    slots_gap_zeroed: int | None = None
    slots_no_hash: int | None = None


@dataclass
class CaseRun:
    case_id: str
    tier: str
    turns: list[TurnTrace] = field(default_factory=list)
    blocked_reason: str | None = None


# --------------------------------------------------------------------------- #
# run —— 走用户真实点击的那条路径
# --------------------------------------------------------------------------- #
def _post(url: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _get(url: str, timeout: float = 30.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def preflight(base: str) -> tuple[bool, str]:
    """部署接缝前置检查。跑不过就不许报进度 —— 这四道缝各自坑过一次。

    注意 /api/llm/config 当前恒定阻塞约 6s（疑似 Keychain 查询），所以 timeout
    必须给到 10s 以上，否则前置检查会因自身超时而误报『不可达』。
    """
    try:
        health = _get(f"{base}/api/health", timeout=10)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"服务不可达: {exc}"

    runtime = health.get("runtime") or {}
    agent_runtime = runtime.get("agent_runtime") or {}
    deps = health.get("dependencies") or {}
    revision = runtime.get("source_revision") or ""

    failed: list[str] = []
    if health.get("status") != "healthy":
        failed.append(f"status={health.get('status')}")
    if not runtime.get("finance_root"):
        failed.append("finance_root 缺失")
    if not revision:
        failed.append("source_revision 缺失")
    for dep in ("repo_root", "knowledge_wiki", "relations", "market_snapshot"):
        if deps.get(dep) is False:
            failed.append(f"依赖 {dep} 不可用")
    if agent_runtime.get("ready") is False:
        failed.append(
            f"agent_runtime 未就绪（backend={agent_runtime.get('backend')}, "
            f"reason={agent_runtime.get('reason')}）"
        )

    try:
        cfg = _get(f"{base}/api/llm/config", timeout=15)
        if cfg.get("ready") is False:
            failed.append("llm_config.ready=false（BYOK 凭据未就绪）")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        failed.append(f"llm/config 不可达: {type(exc).__name__}")

    try:
        users_dir = try_resolve_episode_users_dir(
            health, os.environ.get("FORESIGHT_USERS_DIR")
        )
    except UsersDirMismatch as exc:
        failed.append(str(exc))
        users_dir = None

    if failed:
        return False, "; ".join(failed)
    if users_dir is not None:
        os.environ["FORESIGHT_USERS_DIR"] = str(users_dir)
        users_note = f" users_dir={users_dir}"
    else:
        users_note = " users_dir=<unset>"
    return (
        True,
        f"revision={revision[:8]} backend={agent_runtime.get('backend')}"
        f"{users_note}",
    )


class UsersDirMismatch(RuntimeError):
    """users 目录错配。静默落 ``undetermined``/``api_only`` 会产出「看起来正常」
    的五态——这正是 Round 3 开批前拦下的陷阱（R-20260815-08）。
    """


def resolve_episode_users_dir(
    health: Mapping[str, Any] | None,
    env: str | None,
) -> Path:
    """服务端 users 目录优先；与 ``FORESIGHT_USERS_DIR`` 不一致则响亮失败。

    ``/api/health`` 的 ``runtime.users_dir`` 在未部署新字段时可能缺失——此时
    退回 env，但 ``require_episode_if_expected`` 仍会在 completed 非澄清轮
    找不到 episode 时失败，避免整批静默降级。
    """

    runtime = (health or {}).get("runtime") if isinstance(health, Mapping) else {}
    runtime = runtime if isinstance(runtime, Mapping) else {}
    raw_server = runtime.get("users_dir")
    if not raw_server and isinstance(health, Mapping):
        raw_server = health.get("users_dir")
    server = (
        Path(str(raw_server)).expanduser().resolve() if raw_server else None
    )
    env_path = Path(env).expanduser().resolve() if env and str(env).strip() else None
    if server is not None and env_path is not None and server != env_path:
        raise UsersDirMismatch(
            f"FORESIGHT_USERS_DIR={env_path} 与 /api/health "
            f"users_dir={server} 不一致"
        )
    if server is not None:
        return server
    if env_path is not None:
        return env_path
    raise UsersDirMismatch(
        "无法解析 users 目录：/api/health 无 users_dir 且 FORESIGHT_USERS_DIR 未设"
    )


def try_resolve_episode_users_dir(
    health: Mapping[str, Any] | None,
    env: str | None,
) -> Path | None:
    """preflight 用：两边都缺时不挡（8792 尚未暴露字段）；不一致仍响亮失败。"""

    runtime = (health or {}).get("runtime") if isinstance(health, Mapping) else {}
    runtime = runtime if isinstance(runtime, Mapping) else {}
    raw_server = runtime.get("users_dir")
    if not raw_server and isinstance(health, Mapping):
        raw_server = health.get("users_dir")
    if not raw_server and not (env and str(env).strip()):
        return None
    return resolve_episode_users_dir(health, env)


def episode_artifact_expected(trace: TurnTrace) -> bool:
    """澄清轮合法无 episode；其它 completed 长跑必须能读到产物。"""

    if not trace.run_id:
        return False
    if trace.status not in {"completed", "degraded"}:
        return False
    if not trace.gaps and len(trace.trace_steps) <= 6:
        return False
    return True


_episode_hits_this_run = 0


def reset_episode_hit_counter() -> None:
    """每开一批清零。已有命中后再缺产物，是单题缺口，不是目录错配。"""

    global _episode_hits_this_run
    _episode_hits_this_run = 0


def require_episode_if_expected(
    trace: TurnTrace, facts: Mapping[str, Any] | None
) -> None:
    """错目录会让**整批**读不到 episode。本批已读到过产物后再缺，只标该题。

    2026-08-15 批 #2 第一次开跑：C4 `run_20260815_105037_639945` 目录正确、
    无 `continuous-episode.json`。当时整批中止、21 题已读产物作废——那是量具
    误杀，不是 R-08 要拦的静默降级。
    """

    global _episode_hits_this_run
    if facts is not None:
        _episode_hits_this_run += 1
        return
    if not episode_artifact_expected(trace):
        return
    if _episode_hits_this_run > 0:
        return
    raise UsersDirMismatch(
        f"run {trace.run_id} 在 "
        f"{os.environ.get('FORESIGHT_USERS_DIR') or '<unset>'} "
        "找不到 continuous-episode.json（completed 且非澄清轮，"
        "且本批尚未读到任何 episode）。这是 users 目录错配，不是五态业务读数。"
    )


#: 运行态冻结枚举（R-20260815-01）。**不要新增值而不同步更新判定函数与看板**——
#: 这张表的价值全在「同一个读数只对应一种成因」，多一个语义重叠的值就退回同码。
EXECUTION_STATES = (
    "not_run",  # 基础设施失败：服务不可达/超时，题目根本没跑（R-02：不进分母）
    "clarification",  # 正常澄清轮：反问用户，无 gaps、无 episode 产物（非失败）
    "no_evidence",  # 跑了但一条证据都没取到（检索侧）
    "retrieved_unsynthesized",  # 取到证据但没合成出 draft / 无绑定（合成侧）
    # R-20260815-07：原 `bound_but_dropped` 细分为下面两态。二者都是「绑定了却没
    # 交付」，但**成因相反、处置也相反**：
    #   `gap_zeroed` —— 该格有 `evidence_hashes` 却因附带 gap 被整格判缺。证据是
    #                   真的存在却被扣住，属可修缺陷（轨道 A 的 F-001/R-001 面）。
    #   `no_hash`    —— 该格本就没有任何可绑证据。判缺是**正确行为**，不该"修"。
    # 混在一起会让「该修的」和「本就对的」共用一个读数——这正是 `evidence_bound`
    # 同码问题在下一层的复发。
    "gap_zeroed",  # 至少一格「有哈希 + 带 gap」被零化（证据被扣住）
    "no_hash",  # 被判缺的格全部零哈希（真缺口，判缺正确）
    "delivered",  # 有证据交付到验收可见面
    "undetermined",  # 缺 episode 产物，无法判定——不许猜
)

#: ``not_run`` 是部署接缝失败，不是题目失败。R-20260815-02：把它计进质量分母会
#: 稀释读数——2026-08-13 那份 28 题产物里 C 组 9 题全是 ``Connection refused``，
#: 被当成「C 组 90% 证据为零」写进了结论。
_STATES_OUT_OF_QUALITY_DENOMINATOR = frozenset({"not_run"})


def counts_toward_quality(turn: Mapping[str, Any]) -> bool:
    """该 turn 是否计入业务质量分母。"""

    state = str(turn.get("execution_state") or "")
    if state in _STATES_OUT_OF_QUALITY_DENOMINATOR:
        return False
    # 旧产物没有 execution_state，退回既有判据，保持向后可读
    if not state or state == "unknown":
        return not (
            turn.get("status") == "error" and not (turn.get("trace_steps") or [])
        )
    return True


def summarize_execution_states(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """按运行态汇总，并给出剔除 `not_run` 后的质量分母。

    R-20260815-02 的落点：`quality_denominator` 是**分母本身**，不是又一个提示。
    2026-08-13 那份产物里 C 组 10 题有 9 题是 `Connection refused`，旧口径按
    10 做分母，于是「C 组 90% 证据为零」被当成业务结论写进了诊断。
    """

    tally: dict[str, int] = {}
    source_tally: dict[str, int] = {}
    denominator = 0
    excluded: list[str] = []
    for case in cases:
        turns = case.get("turns") or []
        if not turns:
            continue
        head = turns[0]
        state = str(head.get("execution_state") or "unknown")
        tally[state] = tally.get(state, 0) + 1
        # `execution_state_source` 必须跟着 tally 一起报：只有
        # `episode_artifact` 那部分是有结构化产物支撑的，`api_only` 那部分
        # 只能到 not_run/clarification/undetermined 三档。不报来源，读者无法
        # 判断这张表里有多少格其实是「没证据」而非「测出来是这样」。
        source = str(head.get("execution_state_source") or "unknown")
        source_tally[source] = source_tally.get(source, 0) + 1
        if counts_toward_quality(head):
            denominator += 1
        else:
            excluded.append(str(case.get("case_id") or "?"))
    return {
        "execution_state_tally": dict(sorted(tally.items())),
        "execution_state_source_tally": dict(sorted(source_tally.items())),
        "quality_denominator": denominator,
        "excluded_from_denominator": excluded,
    }


def _read_episode_facts(
    run_id: str,
    user: str | None,
    *,
    users_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    """从已落盘的 episode 产物读结构化判据。

    只读、不请求、不改任何运行时状态。定位方式与 runtime 的存储约定一致
    （``$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/continuous-episode.json``）；
    读不到就返回 None 交由调用方标注 ``undetermined``，绝不构造默认值。
    错目录的响亮失败在 ``require_episode_if_expected``，不在这里猜一个态。
    """

    resolved = users_dir if users_dir is not None else os.environ.get("FORESIGHT_USERS_DIR")
    if not resolved or not run_id:
        return None
    root = Path(resolved)
    candidates = [root / user / "runs" / run_id] if user else []
    candidates.extend(sorted(root.glob(f"*/runs/{run_id}")))
    for run_dir in candidates:
        path = run_dir / "continuous-episode.json"
        if not path.is_file():
            continue
        try:
            episode = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(episode, dict):
            return None
        outcome = episode.get("outcome")
        outcome = outcome if isinstance(outcome, dict) else {}
        structural = episode.get("structural_verifier")
        structural = structural if isinstance(structural, dict) else {}
        completion = structural.get("completion")
        completion = completion if isinstance(completion, dict) else {}
        outputs = completion.get("outputs")
        outputs = outputs if isinstance(outputs, list) else []
        statuses = [
            str(item.get("status"))
            for item in outputs
            if isinstance(item, Mapping)
        ]
        slot_shapes: dict[str, str] = {}
        for binding in outcome.get("bindings") or []:
            if not isinstance(binding, Mapping):
                continue
            output_id = str(binding.get("output_id") or "")
            if not output_id:
                continue
            hashes = binding.get("evidence_hashes") or []
            if not binding.get("gap"):
                slot_shapes[output_id] = "clean"
            elif len(hashes) > 0:
                slot_shapes[output_id] = "gap_zeroed"
            else:
                slot_shapes[output_id] = "no_hash"
        return {
            "evidence_retrieved": len(outcome.get("evidence") or []),
            "bindings_count": len(outcome.get("bindings") or []),
            "draft_chars": len(str(outcome.get("draft") or "")),
            "outputs_missing": sum(1 for s in statuses if s == "missing"),
            "outputs_fulfilled": sum(1 for s in statuses if s == "fulfilled"),
            # R-20260815-07：逐格形状。**必须逐格记而不是只给 turn 级标签**——
            # B7 与 B1@RunB 都是混合形（同一 turn 内既有滑档格又有真缺口格），
            # 只给一个 turn 级值会把其中一种抹掉。
            "slot_shapes": slot_shapes,
            "slots_gap_zeroed": sum(1 for s in slot_shapes.values() if s == "gap_zeroed"),
            "slots_no_hash": sum(1 for s in slot_shapes.values() if s == "no_hash"),
        }
    return None


def _classify_execution_state(
    trace: TurnTrace, facts: Mapping[str, Any] | None
) -> str:
    """按结构化事实定运行态。**不读答案正文**——那是给用户看的话术，不是观测。"""

    if trace.status in {"error", "timeout"} and not trace.trace_steps:
        return "not_run"
    if trace.evidence_bound > 0:
        return "delivered"
    if facts is None:
        # 没有 episode 产物：可能是澄清轮（B6 形状：秒级返回、无 gaps、步数极少），
        # 也可能只是产物读不到。两者不可混为一谈。
        if trace.status == "completed" and not trace.gaps and len(trace.trace_steps) <= 6:
            return "clarification"
        return "undetermined"
    if not facts.get("evidence_retrieved"):
        return "no_evidence"
    if not facts.get("draft_chars") or not facts.get("bindings_count"):
        return "retrieved_unsynthesized"
    # 混合形（同一 turn 内两种格都有）按 `gap_zeroed` 归类：只要存在一格证据被
    # 无谓扣住，这个 turn 就有可修的东西，这是行动意义上更强的信号。逐格明细在
    # `slot_shapes` 里不丢。
    if facts.get("slots_gap_zeroed"):
        return "gap_zeroed"
    return "no_hash"


def _fill_run_detail(base: str, trace: TurnTrace, *, user: str | None = None) -> None:
    """补 run 级证据绑定与步骤。取不到不算失败 —— 答案本身已经拿到了。"""
    if not trace.run_id:
        return
    user_query = f"?{urllib.parse.urlencode({'user': user})}" if user else ""
    try:
        ctx = _get(
            f"{base}/api/runs/{trace.run_id}/context{user_query}",
            timeout=15,
        )
    except (urllib.error.URLError, TimeoutError, OSError):
        ctx = {}
    evidence = ctx.get("evidence") or []
    trace.evidence = list(evidence)
    trace.evidence_bound = sum(
        1 for e in evidence if isinstance(e, dict) and e.get("status") == "hit"
    )
    trace.gaps = list(ctx.get("gaps") or [])
    try:
        steps = _get(
            f"{base}/api/runs/{trace.run_id}/trace{user_query}",
            timeout=15,
        )
    except (urllib.error.URLError, TimeoutError, OSError):
        steps = []
    if isinstance(steps, list):
        trace.trace_steps = [
            str(s.get("name")) for s in steps if isinstance(s, dict) and s.get("name")
        ]
        trace.synthesis_diagnostic = _capture_synthesis_diagnostic(steps)
        trace.fulfillment = _capture_fulfillment(steps)
    facts = _read_episode_facts(trace.run_id, user)
    require_episode_if_expected(trace, facts)
    if facts is not None:
        trace.evidence_retrieved = int(facts["evidence_retrieved"])
        trace.bindings_count = int(facts["bindings_count"])
        trace.outputs_missing = int(facts["outputs_missing"])
        trace.outputs_fulfilled = int(facts["outputs_fulfilled"])
        trace.slot_shapes = dict(facts["slot_shapes"])
        trace.slots_gap_zeroed = int(facts["slots_gap_zeroed"])
        trace.slots_no_hash = int(facts["slots_no_hash"])
        trace.execution_state_source = "episode_artifact"
    else:
        trace.execution_state_source = "api_only"
    trace.execution_state = _classify_execution_state(trace, facts)


_SYNTHESIS_DIAGNOSTIC_FIELDS = (
    "state",
    "reason_code",
    "detail",
    "prepared_message_count",
    "candidate_claim_count",
    "bound_claim_count",
    # 少了这两个，「合成失败」和「合成没时间跑」在验收产物里长得一模一样，
    # 只能靠读代码猜是哪一段吃掉了预算——2026-08-02 那批就是这么卡住的。
    "shadow_status",
    "phases",
)
_SYNTHESIS_DIAGNOSTIC_STATES = {
    # 四态口径：full pass(accepted) / 放行未核验(released_unverified) /
    # 模板降级(rejected) / 没进合成(not_prepared)。二分成 accepted-rejected
    # 会把「没人审但放行了」算进健康数。
    "released_unverified",
    "not_requested",
    "not_prepared",
    "attempted",
    "accepted",
    "rejected",
    "failed",
}


def _capture_synthesis_diagnostic(steps: list[Any]) -> dict[str, Any]:
    """Retain only the bounded diagnostic already exposed by the public trace."""

    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        raw = step.get("diagnostic")
        if not isinstance(raw, dict):
            continue
        state = raw.get("state")
        reason_code = raw.get("reason_code")
        if state not in _SYNTHESIS_DIAGNOSTIC_STATES or not isinstance(
            reason_code, str
        ):
            continue
        diagnostic = {
            key: raw[key]
            for key in _SYNTHESIS_DIAGNOSTIC_FIELDS
            if key in raw
        }
        diagnostic["detail"] = str(diagnostic.get("detail") or "")[:200]
        return diagnostic
    return {}


def _capture_fulfillment(steps: list[Any]) -> dict[str, Any]:
    """取最后一次判缺投影（含修复轮）。

    倒序取第一条：修复轮 ``task_fulfillment_repair`` 排在原始判缺之后，
    验收要看的是**终态**契约完成情况，不是修复前那份。
    """

    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        raw = step.get("fulfillment")
        if not isinstance(raw, dict):
            continue
        status = raw.get("status")
        items = raw.get("items")
        if not isinstance(status, str) or not isinstance(items, list):
            continue
        return raw
    return {}


def ask_once(base: str, user: str, question: str, timeout: float) -> TurnTrace:
    """真实提问一次并轮询到终态。返回可复核的轨迹。"""
    trace = TurnTrace(question=question)
    started = time.monotonic()
    try:
        conv = _post(f"{base}/api/conversations", {"title": "acceptance", "user": user})
        conv_id = conv.get("conversation_id") or conv.get("id")
        if not conv_id:
            trace.status = "error"
            trace.error = f"未拿到 conversation_id: {conv}"
            return trace
        _post(
            f"{base}/api/conversations/{conv_id}/messages",
            {"content": question, "skill_mode": "auto", "user": user},
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(2.0)
            msgs = _get(f"{base}/api/conversations/{conv_id}/messages?user={user}")
            items = msgs if isinstance(msgs, list) else msgs.get("messages", [])
            assistant = [m for m in items if m.get("role") == "assistant"]
            if not assistant:
                continue
            last = assistant[-1]
            if last.get("status") in {"pending", "running", None}:
                continue
            trace.answer = last.get("content")
            trace.status = last.get("status") or "unknown"
            trace.run_id = last.get("run_id")
            trace.invoked_skill_ids = list(last.get("invoked_skill_ids") or [])
            trace.citations = list(last.get("citations") or [])
            trace.degrades = list(last.get("degrades") or [])
            _fill_run_detail(base, trace, user=user)
            break
        else:
            trace.status = "timeout"
            trace.error = f"超过 {timeout}s 未返回终态"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        trace.status = "error"
        trace.error = str(exc)
    trace.elapsed_s = round(time.monotonic() - started, 1)
    return trace


def cmd_run(args: argparse.Namespace) -> int:
    reset_episode_hit_counter()
    requested_output = getattr(args, "output", None)
    output_path = Path(requested_output) if requested_output else None
    if output_path is not None and output_path.exists():
        print(f"❌ 输出已存在，拒绝覆盖：{_rel(output_path)}")
        return 2

    doc = load_cases()
    ok, detail = preflight(args.base)
    if not ok and not args.force:
        print(f"❌ 前置检查未通过：{detail}")
        print("   这是部署接缝问题，不是题目失败。修好再跑，或 --force 强跑留证据。")
        return 2
    print(f"✅ 前置检查：{detail}" if ok else f"⚠️  强跑（前置未过）：{detail}")

    selected = [
        c
        for c in doc["cases"]
        if (not args.tier or c["tier"] == args.tier)
        and (not args.case or c["id"] in args.case)
    ]
    print(f"选中 {len(selected)} / {len(doc['cases'])} 道题\n")
    runs: list[CaseRun] = []
    for i, case in enumerate(selected, 1):
        cr = CaseRun(case_id=case["id"], tier=case["tier"])
        print(f"[{i}/{len(selected)}] {case['id']} … ", end="", flush=True)
        questions = [case["query"], *case.get("followups", [])]
        for q in questions:
            try:
                t = ask_once(args.base, args.user, q, args.timeout)
            except UsersDirMismatch as exc:
                print(f"❌ {exc}")
                print("   拒绝落盘「看起来正常」的五态——这是 users 目录错配。")
                return 2
            cr.turns.append(t)
            if t.status in {"error", "timeout"}:
                break
        head = cr.turns[0] if cr.turns else None
        degraded = " ⚠降级" if head and head.degrades else ""
        print(
            f"{head.status if head else 'n/a'}  {head.elapsed_s if head else 0}s  "
            f"证据={head.evidence_bound if head else 0}{degraded}"
        )
        runs.append(cr)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = output_path or RUNS_DIR / f"{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    case_payload = [asdict(r) for r in runs]
    payload = {
        "generated_at": stamp,
        "base": args.base,
        "preflight_ok": ok,
        "preflight_detail": detail,
        # R-20260815-01/-02：把「多少题跑了、各自卡在哪一层」写进产物本身。
        # 此前只能靠事后逐题翻 run 目录才能区分四种 eb=0，读产物的人拿到的是
        # 一列不可区分的 0。
        **summarize_execution_states(case_payload),
        "cases": case_payload,
    }
    try:
        with out.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except FileExistsError:
        print(f"❌ 输出已存在，拒绝覆盖：{_rel(out)}")
        return 2
    print(f"\ntrace 已落盘：{_rel(out)}")
    print("看板：python3 -m intelligence.eval.acceptance board")
    return 0


# --------------------------------------------------------------------------- #
# board —— 进度只从这里生成
# --------------------------------------------------------------------------- #
def latest_run() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    runs = sorted(RUNS_DIR.glob("*.json"))
    return runs[-1] if runs else None


def cmd_board(args: argparse.Namespace) -> int:
    doc = load_cases()
    cases = doc["cases"]
    case_tiers = {case["id"]: case["tier"] for case in cases}
    explicit_run = getattr(args, "run", None)
    if not explicit_run and (
        getattr(args, "truth_observations", None)
        or getattr(args, "experience_labels", None)
        or getattr(args, "information_comparisons", None)
    ):
        print(
            "❌ observation sidecar 只绑定单个 run；"
            "请同时提供 board --run PATH"
        )
        return 2
    run_path = Path(explicit_run) if explicit_run else None
    try:
        if run_path is not None:
            record = load_validated_run(run_path, case_tiers)
            by_id = {case["case_id"]: case for case in record["cases"]}
            source_by_id = {case_id: run_path for case_id in by_id}
            header_note = (
                f"指定真实运行 {run_path.stem}"
                f"（前置检查{'通过' if record.get('preflight_ok') else '未过'}）"
            )
        else:
            selected = select_latest_case_runs(RUNS_DIR, case_tiers)
            by_id = {
                case_id: item.case_run for case_id, item in selected.items()
            }
            source_by_id = {
                case_id: item.source_path for case_id, item in selected.items()
            }
            contributing = sorted({path.stem for path in source_by_id.values()})
            header_note = "尚无真实运行记录"
            if contributing:
                header_note = (
                    f"汇总 {len(contributing)} 份真实运行"
                    f"（来源：{'、'.join(contributing)}）"
                )
    except RunArtifactError as exc:
        print(f"❌ run artifact 无效：{exc}")
        return 2

    try:
        observations_by_case = _load_board_observations(args, run_path)
    except ObservationArtifactError as exc:
        print(f"❌ observation sidecar 无效：{exc}")
        return 2

    information_by_case: dict[str, Mapping[str, Any]] = {}
    information_path = getattr(args, "information_comparisons", None)
    if information_path:
        assert run_path is not None
        try:
            comparison_queue = build_comparison_queue(run_path, agent="knevo")
            comparison_artifact = load_comparison_result(
                Path(information_path),
                queue=comparison_queue,
            )
            information_by_case = {
                case_id: dict(observation)
                for case_id, observation in comparison_artifact.case_observations.items()
            }
        except ComparisonArtifactError as exc:
            print(f"❌ information comparison 无效：{exc}")
            return 2

    overlay = load_verdict_overlay()
    print(f"# 验收看板 · {header_note}\n")
    print(
        "| 题 | 组 | 来源 | 运行 | 真值 | 体验 | 送达 | 信息量 | 可信度 | "
        "耗时 | 绑定证据 | 说明 |"
    )
    print("|---|---|---|---|---|---|---|---|---|---:|---:|---|")
    operational_tally = {state: 0 for state in OperationalState}
    truth_tally = {state: 0 for state in VerdictState}
    experience_tally = {state: 0 for state in ExperienceState}
    delivery_tally = {state: 0 for state in AxisState}
    information_tally = {state: 0 for state in AxisState}
    credibility_tally = {state: 0 for state in AxisState}
    # 红的稳定性按 rule.kind 差一个数量级：A 组同输入复跑实测，事实层 0% 翻转、
    # 措辞层 33%。合成一个「失败 N」会把两者压成一个数，看板就读不出
    # 「这一刀有没有用」。分层计数，不改表格结构。
    failing_kinds: dict[str, int] = {}
    operational_labels = {
        OperationalState.NOT_RUN: "⬜ 未跑",
        OperationalState.BLOCKED: "⚫ 阻塞",
        OperationalState.FAILED: "🔴 未产出",
        OperationalState.DEGRADED: "🟠 降级完成",
        OperationalState.COMPLETED: "🟢 完成",
    }
    truth_labels = {
        VerdictState.NOT_RUN: "—",
        VerdictState.PASS: "✅ 通过",
        VerdictState.FAIL: "❌ 失败",
        VerdictState.UNJUDGEABLE: "❔ 不可判",
    }
    experience_labels = {
        ExperienceState.UNLABELED: "未标注",
        ExperienceState.LABELED: "已盲标",
        ExperienceState.INELIGIBLE: "不适用",
    }
    axis_labels = {
        AxisState.PASS: "✅ 通过",
        AxisState.PARTIAL: "🟠 部分",
        AxisState.FAIL: "❌ 失败",
        AxisState.UNJUDGEABLE: "❔ 不可判",
        AxisState.NOT_EVALUATED: "— 未评",
        AxisState.NOT_RUN: "—",
    }
    information_comparison_labels = {
        InformationComparison.WORKBENCH_WINS: "✅ 工作台优",
        InformationComparison.TIE: "➖ 持平",
        InformationComparison.KNEVO_WINS: "❌ Knevo优",
    }
    for c in cases:
        r = by_id.get(c["id"])
        contract = compile_case_contract(c, overlay[c["id"]])
        case_observations = observations_by_case.get(c["id"]) or {}
        verdict = evaluate_case(
            contract,
            r,
            observations=case_observations,
        )
        axes = project_axes(
            verdict,
            information=information_by_case.get(c["id"]),
        )
        operational_tally[verdict.operational.state] += 1
        truth_tally[verdict.truth.state] += 1
        experience_tally[verdict.experience.state] += 1
        delivery_tally[axes.delivery.state] += 1
        information_tally[axes.information.state] += 1
        credibility_tally[axes.credibility.state] += 1
        t0 = (r.get("turns") or [None])[0] if r else None
        detail = ""
        if verdict.truth.state is VerdictState.FAIL:
            failures = [
                rule.reason
                for rule in verdict.truth.rules
                if rule.state is VerdictState.FAIL
            ]
            detail = failures[0] if failures else "deterministic truth rule failed"
            for rule in verdict.truth.rules:
                if rule.state is VerdictState.FAIL:
                    failing_kinds[rule.kind] = failing_kinds.get(rule.kind, 0) + 1
        elif verdict.truth.state is VerdictState.UNJUDGEABLE:
            pending = [
                rule.reason
                for rule in verdict.truth.rules
                if rule.state is VerdictState.UNJUDGEABLE
            ]
            detail = pending[0] if pending else verdict.operational.reason
        elif verdict.operational.state in {
            OperationalState.BLOCKED,
            OperationalState.FAILED,
        }:
            detail = verdict.operational.reason
        if verdict.operational.state is OperationalState.DEGRADED:
            diagnostic = (
                t0.get("synthesis_diagnostic")
                if isinstance(t0, Mapping)
                else None
            )
            reason_code = (
                str(diagnostic.get("reason_code") or "")
                if isinstance(diagnostic, Mapping)
                else ""
            )
            diagnostic_note = (
                f"synthesis reason_code={reason_code}"
                if reason_code
                else "synthesis diagnostic unavailable"
            )
            detail = (
                f"{detail}；{diagnostic_note}"
                if detail
                else f"{verdict.operational.reason}；{diagnostic_note}"
            )
        print(
            f"| {c['id']} | {c['tier']} | "
            f"{source_by_id[c['id']].stem[-7:] if c['id'] in source_by_id else '—'} | "
            f"{operational_labels[verdict.operational.state]} | "
            f"{truth_labels[verdict.truth.state]} | "
            f"{experience_labels[verdict.experience.state]}"
            f"{f'({verdict.experience.label})' if verdict.experience.label else ''} | "
            f"{axis_labels[axes.delivery.state]} | "
            f"{information_comparison_labels.get(axes.information.comparison, axis_labels[axes.information.state])} | "
            f"{axis_labels[axes.credibility.state]} | "
            f"{(t0 or {}).get('elapsed_s', '—')}"
            f"{'s' if t0 else ''} | {(t0 or {}).get('evidence_bound') or 0 if t0 else '—'} | "
            f"{detail} |"
        )

    total = len(cases)
    completed_count = (
        operational_tally[OperationalState.COMPLETED]
        + operational_tally[OperationalState.DEGRADED]
    )
    print(
        f"\n**运行口径**：{total} 道题里，未跑 "
        f"{operational_tally[OperationalState.NOT_RUN]}、阻塞 "
        f"{operational_tally[OperationalState.BLOCKED]}、未产出 "
        f"{operational_tally[OperationalState.FAILED]}、降级完成 "
        f"{operational_tally[OperationalState.DEGRADED]}、正常完成 "
        f"{operational_tally[OperationalState.COMPLETED]}（完成合计 {completed_count}）。"
    )
    judged = truth_tally[VerdictState.PASS] + truth_tally[VerdictState.FAIL]
    rate_note = (
        f"可判子集通过率 {truth_tally[VerdictState.PASS]}/{judged}"
        if judged
        else "尚无可判子集通过率"
    )
    print(
        f"**真值口径**：通过 {truth_tally[VerdictState.PASS]}、失败 "
        f"{truth_tally[VerdictState.FAIL]}、不可判 "
        f"{truth_tally[VerdictState.UNJUDGEABLE]}、未跑 "
        f"{truth_tally[VerdictState.NOT_RUN]}；{rate_note}（不是 28 题产品通过率）。"
    )
    print(
        "**三轴口径**：送达通过/部分/失败 "
        f"{delivery_tally[AxisState.PASS]}/{delivery_tally[AxisState.PARTIAL]}/"
        f"{delivery_tally[AxisState.FAIL]}；信息量已评/未评 "
        f"{total - information_tally[AxisState.NOT_EVALUATED] - information_tally[AxisState.NOT_RUN]}/"
        f"{information_tally[AxisState.NOT_EVALUATED]}；可信通过/失败/不可判 "
        f"{credibility_tally[AxisState.PASS]}/{credibility_tally[AxisState.FAIL]}/"
        f"{credibility_tally[AxisState.UNJUDGEABLE]}。"
    )
    if failing_kinds:
        breakdown = "、".join(
            f"{kind} {count}"
            for kind, count in sorted(failing_kinds.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        print(
            f"**失败按判据层**：{breakdown}。"
            "（同输入复跑实测：fact 层 0% 翻转，product_language 层 33%——"
            "措辞层的红不要单次比较）"
        )
    print(
        f"**体验口径**：已盲标 {experience_tally[ExperienceState.LABELED]}、"
        f"未标注 {experience_tally[ExperienceState.UNLABELED]}、"
        f"不适用 {experience_tally[ExperienceState.INELIGIBLE]}。"
    )
    snaps = list(SNAPSHOT_DIR.glob("*.json")) if SNAPSHOT_DIR.exists() else []
    print(f"**参照快照**：已冻结 {len(snaps)} / {total} 道（codex/knevo）")
    return 0


def _load_board_observations(
    args: argparse.Namespace, run_path: Path | None
) -> dict[str, dict[str, Any]]:
    requested = (
        (
            getattr(args, "truth_observations", None),
            "acceptance_truth_observations",
        ),
        (
            getattr(args, "experience_labels", None),
            "acceptance_experience_labels",
        ),
    )
    if not any(path for path, _kind in requested):
        if getattr(args, "blind_manifest", None):
            raise ObservationArtifactError(
                "blind manifest requires --experience-labels"
            )
        return {}
    if run_path is None:
        raise ObservationArtifactError("没有 run，不能加载 observation sidecar")

    merged: dict[str, dict[str, Any]] = {}
    for raw_path, expected_kind in requested:
        if not raw_path:
            continue
        artifact = load_observation_artifact(
            Path(raw_path),
            run_path=run_path,
            cases_path=CASES_PATH,
            overlay_path=VERDICT_OVERLAY_PATH,
            reference_eligibility_path=REFERENCE_ELIGIBILITY_PATH,
            blind_manifest_path=(
                Path(getattr(args, "blind_manifest"))
                if expected_kind == "acceptance_experience_labels"
                and getattr(args, "blind_manifest", None)
                else None
            ),
        )
        if artifact.kind != expected_kind:
            raise ObservationArtifactError(
                f"{raw_path} kind={artifact.kind}, expected={expected_kind}"
            )
        for case_id in artifact.case_observations:
            projection = artifact.for_case(case_id)
            target = merged.setdefault(case_id, {})
            duplicate = set(target) & set(projection)
            if duplicate:
                raise ObservationArtifactError(
                    f"duplicate observation axes for {case_id}: {sorted(duplicate)}"
                )
            target.update(projection)
    return merged


def classify_failure(turn: dict[str, Any]) -> str:
    """把失败分成『部署接缝』和『业务质量』—— 前者不该算题目分数。"""
    err = (turn.get("error") or "").lower()
    status = turn.get("status")
    if status == "timeout":
        return "接缝:超时"
    if "urlopen" in err or "refused" in err or "conversation_id" in err:
        return "接缝:服务/路由"
    if "api_key" in err or "missing" in err or "credential" in err:
        return "接缝:凭据"
    if "schema" in err or "400" in err or "invalid" in err:
        return "接缝:协议/Schema"
    if status == "error":
        return "接缝:未分类"
    if turn.get("degrades") and not (turn.get("evidence_bound") or 0):
        # 服务健康、模型答了，但一条证据都没绑上就降级 —— 这是检索/绑定的业务
        # 缺陷（可能是假拒答），不是部署接缝，别混进接缝账里当"环境没配好"。
        #
        # R-20260815-01：这一格此前把三种成因写成同一句话。带 `execution_state`
        # 的产物按成因分开报——「没取到」和「取到并绑上了却被判缺零掉」是相反的
        # 病，前者查检索、后者查绑定判据，混在一起会让两轮归因都指错层。
        state = str(turn.get("execution_state") or "")
        suffix = {
            "no_evidence": ":未取到证据",
            "retrieved_unsynthesized": ":取到未合成",
            "bound_but_dropped": ":绑定被判缺丢弃",
            "clarification": ":澄清轮",
        }.get(state, "")
        return f"业务质量:零证据降级{suffix}"
    return "业务质量"


def cmd_comparison_pack(args: argparse.Namespace) -> int:
    try:
        queue = build_comparison_queue(Path(args.run), agent=args.agent)
        write_comparison_queue(queue, Path(args.output))
    except ComparisonArtifactError as exc:
        print(f"❌ comparison pack 失败：{exc}")
        return 2
    eligible = sum(entry.status == "eligible" for entry in queue.entries.values())
    missing = sum(entry.status == "missing" for entry in queue.entries.values())
    ineligible = len(queue.entries) - eligible - missing
    print(
        f"✅ comparison pack 已写入 {_rel(Path(args.output))}："
        f"eligible={eligible}, missing={missing}, ineligible={ineligible}"
    )
    return 0


def cmd_validate_comparison(args: argparse.Namespace) -> int:
    try:
        queue = load_comparison_queue(Path(args.queue))
        artifact = load_comparison_result(Path(args.result), queue=queue)
    except ComparisonArtifactError as exc:
        print(f"❌ information comparison 无效：{exc}")
        return 2
    print(
        f"✅ information comparison 有效：{len(artifact.case_observations)} cases，"
        f"evaluator={artifact.evaluator_id}/{artifact.evaluator_model}"
    )
    return 0


# --------------------------------------------------------------------------- #
# freeze —— 参照快照必须外部冻结
# --------------------------------------------------------------------------- #
def cmd_freeze(args: argparse.Namespace) -> int:
    """冻结外部参照答案。

    ``via`` 必填：参照答案的价值全在来源可追溯。codex 走
    ``codex exec -m gpt-5.5``（与 dual_blind_flows.sh 同一条路）；knevo 有两条路 ——
    ``manual_paste``（人工转贴，有转写损耗、可能丢工具轨迹）与 ``cdp_readback``
    （CDP 驱动用户自己已登录的 Chrome，读 /api/conversations/{id} 的 transcript）。
    后者保真度更高且带工具调用轨迹，但**必须记住答案仍是用户账号里人工提问产生的**，
    不是我们自动跑的。半年后回看快照，必须能分清"这是机器跑的"还是"这是人问的"、
    以及问的是哪一天 —— 否则基准不可复核。

    ``answer_sha256`` 是防篡改锚：冻结后任何改动都会让哈希对不上。
    ``--meta-file`` 收 JSON，落到 ``source_meta``：cdp_readback 用它存会话 id、
    原始提问、工具调用轨迹 —— 工具轨迹能和题目的 expect_tools 直接对照，
    是"它怎么答出来的"而不只是"它答了什么"。
    """
    doc = load_cases()
    ids = {c["id"] for c in doc["cases"]}
    if args.case_id not in ids:
        print(f"❌ 未知题号 {args.case_id}。可用：{sorted(ids)}")
        return 2
    if args.agent not in doc["reference_agents"]:
        print(f"❌ agent 必须是 {doc['reference_agents']} 之一")
        return 2
    if args.answer_file == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.answer_file).read_text(encoding="utf-8")
    if not text.strip():
        print("❌ 答案为空，拒绝冻结")
        return 2
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOT_DIR / f"{args.case_id}.{args.agent}.json"
    if out.exists() and not args.overwrite:
        print(
            f"❌ {out.name} 已存在。参照快照一旦冻结不应重生成；确需覆盖加 --overwrite"
        )
        return 2
    meta = None
    if getattr(args, "meta_file", None):
        meta = json.loads(Path(args.meta_file).read_text(encoding="utf-8"))
    out.write_text(
        json.dumps(
            {
                "case_id": args.case_id,
                "agent": args.agent,
                "frozen_at": datetime.now(timezone.utc).isoformat(),
                "via": args.via,
                "asked_at": args.asked_at,
                "answer_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "source_meta": meta,
                "answer": text,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"✅ 已冻结 {_rel(out)}（{len(text)} 字，via={args.via}）")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="acceptance", description="28 道验收题台账")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("board", help="打印看板（进度唯一来源）")
    b.add_argument("--run", help="只读取指定 run artifact（sidecar 必须显式绑定）")
    b.add_argument("--truth-observations", help="显式绑定的 truth observation sidecar")
    b.add_argument("--experience-labels", help="显式绑定的 blind experience sidecar")
    b.add_argument(
        "--information-comparisons",
        help="显式绑定的 information comparison sidecar",
    )
    b.add_argument("--blind-manifest", help="experience sidecar 对应的密封盲评身份清单")
    b.set_defaults(func=cmd_board)

    r = sub.add_parser("run", help="走真实路径跑题并落 trace")
    r.add_argument("--base", default=DEFAULT_BASE)
    r.add_argument("--user", default=DEFAULT_USER)
    r.add_argument("--tier", choices=["high_freq", "mid_freq", "long_tail"])
    r.add_argument("--case", action="append", help="只跑指定题号，可重复")
    r.add_argument("--timeout", type=float, default=300.0)
    r.add_argument("--force", action="store_true", help="前置检查未过也强跑")
    r.add_argument("--output", help="trace 精确输出路径（拒绝覆盖已有文件）")
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("freeze", help="冻结 codex/knevo 参照答案")
    f.add_argument("case_id")
    f.add_argument("agent")
    f.add_argument("answer_file", help="答案文件路径；写 - 表示从 stdin 读")
    f.add_argument(
        "--via",
        required=True,
        choices=["manual_paste", "cdp_readback", "codex_exec", "cli"],
        help=(
            "来源：manual_paste=人工转贴；cdp_readback=CDP 读用户已登录 Chrome 的"
            "会话 transcript（保真、带工具轨迹，仍是人工提问）；codex_exec=codex exec 自动跑"
        ),
    )
    f.add_argument("--asked-at", help="实际提问日期 YYYY-MM-DD（与题目锚定日可能不同）")
    f.add_argument("--meta-file", help="JSON 文件，落到 source_meta（会话 id / 原始提问 / 工具轨迹）")
    f.add_argument("--overwrite", action="store_true")
    f.set_defaults(func=cmd_freeze)

    cp = sub.add_parser("comparison-pack", help="生成冻结 Workbench/Knevo 对比包")
    cp.add_argument("--run", required=True)
    cp.add_argument("--agent", default="knevo", choices=["knevo"])
    cp.add_argument("--output", required=True)
    cp.set_defaults(func=cmd_comparison_pack)

    vc = sub.add_parser("validate-comparison", help="校验 information comparison")
    vc.add_argument("result")
    vc.add_argument("--queue", required=True)
    vc.set_defaults(func=cmd_validate_comparison)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
