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

层次：本模块认识证据账本与 ToolSpec，不认识子进程；``calculation_sandbox`` 反之。
runner 由 ``bind_derived_calculation_tool`` 按 episode 绑（要这一个 episode 的
``EvidenceLedger``），``ContinuousAgentEpisode`` 起步时并进注册表——与 ``sub_research``
同一条「没账本不挂」的规矩。``HarnessReferenceLoop`` 没有证据账本，因此没有这个工具。
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from intelligence.paths import default_market_db_path
from intelligence.services import calculation_sandbox
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
_RESULT_CHARS_IN_DETAIL = 600
_EVIDENCE_DETAIL_CHARS = 600

ERROR_NO_BOUND_EVIDENCE = "no_bound_evidence"
ERROR_SCRIPT_REJECTED = "script_rejected"
ERROR_SANDBOX_TIMEOUT = "sandbox_timeout"
ERROR_SANDBOX_VIOLATION = "sandbox_violation"
ERROR_SCRIPT_ERROR = "script_error"
ERROR_NO_RESULT = "no_result_emitted"
ERROR_SANDBOX_UNAVAILABLE = "sandbox_unavailable"


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


def oldest_as_of(evidence: Sequence[AgentEvidence]) -> str | None:
    """§3.4：``as_of`` 从输入继承，取最旧的一条；一条都没日期就是 None（写「未定日期」）。"""

    dates = [parsed for item in evidence if (parsed := parse_as_of(item.source_date))]
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


def compute_calc_id(
    script: str,
    input_evidence_hashes: Sequence[str],
    *,
    db_fingerprint_value: str = "",
) -> str:
    payload = "|".join(
        (
            calculation_sandbox.PRELUDE_VERSION,
            script,
            ",".join(sorted(input_evidence_hashes)),
            db_fingerprint_value,
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
) -> DerivedCalculation | CalculationError:
    """纯函数：给证据与脚本，回产物或带码的错误。不碰账本、不碰 ToolSpec。"""

    inputs = tuple(item for item in evidence if item.content_hash)
    if not inputs:
        return CalculationError(
            ERROR_NO_BOUND_EVIDENCE,
            "本回合还没有任何已绑定的证据；先用取数 / 检索工具取证，再做计算",
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
    hashes = tuple(item.content_hash for item in inputs)
    fingerprint = db_fingerprint(mounted_db) if mounted_db else ""
    try:
        run = calculation_sandbox.run_script(
            script,
            evidence=evidence_payload(inputs),
            db_path=mounted_db,
            timeout=timeout,
            python=python,
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
            _last_stderr_line(run.stderr_tail) or f"exit code {run.exit_code}",
            enforcement=run.enforcement,
            stderr_tail=run.stderr_tail,
        )
    if run.result is None:
        return CalculationError(
            ERROR_NO_RESULT,
            "脚本正常结束但没有调用 emit({...})；结果字典必须经 emit 输出",
            enforcement=run.enforcement,
            stderr_tail=run.stderr_tail,
        )
    return DerivedCalculation(
        calc_id=compute_calc_id(script, hashes, db_fingerprint_value=fingerprint),
        purpose=purpose,
        script=script,
        input_evidence_hashes=hashes,
        input_refs=evidence_refs(inputs),
        as_of=oldest_as_of(inputs),
        result=dict(run.result),
        enforcement=run.enforcement,
        exit_code=run.exit_code,
        duration_ms=run.duration_ms,
        stdout_tail=run.stdout_tail,
        stderr_tail=run.stderr_tail,
        runtime=dict(run.runtime),
        db_fingerprint=fingerprint,
        notes=run.notes,
    )


def _last_stderr_line(stderr: str) -> str:
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    return lines[-1][:240] if lines else ""


def _result_text(result: Mapping[str, object]) -> str:
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded) > _RESULT_CHARS_IN_DETAIL:
        encoded = encoded[: _RESULT_CHARS_IN_DETAIL - 1] + "…"
    return encoded


def derived_evidence(calc: DerivedCalculation) -> AgentEvidence:
    """把产物铸成一条证据：档次 ``derived_calculation``，日期是输入最旧 as_of，输入链在 ``derived_from``。

    ``detail`` 里放结果与输入 E 号（模型要读、要引）；``enforcement`` 不进 detail——同脚本
    同输入在两档隔离下算出的是同一条证据，隔离档次记在 observation 与 trace 里。
    """

    as_of_text = calc.as_of or "未定日期（输入证据均无日期）"
    numeric = tuple(
        StructuredObservation(
            subject=calc.purpose,
            as_of=calc.as_of or "",
            metric=str(key),
            value=float(value),
        )
        for key, value in calc.result.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    return AgentEvidence(
        tool=DERIVED_CALCULATION_TOOL,
        title=f"派生计算：{calc.purpose}"[:48],
        detail=(
            f"{calc.purpose}｜结果 {_result_text(calc.result)}｜"
            f"输入 {'、'.join(calc.input_refs)}，as_of={as_of_text}（取输入最旧）"
        ),
        source=f"sandbox:{calc.calc_id}",
        source_date=calc.as_of,
        evidence_tier=DERIVED_CALCULATION_TIER,
        independent_key=f"derived:{calc.calc_id}",
        observations=numeric,
        derived_from=calc.input_evidence_hashes,
    )


def success_observation(calc: DerivedCalculation) -> str:
    return (
        f"已完成派生计算「{calc.purpose}」：{_result_text(calc.result)}；"
        f"输入 {len(calc.input_evidence_hashes)} 条证据（{'、'.join(calc.input_refs)}），"
        f"as_of={calc.as_of or '未定日期'}（取输入最旧，不是今天）；"
        f"沙箱 enforcement={calc.enforcement}，{calc.duration_ms} ms，calc_id={calc.calc_id}。"
        "派生数的档次不高于输入里最低的一档；与某个来源的数不一致时，先看两边输入是否同一批证据。"
    )


def error_observation(error: CalculationError) -> str:
    hint = (
        "改脚本后可重试。" if error.retryable_by_rewriting else "先用取证工具拿到证据再来计算。"
    )
    return (
        f"派生计算未产出（{error.code}：{error.detail}）。"
        f"这不是任何数值，也不能当否定证据；{hint}"
    )


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
    )


# --------------------------------------------------------------------------- binding


def bind_derived_calculation_tool(
    *,
    evidence_ledger: EvidenceLedger,
    db_path: str | os.PathLike[str] | None = None,
    python: str | None = None,
) -> ToolSpec:
    """绑出这一个 episode 的 ``derived_calculation`` ToolSpec。

    ``evidence_ledger`` 是账本对象不是快照：每次调用时读**当时**已有的证据（模型在
    第 3 轮算的是前两轮取到的证据）。``db_path`` 缺省走 ``default_market_db_path()``。
    """

    def runner(args_json: str, tool_context: AgentToolContext) -> ToolRunResult:
        args = json.loads(args_json)
        tool_context.check_cancelled()
        requested = float(args.get("timeout_seconds") or DERIVED_CALCULATION_DEFAULT_TIMEOUT)
        # 工具窗以本批授予为界：模型要 60 秒、窗只剩 12 秒，就只给 12 秒。
        window = tool_context.timeout(requested)
        outcome = run_derived_calculation(
            script=str(args.get("script") or ""),
            purpose=str(args.get("purpose") or ""),
            evidence=evidence_ledger.items(),
            use_duckdb=bool(args.get("use_duckdb", False)),
            timeout=max(1.0, min(requested, window)),
            db_path=db_path,
            python=python,
        )
        tool_context.check_cancelled()
        return to_tool_result(outcome)

    return derived_calculation_tool_spec(runner)
