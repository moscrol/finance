"""判官身份与校准有效性：唯一资格门的纯函数层。

方案：``docs/superpowers/plans/2026-09-14-judge-calibration-validity.md`` §3.3。

**这个模块只回答一个问题：这批评分能不能拿去下实验结论。** 它不评分、不调模型、
不读文件、不看环境变量——所有判断只吃传进来的收据。理由是那条被复现的缺口：
``aggregate_components`` 当时只校验 rubric 版本没混用，于是「旧底是 Grok 测的、
补评换 GPT 打分」照样出 ``callable``；而补评脚本自己把这个假设写在收据的
``judge_continuity`` 里当人读字符串——**假设写进散文就是没有门**。

三条贯穿全模块的纪律：

1. **缺失不回填。** 响应没报模型就是 ``unreported``，不许拿 ``requested_model``
   或当前环境配置补上。两个陌生字符串不相等也不算异构——家族解析只认显式支持表，
   认不出就是 unknown（``resolve_family``）。
2. **失效是拦结论，不是删证据。** 任何一项不过，整批组件决定降 ``no_call``，
   但分差、覆盖率、失败尝试原样保留。删掉难看的记录不能换来更好的资格。
3. **``now`` 只用于 open 批次准入。** 已封存的收据日后再读，按它**当时**的调用
   时间判断，不与今天的墙钟比而自动过期（§3.2）。

响应自报身份只支持「按对端声明相同/不同」这一档审计强度，**不等于已认证真实
模型**，也不保证跨家族的偏差统计独立。
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

# --------------------------------------------------------------------------- #
# 版本与常量
# --------------------------------------------------------------------------- #

#: 本模块能出结论的收据版本。未知版本一律拒绝出结论（§3.3-1）。
SUPPORTED_SCHEMA_VERSIONS = frozenset({2})
#: 旧版可读、可展示，但不能取得资格。
DISPLAY_ONLY_SCHEMA_VERSIONS = frozenset({1})

#: 与 ``run_quality_ablation.CALIBRATION_MIN_REPEATS`` 同值。**这里重声明而不 import**：
#: 本模块不许依赖 scripts/services，两处若要改必须一起改，故在下方 _recompute 的
#: docstring 里写明公式出处，让漂移在 review 时可见。
CALIBRATION_MIN_REPEATS = 2
#: §3.3-4：至少两份**不同**基线文本，每份至少两次评分。
CALIBRATION_MIN_TEXTS = 2

#: 身份采集状态（§3.1），与 status=success/failed 正交。
IDENTITY_NOT_CALLED = "not_called"
IDENTITY_UNREPORTED = "unreported"
IDENTITY_REPORTED = "reported"

#: 家族映射的显式支持表版本。别名兼容映射必须事前冻结，缺失或冲突不在运行时猜测
#: （§3.2）。改这张表 = 改版本号，``judge_spec`` 里记的就是这个号。
FAMILY_TABLE_VERSION = "2026-09-14"
_FAMILY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("gpt-", "openai"),
    ("o1-", "openai"),
    ("o3-", "openai"),
    ("openai/", "openai"),
    ("claude-", "anthropic"),
    ("anthropic/", "anthropic"),
    ("grok-", "xai"),
    ("xai/", "xai"),
    ("judge/grok", "xai"),
    ("judge/gpt", "openai"),
    ("deepseek", "deepseek"),
    ("qwen", "qwen"),
    ("glm", "zhipu"),
    ("zhipu", "zhipu"),
    ("gemini", "google"),
    ("google/", "google"),
)
#: 支持表认得的全部家族名。``writer_provenance.families`` 存的是**家族名**（已归一），
#: 不是模型名——所以它按这张集合校验，不要再过一遍 ``resolve_family``。
KNOWN_FAMILIES = frozenset(family for _, family in _FAMILY_PREFIXES)

# --------------------------------------------------------------------------- #
# 原因码
# --------------------------------------------------------------------------- #

REASON_SCHEMA_UNSUPPORTED = "schema_unsupported"
REASON_MANIFEST_MISMATCH = "manifest_mismatch"
REASON_ANSWER_BINDING_MISMATCH = "answer_binding_mismatch"
REASON_JUDGE_IDENTITY_UNKNOWN = "judge_identity_unknown"
REASON_JUDGE_IDENTITY_MISMATCH = "judge_identity_mismatch"
REASON_JUDGE_SPEC_MISMATCH = "judge_spec_mismatch"
REASON_WRITER_IDENTITY_UNKNOWN = "writer_identity_unknown"
REASON_JUDGE_NOT_INDEPENDENT = "judge_not_independent"
REASON_CALIBRATION_BINDING_MISMATCH = "calibration_binding_mismatch"
REASON_CALIBRATION_INCOMPLETE = "calibration_incomplete"
REASON_CALIBRATION_STALE = "calibration_stale"
REASON_NOISE_FLOOR_INVALID = "noise_floor_invalid"
REASON_COVERAGE_INCOMPLETE = "coverage_incomplete"
REASON_BATCH_STATE_INVALID = "batch_state_invalid"
REASON_BATCH_EXPIRED = "batch_expired"


# --------------------------------------------------------------------------- #
# 规范哈希
# --------------------------------------------------------------------------- #


def canonical_json(payload: object) -> str:
    """规范 JSON：UTF-8、键排序、固定 separators、``allow_nan=False``（§3.2）。

    ``allow_nan=False`` 是要点而不是洁癖：``json`` 默认会把 NaN/Infinity 写成
    裸字面量再原样读回来，于是一个非有限的噪声参数可以**一路哈希一致地**穿过
    所有绑定校验。让它在序列化这一步就炸。
    """

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(payload: object) -> str:
    """规范 JSON 的 sha256。生成时间与秘密配置不得进入被哈希的对象（§3.2）。"""

    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def judge_spec_sha256(spec: Mapping[str, object]) -> str:
    """从 ``judge_spec`` 的**有效值**派生哈希。

    rubric 标签不变而正文/temperature/截断规则改了一项，就是另一套评分口径
    （验收 V5）——所以哈希吃的是整份 spec，不是它的标签。
    """

    return canonical_sha256(dict(spec))


def resolve_family(model: object) -> str | None:
    """按显式支持表解析模型家族；认不出返回 ``None``（= unknown，不是「异构」）。

    **不能用两个陌生字符串不相等就判异构**（§3.1）：``judge-a`` 与 ``judge-b``
    完全可能是同一个后端的两个别名，判成独立会让独立性校验形同虚设。
    """

    if not isinstance(model, str) or not model.strip():
        return None
    needle = model.strip().lower()
    for prefix, family in _FAMILY_PREFIXES:
        if needle.startswith(prefix) or f"/{prefix}" in needle:
            return family
    return None


# --------------------------------------------------------------------------- #
# 结果类型
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BatchValidity:
    """资格判定结果。``valid=False`` 时调用方必须把组件决定降为 ``no_call``。

    ``reason_codes`` 去重且按首次触发顺序排列——诊断时要看**最先**是哪一步塌的。
    """

    valid: bool
    reason_codes: tuple[str, ...] = ()
    invalid_answer_ids: tuple[str, ...] = ()
    #: 描述性统计：即使 valid=False 也要能报出来（§3.3 末段）
    counts: Mapping[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "reason_codes": list(self.reason_codes),
            "invalid_answer_ids": list(self.invalid_answer_ids),
            "counts": dict(self.counts),
        }


class _Collector:
    """按首次触发顺序收原因码，并记下被点名的 answer_id。"""

    def __init__(self) -> None:
        self._codes: list[str] = []
        self._answers: list[str] = []

    def add(self, code: str, answer_id: object = None) -> None:
        if code not in self._codes:
            self._codes.append(code)
        if answer_id is not None:
            aid = str(answer_id)
            if aid not in self._answers:
                self._answers.append(aid)

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(self._codes)

    @property
    def answers(self) -> tuple[str, ...]:
        return tuple(self._answers)


# --------------------------------------------------------------------------- #
# 各步校验
# --------------------------------------------------------------------------- #


def _schema_of(payload: Mapping[str, object]) -> object:
    return payload.get("schema_version")


def _parse_ts(value: object) -> datetime | None:
    """显式解析 ISO 时间戳；解析不了返回 None（调用方按缺失处理，不猜）。"""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _finite(value: object) -> bool:
    """有限实数才算数：NaN / Infinity / 非数 / bool 全判否。

    ``bool`` 单独排除是因为 ``isinstance(True, int)`` 为真——一个 ``True`` 能
    悄悄当成 sigma=1 用。
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _check_schema_and_manifest(
    answers: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
    out: _Collector,
    *,
    now: datetime | None,
) -> bool:
    """§3.3-1：版本、题臂唯一性与完整性、答案绑定、批次封存状态。

    返回 False 表示结构已经塌到无法继续后续检查（后面几步会读到无意义的字段）。
    """

    run_manifest = manifest.get("run_manifest")
    answer_manifest = manifest.get("answer_manifest")
    if not isinstance(run_manifest, Mapping) or not isinstance(answer_manifest, Mapping):
        out.add(REASON_MANIFEST_MISMATCH)
        return False

    for payload in (run_manifest, answer_manifest):
        if _schema_of(payload) not in SUPPORTED_SCHEMA_VERSIONS:
            out.add(REASON_SCHEMA_UNSUPPORTED)
            return False

    # answer_manifest 引用 run_manifest 的哈希：事后改事前计划要能被发现（§3.2）
    if answer_manifest.get("run_manifest_sha256") != canonical_sha256(dict(run_manifest)):
        out.add(REASON_MANIFEST_MISMATCH)

    # 批次生命周期与期限。now 只在 open 批次上用（§3.2）。
    state = str(answer_manifest.get("state") or "")
    if state not in {"open", "sealed"}:
        out.add(REASON_BATCH_STATE_INVALID)
    expires_at = _parse_ts(run_manifest.get("expires_at"))
    if state == "open":
        if expires_at is None:
            out.add(REASON_BATCH_STATE_INVALID)
        elif now is not None and now > expires_at:
            out.add(REASON_BATCH_EXPIRED)

    # 预登记题臂 vs 实际交付：删行、改 arm、重复 case 都不能换来更好的资格
    registered: set[tuple[str, str]] = set()
    for case in run_manifest.get("cases") or []:
        if not isinstance(case, Mapping):
            out.add(REASON_MANIFEST_MISMATCH)
            continue
        cid = str(case.get("case_id"))
        for arm in case.get("arms") or []:
            registered.add((cid, str(arm)))

    seen: set[tuple[str, str]] = set()
    expected_hashes = answer_manifest.get("answer_sha256_by_id")
    expected_hashes = expected_hashes if isinstance(expected_hashes, Mapping) else {}
    for rec in answers:
        key = (str(rec.get("case_id")), str(rec.get("arm")))
        if key in seen:  # 重复 case/arm
            out.add(REASON_MANIFEST_MISMATCH, rec.get("answer_id"))
        seen.add(key)
        if key not in registered:  # 改 arm / 凭空多出来的行
            out.add(REASON_MANIFEST_MISMATCH, rec.get("answer_id"))
        aid = str(rec.get("answer_id") or "")
        if aid not in expected_hashes:
            out.add(REASON_ANSWER_BINDING_MISMATCH, aid or None)
        elif expected_hashes[aid] != rec.get("answer_sha256"):
            out.add(REASON_ANSWER_BINDING_MISMATCH, aid)
        # 存储、评分两处分别验证：防「原答案没变但实际送评文本换了」（§3.2）
        if not str(rec.get("judge_input_sha256") or "").strip():
            out.add(REASON_ANSWER_BINDING_MISMATCH, aid or None)

    if registered - seen:  # 删行
        out.add(REASON_MANIFEST_MISMATCH)
    return True


def _successful_attempt(rec: Mapping[str, object], attempt_id: object) -> Mapping[str, object] | None:
    """在该条记录的 attempts 里定位唯一一次成功尝试。

    失败重试也保留在 attempts 里；**任何已返回成功内容的未知/冲突身份不能因为
    后续 JSON 解析失败被丢掉，然后继续声称这批兼容**（§3.3-2）。
    """

    if attempt_id is None:
        return None
    hits = [
        a
        for a in (rec.get("attempts") or [])
        if isinstance(a, Mapping)
        and a.get("attempt_id") == attempt_id
        and a.get("status") == "success"
    ]
    return hits[0] if len(hits) == 1 else None


def _check_judge_identity(
    answers: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
    out: _Collector,
) -> None:
    """§3.3-2 与 §3.3-3：评分身份、规格一致、与源 writer 的独立性。"""

    run_manifest = manifest.get("run_manifest") or {}
    spec = run_manifest.get("judge_spec") if isinstance(run_manifest, Mapping) else None
    expected_spec_sha = (
        run_manifest.get("judge_spec_sha256") if isinstance(run_manifest, Mapping) else None
    )
    if isinstance(spec, Mapping) and judge_spec_sha256(spec) != expected_spec_sha:
        out.add(REASON_JUDGE_SPEC_MISMATCH)
    allowed = {
        str(m).strip().lower()
        for m in (spec.get("allowed_reported_models") or [] if isinstance(spec, Mapping) else [])
    }

    judge_families: set[str] = set()
    for rec in answers:
        judge = rec.get("judge")
        if not isinstance(judge, Mapping) or not judge.get("scored"):
            continue
        aid = rec.get("answer_id")
        if judge.get("judge_spec_sha256") != expected_spec_sha:
            out.add(REASON_JUDGE_SPEC_MISMATCH, aid)
        ref = judge.get("attempt_ref")
        ref = ref if isinstance(ref, Mapping) else {}
        attempt = _successful_attempt(rec, ref.get("attempt_id"))
        if attempt is None:
            # 定位不到唯一成功 attempt：这条分数没有可追溯的身份
            out.add(REASON_JUDGE_IDENTITY_UNKNOWN, aid)
            continue
        if attempt.get("identity_state") != IDENTITY_REPORTED:
            out.add(REASON_JUDGE_IDENTITY_UNKNOWN, aid)
            continue
        reported = str(attempt.get("reported_model") or "").strip().lower()
        if not reported:
            out.add(REASON_JUDGE_IDENTITY_UNKNOWN, aid)
            continue
        if allowed and reported not in allowed:
            # 配置没变、响应换了模型（验收 V1）
            out.add(REASON_JUDGE_IDENTITY_MISMATCH, aid)
        family = resolve_family(reported)
        if family is None:
            out.add(REASON_JUDGE_IDENTITY_UNKNOWN, aid)
        else:
            judge_families.add(family)

    if len(judge_families) > 1:
        # 同一批次里不同家族打分：彼此不兼容
        out.add(REASON_JUDGE_IDENTITY_MISMATCH)

    # 独立性：判官家族必须与源 writer 的**全部已知贡献家族**都不同
    for rec in answers:
        judge = rec.get("judge")
        if not isinstance(judge, Mapping) or not judge.get("scored"):
            continue
        prov = rec.get("writer_provenance")
        aid = rec.get("answer_id")
        if not isinstance(prov, Mapping):
            out.add(REASON_WRITER_IDENTITY_UNKNOWN, aid)
            continue
        if prov.get("unknown"):
            out.add(REASON_WRITER_IDENTITY_UNKNOWN, aid)
            continue
        raw = prov.get("families")
        if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
            out.add(REASON_WRITER_IDENTITY_UNKNOWN, aid)
            continue
        writer_families = {str(f).strip().lower() for f in raw if str(f).strip()}
        # 空集合、或含支持表认不出的家族 → unknown。**不能因为「两个名字不一样」
        # 就当成异构**：陌生名字可能正是判官的别名（§3.1）。
        if not writer_families or not writer_families <= KNOWN_FAMILIES:
            out.add(REASON_WRITER_IDENTITY_UNKNOWN, aid)
            continue
        if judge_families & writer_families:
            out.add(REASON_JUDGE_NOT_INDEPENDENT, aid)


def _recompute_noise_floor(
    totals_by_text: Mapping[str, Sequence[float]]
) -> tuple[float, float] | None:
    """按 ``run_quality_ablation.judge_noise_floor`` 的同一公式重算。

    公式在那边（``scripts/run_quality_ablation.py::judge_noise_floor``）：
    组内样本方差 → 跨文本取均值 → 开方 = ``sd_judging``；
    ``sd_delta_single_question = sd_judging × √2``，四舍五入 4 位。

    **这里刻意重写而不 import**：本模块不得依赖 scripts。代价是两份公式可能漂，
    所以重算值与收据里的存量值要逐位核对——漂了会在 V8 那组测试上直接见红。
    """

    variances = [
        statistics.variance(list(totals))
        for totals in totals_by_text.values()
        if len(totals) >= CALIBRATION_MIN_REPEATS
    ]
    if not variances:
        return None
    sd_judging = math.sqrt(statistics.fmean(variances))
    return round(sd_judging, 4), round(sd_judging * math.sqrt(2), 4)


def _check_calibration(
    calibration: Mapping[str, object],
    manifest: Mapping[str, object],
    out: _Collector,
) -> None:
    """§3.3-4 与 §3.3-5：校准绑定、完整性、噪声参数重算。"""

    run_manifest = manifest.get("run_manifest") or {}
    answer_manifest = manifest.get("answer_manifest") or {}
    if not isinstance(run_manifest, Mapping) or not isinstance(answer_manifest, Mapping):
        out.add(REASON_CALIBRATION_BINDING_MISMATCH)
        return
    if not isinstance(calibration, Mapping) or not calibration:
        out.add(REASON_CALIBRATION_INCOMPLETE)
        return

    # 绑定：同一批次、同一有效规格（验收 V6 / V3）
    if calibration.get("batch_id") != run_manifest.get("batch_id"):
        out.add(REASON_CALIBRATION_BINDING_MISMATCH)
    if calibration.get("judge_spec_sha256") != run_manifest.get("judge_spec_sha256"):
        # 规格换了还想沿用旧底 = 补评换判官那条路（验收 V3）
        out.add(REASON_CALIBRATION_STALE)

    plan = run_manifest.get("calibration_plan")
    plan = plan if isinstance(plan, Mapping) else {}
    planned_texts = [str(t) for t in (plan.get("texts") or [])]
    repeats_per_text = plan.get("repeats_per_text")
    if len(set(planned_texts)) < CALIBRATION_MIN_TEXTS or not isinstance(repeats_per_text, int):
        out.add(REASON_CALIBRATION_INCOMPLETE)
    if isinstance(repeats_per_text, int) and repeats_per_text < CALIBRATION_MIN_REPEATS:
        out.add(REASON_CALIBRATION_INCOMPLETE)

    known_texts = answer_manifest.get("calibration_texts")
    known_texts = known_texts if isinstance(known_texts, Mapping) else {}

    totals_by_text: dict[str, list[float]] = {}
    for rep in calibration.get("repeats") or []:
        if not isinstance(rep, Mapping):
            out.add(REASON_CALIBRATION_INCOMPLETE)
            continue
        text_id = str(rep.get("text_id") or "")
        # 同一文本：文本哈希必须与事前封存的一致，否则「重复评分」评的不是同一份
        if known_texts.get(text_id) != rep.get("text_sha256"):
            out.add(REASON_CALIBRATION_BINDING_MISMATCH)
            continue
        total = rep.get("total")
        if not _finite(total):
            out.add(REASON_NOISE_FLOOR_INVALID)
            continue
        totals_by_text.setdefault(text_id, []).append(float(total))

    # 计划里的重复最终缺失 → incomplete。不看分数后挑剩余成功样本重新凑底（§3.3-4）
    for text_id in planned_texts:
        got = len(totals_by_text.get(text_id, []))
        if isinstance(repeats_per_text, int) and got < repeats_per_text:
            out.add(REASON_CALIBRATION_INCOMPLETE)

    floor = calibration.get("noise_floor")
    if not isinstance(floor, Mapping) or not floor.get("measured"):
        out.add(REASON_NOISE_FLOOR_INVALID)
        return

    sigma = floor.get("sigma")
    stored_sd_delta = floor.get("sd_delta_single_question")
    # 缺字段 / NaN / Infinity / 负值均无效；**不许用 `or 0.0` 变成零噪声**（§3.3-5）
    if not _finite(sigma) or float(sigma) <= 0:
        out.add(REASON_NOISE_FLOOR_INVALID)
    if not _finite(stored_sd_delta) or float(stored_sd_delta) < 0:
        out.add(REASON_NOISE_FLOOR_INVALID)
        return

    recomputed = _recompute_noise_floor(totals_by_text)
    if recomputed is None:
        out.add(REASON_NOISE_FLOOR_INVALID)
        return
    _, sd_delta = recomputed
    # 真实零方差（同文本重复恰好同分）是合法的，不过度拦截；但它必须是**重算出来**
    # 的零，而不是字段缺失被当成零。
    if abs(sd_delta - float(stored_sd_delta)) > 1e-9:
        out.add(REASON_NOISE_FLOOR_INVALID)


def _check_coverage(
    answers: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
    out: _Collector,
) -> dict[str, int]:
    """§3.3-6：预登记题臂全部有有效评分，才允许该批次质量分差进入判定。

    **产品失败仍留在端到端分母**，不能通过身份门重归因为实验条件失效——所以这里
    只拦「结论」，counts 里的交付/失败数照报。
    """

    run_manifest = manifest.get("run_manifest") or {}
    registered = 0
    if isinstance(run_manifest, Mapping):
        for case in run_manifest.get("cases") or []:
            if isinstance(case, Mapping):
                registered += len(case.get("arms") or [])

    delivered = 0
    scored = 0
    failed_attempts = 0
    for rec in answers:
        if rec.get("ok"):
            delivered += 1
        judge = rec.get("judge")
        if isinstance(judge, Mapping) and judge.get("scored"):
            scored += 1
        failed_attempts += sum(
            1
            for a in (rec.get("attempts") or [])
            if isinstance(a, Mapping) and a.get("status") == "failed"
        )

    if registered and scored < registered:
        out.add(REASON_COVERAGE_INCOMPLETE)
    return {
        "registered_arms": registered,
        "answers_present": len(answers),
        "delivered": delivered,
        "scored": scored,
        "failed_attempts": failed_attempts,
    }


# --------------------------------------------------------------------------- #
# 唯一资格门
# --------------------------------------------------------------------------- #


def validate_judging_batch(
    answers: Sequence[Mapping[str, object]],
    calibration: Mapping[str, object],
    manifest: Mapping[str, object],
    *,
    now: datetime | None = None,
) -> BatchValidity:
    """唯一资格门：这批评分能不能拿去下实验结论。

    ``aggregate_components`` **每次调用都要重跑本函数**，不能只相信传进来的
    ``valid=True`` 或收据里的旧 ``decision``（§3.3）——上游把结论缓存进字段，
    门就等于没有。

    参数
    ----
    answers
        v2 答案记录序列，每条带 ``answer_id / case_id / arm / answer_sha256 /
        judge_input_sha256 / writer_provenance / judge / attempts``。
    calibration
        校准收据：``batch_id / judge_spec_sha256 / repeats[] / noise_floor``。
        ``repeats`` 保留每次完整 verdict 与成功 attempt 引用，**不是只存 totals**。
    manifest
        ``{"run_manifest": ..., "answer_manifest": ...}``，已绑定的事前计划。
    now
        仅用于 open 批次的期限准入。sealed 收据不与今天的墙钟比较（§3.2）。

    返回
    ----
    :class:`BatchValidity`。``valid=False`` 时调用方保留描述性分差与覆盖率，
    但组件决定必须降 ``no_call``。``decision=callable`` 只表示越过当次判官噪声门，
    **不自动授权合并，也不证明跨任务或未来效果**。
    """

    out = _Collector()
    structural_ok = _check_schema_and_manifest(answers, manifest, out, now=now)
    if not structural_ok:
        # 结构已塌：后面几步会读到无意义的字段，报出来的原因码只会误导诊断
        return BatchValidity(False, out.codes, out.answers, {"answers_present": len(answers)})

    _check_judge_identity(answers, manifest, out)
    _check_calibration(calibration, manifest, out)
    counts = _check_coverage(answers, manifest, out)

    return BatchValidity(
        valid=not out.codes,
        reason_codes=out.codes,
        invalid_answer_ids=out.answers,
        counts=counts,
    )
