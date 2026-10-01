"""生效模型准入：这轮读数用的是不是它声称测的那个模型。

spec ``docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md``
§3.5.4 硬门 3 写的是两件事：逐 model turn 落盘响应体 ``model``，**并与请求的模型名
比对**；「四条缺一条，该轮读数作废」。落盘那半早已做完（``ModelTurn.served_model``，
见 ``intelligence/tests/test_served_model_receipt.py``）；比对那半一直靠人眼——
2026-09-29 的 GLM 重写消融就是事后才发现实际模型是 ``glm-5.3-flash`` 而不是预设的
``glm-5.3``（``docs/handoffs/2026-09-29-8792-answer-capability-lines-map.md``，其「下一步」
第 1 条：先钉住模型准入，钉不住就阻塞、不跑）。

本模块把比对做成机器判定。只读、只用标准库、不发任何请求。

判定（fail-closed，证明不了就不许当读数用）：

* ``admitted``   ：每个带回的生效模型都在期望集合里，且（默认）没有「未回」；
* ``mismatch``   ：出现任何期望集合之外的生效模型——该轮读数作废；
* ``no_evidence``：一个带回的生效模型都没有、产物读不了/找不到，或（默认）有 turn
  标了「未回」。``allow_unreported=True`` 时只要有匹配证据且无错配，「未回」只计数
  不拦——这是显式放宽，调用方要在命令行上写出来。

三态沿用 ``ModelTurn.served_model``：键缺失或 ``None`` = 回合没到 provider（只计数）；
``""`` = provider 回了响应但没带 model（记「未回」）；非空 = 对端实际服务的模型。
**永不**拿配置值回填——那正是 §3.5.4 要防的事故。

认得的产物：

* ``continuous-episode.json``（run 目录产物，``events`` = ``{sequence, kind, payload}``）；
* ``events.jsonl``（``JsonlEpisodeStore``，每行一个同形事件）；
* 其它 JSON / JSONL：退回按键名 ``served_model`` / ``served_models`` 递归收集。

事件里取证的位置：``model_turn`` / ``branch_completed`` 的 ``served_model``（continuous
臂），``model_turn`` / ``runtime_result`` 的 ``served_models`` 列表（SDK 臂，逐响应自报）。

子分支（2026-10-01 审查复现「父对、子错，准入照样通过」后补上）：``sub_research`` 分支
自己的 model turn 记在各自的分支 episode 里，父产物只有 ``branch_completed`` /
``branch_failed``。现在两条路取证：

1. 分支把每轮生效模型带回父事件：``payload.served_models``（``branch_telemetry``）；
2. 老产物没有这个键时，按 ``episode_ref.episode_id`` 去 episode store
   （``<store>/<目录名>/events.jsonl``，目录名规则同 ``episode_store._directory_name``）
   读分支自己的 ``model_turn``。

两条都拿不到、而分支调用过模型或调用账未知 → 判「无证据」，**不再放行**。
worker 异常会丢失返回的调用账，不能把占位 ``llm_calls=0`` 当成没调用；新产物用
``llm_calls_known=False`` 标明，老产物按异常终局识别。启动前取消 / 存储失败的
分支仍有可信的零调用账，不需要模型证据。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

EPISODE_FILENAME = "continuous-episode.json"
EVENTS_FILENAME = "events.jsonl"
ARTIFACT_FILENAMES = (EPISODE_FILENAME, EVENTS_FILENAME)

VERDICT_ADMITTED = "admitted"
VERDICT_MISMATCH = "mismatch"
VERDICT_NO_EVIDENCE = "no_evidence"
EXIT_CODES = {VERDICT_ADMITTED: 0, VERDICT_MISMATCH: 1, VERDICT_NO_EVIDENCE: 2}

_SERVED_MODEL_KINDS = frozenset({"model_turn", "branch_completed"})
_SERVED_MODELS_KINDS = frozenset({"model_turn", "runtime_result", "branch_completed", "branch_failed"})
_BRANCH_KINDS = frozenset({"branch_completed", "branch_failed"})
# 与 ``intelligence.services.episode_store._directory_name`` 同一规则（本模块只用标准库，
# 抄一份；``tests/test_model_admission_branches.py`` 钉住两边逐字一致）。
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def episode_directory_name(episode_id: str) -> str:
    safe = _UNSAFE_NAME.sub("_", episode_id)
    if safe == episode_id:
        return safe
    digest = hashlib.sha256(episode_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe}-{digest}"


def normalize_model(name: object) -> str:
    """大小写与空白不算不同模型；其余一个字符都不放过（``-flash`` 就是另一个模型）。"""

    return " ".join(str(name).split()).casefold()


@dataclass
class ServedModelEvidence:
    source: str
    served: dict[str, int] = field(default_factory=dict)
    unreported: int = 0
    not_reached: int = 0
    error: str | None = None
    # 调用过模型、却没带回生效模型的子分支（等 episode store 补证；补不上就判无证据）。
    branch_unproven: int = 0
    branch_refs: list[str] = field(default_factory=list)

    def add(self, value: object) -> None:
        if value is None:
            self.not_reached += 1
            return
        if not isinstance(value, str):
            # 形状坏了不是「未回」也不是某个模型；当读不懂处理，免得被误当证据。
            self.error = self.error or f"served_model 不是字符串：{type(value).__name__}"
            return
        name = normalize_model(value)
        if not name:
            self.unreported += 1
        else:
            self.served[name] = self.served.get(name, 0) + 1


@dataclass(frozen=True)
class AdmissionResult:
    source: str
    verdict: str
    expected: tuple[str, ...]
    served: dict[str, int]
    unexpected: dict[str, int]
    unreported: int
    not_reached: int
    reason: str
    branch_unproven: int = 0

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "verdict": self.verdict,
            "expected": list(self.expected),
            "served": dict(self.served),
            "unexpected": dict(self.unexpected),
            "unreported": self.unreported,
            "not_reached": self.not_reached,
            "branch_unproven": self.branch_unproven,
            "reason": self.reason,
        }


def _is_event(record: object) -> bool:
    return isinstance(record, Mapping) and "kind" in record and isinstance(
        record.get("payload"), Mapping
    )


def collect_from_events(events: Iterable[object], source: str) -> ServedModelEvidence:
    evidence = ServedModelEvidence(source)
    for event in events:
        if not _is_event(event):
            continue
        assert isinstance(event, Mapping)
        kind = event.get("kind")
        payload = event["payload"]
        has_single = kind in _SERVED_MODEL_KINDS and "served_model" in payload
        has_list = kind in _SERVED_MODELS_KINDS and isinstance(payload.get("served_models"), list)
        if has_single:
            evidence.add(payload.get("served_model"))
        if has_list:
            for item in payload["served_models"]:
                evidence.add(item)
        if kind == "model_turn" and not has_single and not has_list:
            evidence.not_reached += 1
        if kind in _BRANCH_KINDS and not has_single and not (has_list and payload["served_models"]):
            calls = payload.get("llm_calls")
            error = str(payload.get("error") or "")
            # 兼容标志加入前的产物：协调器异常出口没有 stop_reason；启动前
            # 的 storage_failed 早退则有同名 stop_reason，且确实尚未调用 worker。
            legacy_worker_failure = kind == "branch_failed" and (
                error.startswith("branch_worker_exception:")
                or (error == "storage_failed" and not payload.get("stop_reason"))
            )
            called = (isinstance(calls, int) and not isinstance(calls, bool) and calls > 0) or (
                kind == "branch_completed" and calls is None
            )
            if called or payload.get("llm_calls_known") is False or legacy_worker_failure:
                evidence.branch_unproven += 1
                ref = payload.get("episode_ref")
                episode_id = ref.get("episode_id") if isinstance(ref, Mapping) else None
                if isinstance(episode_id, str) and episode_id:
                    evidence.branch_refs.append(episode_id)
    return evidence


def _merge(into: ServedModelEvidence, other: ServedModelEvidence) -> None:
    for name, count in other.served.items():
        into.served[name] = into.served.get(name, 0) + count
    into.unreported += other.unreported
    into.not_reached += other.not_reached
    into.error = into.error or other.error
    into.branch_unproven += other.branch_unproven
    into.branch_refs.extend(other.branch_refs)


def resolve_branches(evidence: ServedModelEvidence, episode_store: Path | None) -> ServedModelEvidence:
    """老产物的子分支：去 episode store 读分支自己的 model_turn；读到一支就销一支「未证」。"""

    if episode_store is None or not evidence.branch_refs:
        return evidence
    pending = list(evidence.branch_refs)
    evidence.branch_refs = []
    for episode_id in pending:
        path = episode_store / episode_directory_name(episode_id) / EVENTS_FILENAME
        if not path.is_file():
            evidence.branch_refs.append(episode_id)
            continue
        branch = load_evidence(path)
        if branch.error or not (branch.served or branch.unreported):
            evidence.branch_refs.append(episode_id)
            continue
        evidence.branch_unproven -= 1
        _merge(evidence, branch)
    return evidence


def _walk(node: object, evidence: ServedModelEvidence) -> None:
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key == "served_model":
                evidence.add(value)
            elif key == "served_models" and isinstance(value, list):
                for item in value:
                    evidence.add(item)
            else:
                _walk(value, evidence)
    elif isinstance(node, list):
        for item in node:
            _walk(item, evidence)


def collect_from_document(document: object, source: str) -> ServedModelEvidence:
    """一个已解析的产物：认得 episode 形状就按事件取证，否则按键名递归兜底。"""

    if isinstance(document, Mapping) and isinstance(document.get("events"), list):
        return collect_from_events(document["events"], source)
    if isinstance(document, list) and document and all(_is_event(item) for item in document):
        return collect_from_events(document, source)
    evidence = ServedModelEvidence(source)
    _walk(document, evidence)
    return evidence


def load_evidence(path: Path, episode_store: Path | None = None) -> ServedModelEvidence:
    source = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ServedModelEvidence(source, error=f"读不了：{type(exc).__name__}")
    try:
        if path.suffix == ".jsonl":
            document: object = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            document = json.loads(text)
    except ValueError as exc:
        return ServedModelEvidence(source, error=f"不是合法 JSON：{exc}")
    return resolve_branches(collect_from_document(document, source), episode_store)


def resolve_artifacts(paths: Iterable[str | Path]) -> tuple[list[Path], list[str]]:
    """文件原样收；目录先看自身有没有产物文件，没有再递归找。找不到的单列出来。"""

    found: list[Path] = []
    missing: list[str] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_file():
            found.append(path)
            continue
        if not path.is_dir():
            missing.append(str(path))
            continue
        direct = [path / name for name in ARTIFACT_FILENAMES if (path / name).is_file()]
        if direct:
            found.extend(direct)
            continue
        hits = sorted(
            hit for name in ARTIFACT_FILENAMES for hit in path.rglob(name) if hit.is_file()
        )
        if hits:
            found.extend(hits)
        else:
            missing.append(str(path))
    return found, missing


def _fmt_counts(counts: Mapping[str, int]) -> str:
    return "、".join(f"{name}×{count}" for name, count in sorted(counts.items()))


def judge(
    evidence: ServedModelEvidence,
    expected: Iterable[str],
    *,
    allow_unreported: bool = False,
) -> AdmissionResult:
    expected_norm = tuple(sorted({normalize_model(item) for item in expected} - {""}))
    if not expected_norm:
        raise ValueError("至少要给一个期望模型")

    def result(verdict: str, reason: str, unexpected: Mapping[str, int] | None = None):
        return AdmissionResult(
            source=evidence.source,
            verdict=verdict,
            expected=expected_norm,
            served=dict(evidence.served),
            unexpected=dict(unexpected or {}),
            unreported=evidence.unreported,
            not_reached=evidence.not_reached,
            reason=reason,
            branch_unproven=evidence.branch_unproven,
        )

    unexpected = {
        name: count for name, count in evidence.served.items() if name not in expected_norm
    }
    if unexpected:
        # 错配优先于「读不懂」：只要看到一次别的模型，这轮就已经作废了。
        return result(
            VERDICT_MISMATCH,
            f"实际服务了期望之外的模型：{_fmt_counts(unexpected)}（期望 {' / '.join(expected_norm)}）",
            unexpected,
        )
    if evidence.error:
        return result(VERDICT_NO_EVIDENCE, evidence.error)
    if evidence.branch_unproven:
        return result(
            VERDICT_NO_EVIDENCE,
            f"{evidence.branch_unproven} 个子分支调用过模型，但父产物没带回它们的生效模型，"
            "episode store 里也没找到分支事件（--episode-store 指向分支 episode 所在目录）——"
            "证明不了分支用的是哪个模型",
        )
    if not evidence.served:
        return result(
            VERDICT_NO_EVIDENCE,
            f"没有任何 turn 带回生效模型（未回 {evidence.unreported}，"
            f"未到 provider {evidence.not_reached}），证明不了用的是哪个模型",
        )
    if evidence.unreported and not allow_unreported:
        return result(
            VERDICT_NO_EVIDENCE,
            f"{evidence.unreported} 个 turn 未回 model，证明不了全程是期望模型"
            "（确认可以接受时显式加 --allow-unreported）",
        )
    note = f"，另有未回 {evidence.unreported}（已显式放行）" if evidence.unreported else ""
    return result(VERDICT_ADMITTED, f"带回的生效模型全部符合：{_fmt_counts(evidence.served)}{note}")


def check_paths(
    paths: Iterable[str | Path],
    expected: Iterable[str],
    *,
    allow_unreported: bool = False,
    episode_store: str | Path | None = None,
) -> list[AdmissionResult]:
    expected = tuple(expected)
    store = Path(episode_store).expanduser() if episode_store else None
    found, missing = resolve_artifacts(paths)
    results = [
        judge(load_evidence(path, store), expected, allow_unreported=allow_unreported)
        for path in found
    ]
    for source in missing:
        results.append(
            judge(ServedModelEvidence(source, error="找不到产物文件"), expected)
        )
    return results


def overall_exit_code(results: Iterable[AdmissionResult]) -> int:
    """任何错配 → 1；否则任何无证据（或一个产物都没有）→ 2；全部准入 → 0。"""

    verdicts = [item.verdict for item in results]
    if VERDICT_MISMATCH in verdicts:
        return EXIT_CODES[VERDICT_MISMATCH]
    if not verdicts or VERDICT_NO_EVIDENCE in verdicts:
        return EXIT_CODES[VERDICT_NO_EVIDENCE]
    return EXIT_CODES[VERDICT_ADMITTED]
