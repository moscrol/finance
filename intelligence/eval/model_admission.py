"""生效模型准入：这轮读数用的是不是它声称测的那个模型。

spec ``docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md``
§3.5.4 硬门 3 写的是两件事：逐 model turn 落盘响应体 ``model``，**并与请求的模型名
比对**；「四条缺一条，该轮读数作废」。落盘那半早已做完（``ModelTurn.served_model``，
见 ``intelligence/tests/test_served_model_receipt.py``）；比对那半一直靠人眼——
2026-09-29 的 GLM 重写消融就是事后才发现实际模型是 ``glm-5.3-flash`` 而不是预设的
``glm-5.3``（``docs/handoffs/2026-09-29-8792-answer-capability-lines-map.md``，其「下一步」
第 1 条：先钉住模型准入，钉不住就阻塞、不跑）。

本模块把比对做成机器判定。只读、不发任何请求；子分支地址复用生产 JsonlEpisodeStore。

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

子分支：目录始终递归，不因发现父产物就停止；每个 episode_ref 必须追到子产物。
读 events.jsonl 时自动在同一 store 找兄弟分支；公开 run 产物需显式传 episode_store_roots。
缺失、坏引用、环路都判无证据，绝不凭父运行模型正确放行整个运行。
"""

from __future__ import annotations

import json
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
_SERVED_MODELS_KINDS = frozenset({"model_turn", "runtime_result"})


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


def load_evidence(path: Path) -> ServedModelEvidence:
    source = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return ServedModelEvidence(source, error=f"读不了：{type(exc).__name__}")
    try:
        if path.suffix == ".jsonl":
            document: object = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            document = json.loads(text)
    except ValueError as exc:
        return ServedModelEvidence(source, error=f"不是合法 JSON：{exc}")
    return collect_from_document(document, source)


def resolve_artifacts(paths: Iterable[str | Path]) -> tuple[list[Path], list[str]]:
    """文件原样收；目录始终递归查找，包括已含父产物的目录。找不到的单列出来。"""

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


def _episode_references(path: Path) -> tuple[list[str], list[str]]:
    """递归读引用（包括 tool telemetry）；不把配置中的 model 当证据。"""

    try:
        text = path.read_text(encoding="utf-8")
        doc = ([json.loads(line) for line in text.splitlines() if line.strip()]
               if path.suffix == ".jsonl" else json.loads(text))
    except (OSError, ValueError):
        return [], []  # load_evidence 已把同一读取错误记为 no_evidence。
    ids: list[str] = []
    errors: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                if key == "episode_ref":
                    episode_id = value.get("episode_id") if isinstance(value, Mapping) else None
                    if not isinstance(episode_id, str) or not episode_id.strip() or episode_id in {".", ".."}:
                        errors.append("episode_ref 缺少合法 episode_id")
                    elif episode_id not in ids:
                        ids.append(episode_id)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    return ids, errors


def check_paths(
    paths: Iterable[str | Path],
    expected: Iterable[str],
    *,
    allow_unreported: bool = False,
    episode_store_roots: Iterable[str | Path] = (),
) -> list[AdmissionResult]:
    expected = tuple(expected)
    found, missing = resolve_artifacts(paths)
    stores = tuple(Path(root).expanduser().resolve() for root in episode_store_roots)
    results: list[AdmissionResult] = []
    visited: set[Path] = set()

    def fail(source: str, reason: str) -> None:
        results.append(judge(ServedModelEvidence(source, error=reason), expected))

    def visit(path: Path, ancestors: frozenset[Path]) -> None:
        path = path.resolve()
        if path in ancestors:
            fail(str(path), "episode_ref 存在环路，无法证明完整模型链")
            return
        if path in visited:
            return
        visited.add(path)
        results.append(judge(load_evidence(path), expected, allow_unreported=allow_unreported))
        references, errors = _episode_references(path)
        for error in errors:
            fail(str(path), error)
        if not references:
            return
        # 使用生产 writer 的目录规则，不复制它的替换/哈希算法；构造器不创建目录。
        from intelligence.services.episode_store import JsonlEpisodeStore

        roots = set(stores)
        if path.name == EVENTS_FILENAME:
            roots.add(path.parent.parent)
        for episode_id in references:
            hits = sorted({
                JsonlEpisodeStore(root).episode_dir(episode_id) / EVENTS_FILENAME
                for root in roots
                if (JsonlEpisodeStore(root).episode_dir(episode_id) / EVENTS_FILENAME).is_file()
            })
            if not hits:
                fail(f"{path} -> {episode_id}", "找不到子分支产物；请提供完整 --episode-store")
            for child in hits:
                visit(child, ancestors | {path})

    for path in found:
        visit(path, frozenset())
    for source in missing:
        fail(source, "找不到产物文件")
    return results


def overall_exit_code(results: Iterable[AdmissionResult]) -> int:
    """任何错配 → 1；否则任何无证据（或一个产物都没有）→ 2；全部准入 → 0。"""

    verdicts = [item.verdict for item in results]
    if VERDICT_MISMATCH in verdicts:
        return EXIT_CODES[VERDICT_MISMATCH]
    if not verdicts or VERDICT_NO_EVIDENCE in verdicts:
        return EXIT_CODES[VERDICT_NO_EVIDENCE]
    return EXIT_CODES[VERDICT_ADMITTED]
