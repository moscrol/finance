"""``derived_calculation``：对本回合已绑定的证据跑一段 Python，产物带输入哈希链。

spec `2026-09-02-capability-amplification-output-gate-design.md` §3.4。它**不修任何已量出
的缺陷**（取数类题沙箱一个都不修），开的是现有工具完全答不了的一类题：跨源口径核对、
差额 / 敏感性、统计检验。第一个用例是跨源口径核对而不是 DCF——两边都是已绑定证据、
有真值可判、``input_evidence_hashes`` 天然完整。

协议（§3.4，逐条）：

- 产物强制携带 ``input_evidence_hashes``（本回合已绑定证据的哈希）+ ``script``（原样）+
  ``as_of``。
- ``as_of`` **从输入继承、取最旧的那一条**，不是运行日（knevo 演示脚本把运行日写成
  ``AS_OF`` 的反例就在 spec 里）。
- 沙箱只挂 DuckDB 只读连接 + 本回合证据集，不写库、不外呼（``calculation_sandbox`` 两层）。
- 沙箱数与 provider 数不一致时不是二选一：看推导链的输入是不是同一批证据。

工单 04（计算与产物）在此之上加了四件，协议一条不改：

- ``params``：模型传的假设 / 参数字典，脚本里以 ``PARAMS`` 读，进 calc_id（同脚本不同假设
  是两次不同的计算），进产物；用户「改一个假设」就是改它重算。
- ``inputs_from_calc``：沿用上一轮某次计算的输入快照（不重取数、哈希链不断），配 ``params``
  即「只重算受影响部分」；上一轮的输入在脚本里编号 ``P1..Pn``，本轮证据仍是 ``E1..En``。
- 结果协议 v1（``sandbox_fincalc.build_result`` / ``emit_result``）：摘要 / 表 / 图 / 参数 /
  公式 / 说明；表格数字全部进派生证据的 ``observations``，正文引用的每个数都有据。
- 完整计算记录走 ``ToolRunResult.telemetry``（只进审计底稿，不进模型上下文），由
  ``derived_calculation_artifacts.publish_calculation_artifacts`` 在 run 收口时渲染成
  ``calc-<id>.json / .csv / .html`` 产物。

层次：本模块认识证据账本与 ToolSpec，不认识子进程；``calculation_sandbox`` 反之。
runner 由 ``bind_derived_calculation_tool`` 按 episode 绑（要这一个 episode 的
``EvidenceLedger``），``ContinuousAgentEpisode`` 起步时并进注册表——与 ``sub_research``
同一条「没账本不挂」的规矩。``HarnessReferenceLoop`` 没有证据账本，因此没有这个工具。
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from intelligence.paths import default_market_db_path
from intelligence.services import calculation_sandbox
from intelligence.services import derived_calculation_artifacts as artifacts
from intelligence.services.agent_research import (
    AgentEvidence,
    AgentToolContext,
    StructuredObservation,
)
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import (
    DERIVED_CALCULATION_DEFAULT_TIMEOUT,
    ToolRunResult,
    ToolSpec,
    derived_calculation_tool_spec,
)

DERIVED_CALCULATION_TOOL = "derived_calculation"
# 证据档次词表里的新值：派生数不高于其输入的最低档，这个标签只说「它是算出来的」。
DERIVED_CALCULATION_TIER = "derived_calculation"
_PROVIDER = "sandbox:derived_calculation"
_EVIDENCE_DETAIL_CHARS = 600
# 模型视图一次工具观察 900 字符（tool_result_budget.MAX_OBSERVATION_CHARS）；结果正文给 470，
# 其余留给固定句（计算编号 / 产物 / 输入 / as_of）。计算编号与产物名放在**结果之前**：
# 预算从头数，放在末尾的会被截掉，模型就引不出编号、也不知道有文件可下载。
_OBSERVATION_RESULT_BUDGET = 470
# 证据 detail 的模型视图只有 240 字符（MAX_EVIDENCE_DETAIL_CHARS），同样把编号放前面。
_DERIVED_DETAIL_RESULT_BUDGET = 320

ERROR_NO_BOUND_EVIDENCE = "no_bound_evidence"
ERROR_SCRIPT_REJECTED = "script_rejected"
ERROR_SANDBOX_TIMEOUT = "sandbox_timeout"
ERROR_SANDBOX_VIOLATION = "sandbox_violation"
ERROR_SCRIPT_ERROR = "script_error"
ERROR_NO_RESULT = "no_result_emitted"
ERROR_SANDBOX_UNAVAILABLE = "sandbox_unavailable"
ERROR_BASE_CALC_NOT_FOUND = "base_calc_not_found"

CalcLoader = Callable[[str], Mapping[str, object] | None]


@dataclass(frozen=True)
class DerivedCalculation:
    """一次成功的派生计算产物（§3.4 协议的字段全在这里）。"""

    calc_id: str
    purpose: str
    script: str
    input_evidence_hashes: tuple[str, ...]
    input_refs: tuple[str, ...]
    as_of: str | None
    result: Mapping[str, object]
    enforcement: str
    exit_code: int | None
    duration_ms: int
    stdout_tail: str
    stderr_tail: str
    runtime: Mapping[str, object] = field(default_factory=dict)
    db_fingerprint: str = ""
    notes: tuple[str, ...] = ()
    # 工单 04：参数、输入快照（供下一轮 inputs_from_calc 复用）、沿用自哪次计算。
    params: Mapping[str, object] = field(default_factory=dict)
    inputs: tuple[Mapping[str, object], ...] = ()
    base_calc_id: str | None = None

    @property
    def view(self) -> artifacts.ResultView:
        return artifacts.normalize_result(self.result)

    @property
    def artifact_names(self) -> tuple[str, ...]:
        return artifacts.planned_artifact_names(self.calc_id, self.view)

    def to_dict(self) -> dict[str, object]:
        return {
            "calc_id": self.calc_id,
            "purpose": self.purpose,
            "script": self.script,
            "input_evidence_hashes": list(self.input_evidence_hashes),
            "input_refs": list(self.input_refs),
            "as_of": self.as_of,
            "result": dict(self.result),
            "enforcement": self.enforcement,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "runtime": dict(self.runtime),
            "db_fingerprint": self.db_fingerprint,
            "notes": list(self.notes),
            "params": dict(self.params),
            "inputs": [dict(item) for item in self.inputs],
            "base_calc_id": self.base_calc_id,
            "artifacts": list(self.artifact_names),
        }


@dataclass(frozen=True)
class CalculationError:
    """计算没产出——带码带原因，模型读得出是改脚本还是先取证。"""

    code: str
    detail: str
    enforcement: str = ""
    stderr_tail: str = ""

    @property
    def retryable_by_rewriting(self) -> bool:
        return self.code in {
            ERROR_SCRIPT_REJECTED,
            ERROR_SANDBOX_TIMEOUT,
            ERROR_SANDBOX_VIOLATION,
            ERROR_SCRIPT_ERROR,
            ERROR_NO_RESULT,
        }


# --------------------------------------------------------------------------- pure pieces


def parse_as_of(value: str | None) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def oldest_as_of(
    evidence: Sequence[AgentEvidence],
    prior_inputs: Sequence[Mapping[str, object]] = (),
) -> str | None:
    """§3.4：``as_of`` 从输入继承，取最旧的一条；一条都没日期就是 None（写「未定日期」）。

    沿用上一轮输入时它们也算输入：as_of 同样在它们里面取最旧。
    """

    dates = [parsed for item in evidence if (parsed := parse_as_of(item.source_date))]
    dates.extend(
        parsed
        for item in prior_inputs
        if (parsed := parse_as_of(str(item.get("as_of") or "") or None))
    )
    return min(dates).isoformat() if dates else None


def evidence_refs(evidence: Sequence[AgentEvidence]) -> tuple[str, ...]:
    return tuple(f"E{index}" for index in range(1, len(evidence) + 1))


def evidence_payload(evidence: Sequence[AgentEvidence]) -> list[dict[str, object]]:
    """脚本里看到的 ``EVIDENCE``：按证据账本顺序编 E 号，带哈希与结构化观察值。

    E 号取账本序。账本会跳过晚于信息截止日的证据，而模型视图（累加器）不跳，所以
    在「模型见过一条被截止日拒掉的证据」这个罕见情形下两边编号会错一位——脚本同时
    拿到 ``hash`` / ``tool`` / ``observations``，按这些选证据不受影响；产物里的
    ``input_refs`` + ``input_evidence_hashes`` 让读收据的人能对上。
    """

    payload: list[dict[str, object]] = []
    for index, item in enumerate(evidence, start=1):
        payload.append(
            {
                "ref": f"E{index}",
                "hash": item.content_hash,
                "tool": item.tool,
                "title": item.title,
                "detail": item.detail[:_EVIDENCE_DETAIL_CHARS],
                "source": item.source,
                "as_of": item.source_date,
                "tier": item.evidence_tier,
                "observations": [
                    {
                        "subject": obs.subject,
                        "as_of": obs.as_of,
                        "metric": obs.metric,
                        "value": obs.value,
                    }
                    for obs in item.observations
                ],
            }
        )
    return payload


_INPUT_SNAPSHOT_KEYS = ("hash", "tool", "title", "source", "as_of", "tier", "observations")


def compact_inputs(payload: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    """进产物记录的输入快照：去掉 detail 正文（脚本复用时读 observations），其余原样。"""

    out: list[dict[str, object]] = []
    for item in payload:
        snapshot: dict[str, object] = {"ref": item.get("ref")}
        for key in _INPUT_SNAPSHOT_KEYS:
            if key in item:
                snapshot[key] = item[key]
        out.append(snapshot)
    return tuple(out)


def prior_inputs_payload(prior_inputs: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """上一轮的输入快照 → 本轮脚本里编号 ``P1..Pn`` 的证据项（``detail`` 可能缺）。"""

    payload: list[dict[str, object]] = []
    for index, item in enumerate(prior_inputs, start=1):
        if not str(item.get("hash") or ""):
            continue
        entry = {key: item.get(key) for key in _INPUT_SNAPSHOT_KEYS}
        entry["ref"] = f"P{index}"
        entry["detail"] = str(item.get("detail") or "")[:_EVIDENCE_DETAIL_CHARS]
        entry["observations"] = list(item.get("observations") or ())
        payload.append(entry)
    return payload


def db_fingerprint(path: str | os.PathLike[str] | None) -> str:
    """只读快照的身份：路径 + 大小 + mtime。库变了，同脚本同证据也该是另一个 calc_id。"""

    if not path:
        return ""
    target = Path(path)
    try:
        stat = target.stat()
    except OSError:
        return f"{target}:missing"
    return f"{target}:{stat.st_size}:{stat.st_mtime_ns}"


def canonical_params(params: Mapping[str, object] | None) -> str:
    """参数的规范 JSON（键排序）；空参是空串，老 calc_id 一个不变。"""

    if not params:
        return ""
    return json.dumps(dict(params), ensure_ascii=False, sort_keys=True, default=str)


def compute_calc_id(
    script: str,
    input_evidence_hashes: Sequence[str],
    *,
    db_fingerprint_value: str = "",
    params_json: str = "",
) -> str:
    payload = "|".join(
        (
            calculation_sandbox.PRELUDE_VERSION,
            script,
            ",".join(sorted(input_evidence_hashes)),
            db_fingerprint_value,
            params_json,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def run_derived_calculation(
    *,
    script: str,
    purpose: str,
    evidence: Sequence[AgentEvidence],
    use_duckdb: bool = False,
    timeout: float = DERIVED_CALCULATION_DEFAULT_TIMEOUT,
    db_path: str | os.PathLike[str] | None = None,
    python: str | None = None,
    params: Mapping[str, object] | None = None,
    prior_inputs: Sequence[Mapping[str, object]] = (),
    base_calc_id: str | None = None,
) -> DerivedCalculation | CalculationError:
    """纯函数：给证据与脚本，回产物或带码的错误。不碰账本、不碰 ToolSpec。

    ``prior_inputs`` 是上一轮计算记录里的输入快照（``inputs_from_calc``）：与本回合证据一起
    进 ``EVIDENCE``（编号 ``P1..``），哈希一起进 ``input_evidence_hashes``，as_of 一起取最旧。
    """

    inputs = tuple(item for item in evidence if item.content_hash)
    prior_payload = prior_inputs_payload(prior_inputs)
    if not inputs and not prior_payload:
        return CalculationError(
            ERROR_NO_BOUND_EVIDENCE,
            "本回合还没有任何已绑定的证据；先用取数 / 检索工具取证，再做计算"
            "（或用 inputs_from_calc 沿用上一轮计算的输入）",
        )
    blocked = calculation_sandbox.forbidden_import(script)
    if blocked is not None:
        return CalculationError(
            ERROR_SCRIPT_REJECTED,
            f"forbidden_import:{blocked}——沙箱不联网、不起进程，去掉这一段再试",
        )
    mounted_db: str | None = None
    if use_duckdb:
        candidate = Path(db_path) if db_path else default_market_db_path()
        if not candidate.exists():
            return CalculationError(
                ERROR_SANDBOX_UNAVAILABLE,
                f"duckdb snapshot not found: {candidate}",
            )
        mounted_db = str(candidate)
    payload = [*evidence_payload(inputs), *prior_payload]
    hashes = tuple(str(item["hash"]) for item in payload)
    fingerprint = db_fingerprint(mounted_db) if mounted_db else ""
    params_json = canonical_params(params)
    try:
        run = calculation_sandbox.run_script(
            script,
            evidence=payload,
            db_path=mounted_db,
            timeout=timeout,
            python=python,
            params=params,
        )
    except calculation_sandbox.SandboxUnavailable as exc:
        return CalculationError(ERROR_SANDBOX_UNAVAILABLE, str(exc))
    if run.timed_out:
        return CalculationError(
            ERROR_SANDBOX_TIMEOUT,
            f"脚本超过 {timeout:g} 秒未结束；缩小计算量或提高 timeout_seconds",
            enforcement=run.enforcement,
            stderr_tail=run.stderr_tail,
        )
    if run.violations:
        return CalculationError(
            ERROR_SANDBOX_VIOLATION,
            "; ".join(run.violations),
            enforcement=run.enforcement,
            stderr_tail=run.stderr_tail,
        )
    if run.exit_code != 0:
        return CalculationError(
            ERROR_SCRIPT_ERROR,
            _script_error_detail(run.stderr_tail) or f"exit code {run.exit_code}",
            enforcement=run.enforcement,
            stderr_tail=run.stderr_tail,
        )
    if run.result is None:
        return CalculationError(
            ERROR_NO_RESULT,
            "脚本正常结束但没有调用 emit({...}) / emit_result(...)；结果必须经 emit 输出",
            enforcement=run.enforcement,
            stderr_tail=run.stderr_tail,
        )
    return DerivedCalculation(
        calc_id=compute_calc_id(
            script, hashes, db_fingerprint_value=fingerprint, params_json=params_json
        ),
        purpose=purpose,
        script=script,
        input_evidence_hashes=hashes,
        input_refs=tuple(str(item["ref"]) for item in payload),
        as_of=oldest_as_of(inputs, prior_payload),
        result=dict(run.result),
        enforcement=run.enforcement,
        exit_code=run.exit_code,
        duration_ms=run.duration_ms,
        stdout_tail=run.stdout_tail,
        stderr_tail=run.stderr_tail,
        runtime=dict(run.runtime),
        db_fingerprint=fingerprint,
        notes=run.notes,
        params=dict(params or {}),
        inputs=compact_inputs(payload),
        base_calc_id=base_calc_id,
    )


def _script_error_detail(stderr: str) -> str:
    """脚本报错时给模型的定位：最后一行异常 + 出错那一行的脚本行号（去掉 prelude 偏移的口径由
    traceback 自带 ``script.py`` 行号——模型看到的是拼接后的行号，这里附上 prelude 行数供换算）。"""

    lines = [line.rstrip() for line in (stderr or "").splitlines() if line.strip()]
    if not lines:
        return ""
    last = lines[-1].strip()[:240]
    location = next(
        (line.strip() for line in reversed(lines) if 'File "' in line and "script.py" in line),
        "",
    )
    prelude_lines = calculation_sandbox.PRELUDE_SOURCE.count("\n")
    if location:
        return f"{last}（{location[:120]}；脚本行号 = 报错行号 − {prelude_lines}）"
    return last


def _observations(calc: DerivedCalculation) -> tuple[StructuredObservation, ...]:
    """结果里每一个数都进观察值：摘要标量 + 表格单元格（``表名.列名[行标签]``）。"""

    return tuple(
        StructuredObservation(
            subject=calc.purpose,
            as_of=calc.as_of or "",
            metric=metric,
            value=value,
        )
        for metric, value in artifacts.numeric_observations(calc.view)
    )


def derived_evidence(calc: DerivedCalculation) -> AgentEvidence:
    """把产物铸成一条证据：档次 ``derived_calculation``，日期是输入最旧 as_of，输入链在 ``derived_from``。

    ``detail`` 里放结果与输入 E 号（模型要读、要引）；``enforcement`` 不进 detail——同脚本
    同输入在两档隔离下算出的是同一条证据，隔离档次记在 observation 与 trace 里。
    """

    as_of_text = calc.as_of or "未定日期（输入证据均无日期）"
    result_text = artifacts.compact_text(calc.view, budget=_DERIVED_DETAIL_RESULT_BUDGET)
    return AgentEvidence(
        tool=DERIVED_CALCULATION_TOOL,
        title=f"派生计算：{calc.purpose}"[:48],
        detail=(
            f"{calc.purpose}｜计算编号 {calc.calc_id}｜结果 {result_text}｜"
            f"输入 {'、'.join(calc.input_refs)}，as_of={as_of_text}（取输入最旧）"
        ),
        source=f"sandbox:{calc.calc_id}",
        source_date=calc.as_of,
        evidence_tier=DERIVED_CALCULATION_TIER,
        independent_key=f"derived:{calc.calc_id}",
        observations=_observations(calc),
        derived_from=calc.input_evidence_hashes,
    )


def success_observation(calc: DerivedCalculation) -> str:
    result_text = artifacts.compact_text(calc.view, budget=_OBSERVATION_RESULT_BUDGET)
    params_text = (
        f"参数 {json.dumps(dict(calc.params), ensure_ascii=False, default=str)[:100]}；"
        if calc.params
        else ""
    )
    reuse_text = f"沿用计算 {calc.base_calc_id} 的输入；" if calc.base_calc_id else ""
    files = "、".join(name for name in calc.artifact_names if not name.endswith(".json"))
    return (
        f"已完成派生计算「{calc.purpose}」，计算编号 {calc.calc_id}（表格 / 图表随本次回答落盘为可下载产物 "
        f"{files}，正文引用表格数字时写明「计算编号 {calc.calc_id}」）："
        f"{result_text}；"
        f"{params_text}{reuse_text}"
        f"输入 {len(calc.input_evidence_hashes)} 条证据（{'、'.join(calc.input_refs)}），"
        f"as_of={calc.as_of or '未定日期'}（取输入最旧，不是今天）；"
        f"enforcement={calc.enforcement}，{calc.duration_ms} ms。"
        f"改假设用 inputs_from_calc={calc.calc_id} 沿用输入重算；"
        "派生数档次不高于输入最低档，与来源不一致先看输入是否同一批。"
    )


def error_observation(error: CalculationError) -> str:
    if error.code == ERROR_BASE_CALC_NOT_FOUND:
        hint = "检查 inputs_from_calc 的计算编号（回答正文与产物文件名 calc-<id> 里那 16 位），或改为重新取数再算。"
    elif error.retryable_by_rewriting:
        hint = "改脚本后可重试。"
    else:
        hint = "先用取证工具拿到证据再来计算。"
    return (
        f"派生计算未产出（{error.code}：{error.detail}）。"
        f"这不是任何数值，也不能当否定证据；{hint}"
    )


def calculation_record(calc: DerivedCalculation) -> dict[str, object]:
    """进 ``ToolRunResult.telemetry`` 的完整记录（审计底稿 → continuous-episode.json → 产物渲染）。"""

    return calc.to_dict()


def to_tool_result(outcome: DerivedCalculation | CalculationError) -> ToolRunResult:
    if isinstance(outcome, CalculationError):
        status = "timeout" if outcome.code == ERROR_SANDBOX_TIMEOUT else "error"
        return ToolRunResult(
            evidence=(),
            observation=error_observation(outcome),
            trace=ProviderTrace(
                provider=_PROVIDER,
                capability=DERIVED_CALCULATION_TOOL,
                status=status,
                detail=(
                    f"{outcome.code}: {outcome.detail}"
                    + (f" [enforcement={outcome.enforcement}]" if outcome.enforcement else "")
                )[:400],
                result_count=0,
            ),
        )
    return ToolRunResult(
        evidence=(derived_evidence(outcome),),
        observation=success_observation(outcome),
        trace=ProviderTrace(
            provider=_PROVIDER,
            capability=DERIVED_CALCULATION_TOOL,
            status="success",
            detail=(
                f"calc_id={outcome.calc_id}; enforcement={outcome.enforcement}; "
                f"inputs={len(outcome.input_evidence_hashes)}; {outcome.duration_ms}ms"
            ),
            source_trade_date=outcome.as_of,
            result_count=1,
        ),
        # 控制面收据：只进 ledger / continuous-episode.json，不进模型上下文。
        telemetry={"derived_calculation": calculation_record(outcome)},
    )


# --------------------------------------------------------------------------- prior calculations


def load_calculation_record(
    calc_id: str, *, runs_root: str | os.PathLike[str] | None = None
) -> dict[str, object] | None:
    """按计算编号找上一轮落盘的 ``calc-<id>.json``（默认在当前用户的 runs 目录里找）。

    产物是 run 收口时由 orchestrator 写的，所以只能找到**已完成**回合的计算；同一编号可能
    出现在多个 run（同脚本同输入同参数），内容相同，取任意一份。找不到回 None。
    """

    if not artifacts.is_calc_id(calc_id):
        return None
    if runs_root is None:
        # 延迟 import：run_store 依赖 api.stream_events 一族，模块级 import 会把装配面拖进来。
        from intelligence.services.run_store import RunStore  # noqa: PLC0415

        root = Path(RunStore().root)
    else:
        root = Path(runs_root)
    if not root.is_dir():
        return None
    for path in sorted(root.glob(f"*/{artifacts.ARTIFACT_PREFIX}{calc_id}.json"), reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and record.get("calc_id") == calc_id:
            return record
    return None


# --------------------------------------------------------------------------- binding


def bind_derived_calculation_tool(
    *,
    evidence_ledger: EvidenceLedger,
    db_path: str | os.PathLike[str] | None = None,
    python: str | None = None,
    calc_loader: CalcLoader | None = None,
) -> ToolSpec:
    """绑出这一个 episode 的 ``derived_calculation`` ToolSpec。

    ``evidence_ledger`` 是账本对象不是快照：每次调用时读**当时**已有的证据（模型在
    第 3 轮算的是前两轮取到的证据）。``db_path`` 缺省走 ``default_market_db_path()``。
    ``calc_loader`` 缺省按计算编号在当前用户的 runs 目录里找上一轮的记录。
    """

    loader = calc_loader or load_calculation_record

    def runner(args_json: str, tool_context: AgentToolContext) -> ToolRunResult:
        args = json.loads(args_json)
        tool_context.check_cancelled()
        requested = float(args.get("timeout_seconds") or DERIVED_CALCULATION_DEFAULT_TIMEOUT)
        script = str(args.get("script") or "")
        params_arg = args.get("params")
        params: dict[str, object] = dict(params_arg) if isinstance(params_arg, Mapping) else {}
        prior_inputs: Sequence[Mapping[str, object]] = ()
        base_calc_id = str(args.get("inputs_from_calc") or "").strip() or None
        if base_calc_id:
            record = loader(base_calc_id)
            if record is None:
                return to_tool_result(
                    CalculationError(
                        ERROR_BASE_CALC_NOT_FOUND,
                        f"找不到计算编号 {base_calc_id} 的记录（只有已完成回合落盘的计算能沿用）",
                    )
                )
            if not script:
                script = str(record.get("script") or "")
            base_params = record.get("params")
            if isinstance(base_params, Mapping):
                params = {**dict(base_params), **params}
            raw_inputs = record.get("inputs")
            prior_inputs = tuple(
                item for item in (raw_inputs or ()) if isinstance(item, Mapping)
            )
        # 工具窗以本批授予为界：模型要 60 秒、窗只剩 12 秒，就只给 12 秒。
        window = tool_context.timeout(requested)
        outcome = run_derived_calculation(
            script=script,
            purpose=str(args.get("purpose") or ""),
            evidence=evidence_ledger.items(),
            use_duckdb=bool(args.get("use_duckdb", False)),
            timeout=max(1.0, min(requested, window)),
            db_path=db_path,
            python=python,
            params=params,
            prior_inputs=prior_inputs,
            base_calc_id=base_calc_id,
        )
        tool_context.check_cancelled()
        return to_tool_result(outcome)

    return derived_calculation_tool_spec(runner)
