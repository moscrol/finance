"""Deterministic leakage checks for sealed runtime benchmark exports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Literal
import unicodedata


LeakKind = Literal[
    "question",
    "conversation_context",
    "required_output",
    "direct_target",
    "reference_answer",
    "expected_fact",
    "pass_rule",
    "prior_answer",
    "post_cutoff_result",
]
LeakRule = Literal[
    "full_normalized_match",
    "character_ngram_match",
    "token_ngram_match",
    "token_jaccard_match",
    "invalid_utf8",
    "non_regular_file",
]

_SENTENCE_SPLIT_RE = re.compile(r"[\n\r。！？!?；;]+")
_CHAR_NGRAM = 12
_TOKEN_NGRAM = 6
_JACCARD_THRESHOLD = 0.80
_SEMANTIC_CANDIDATE_THRESHOLD = 0.15
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def normalize_char_stream(text: str) -> str:
    """Return the NFKC/case-folded stream used by character leak checks."""

    normalized = unicodedata.normalize("NFKC", str(text)).casefold()
    return "".join(
        char
        for char in normalized
        if not char.isspace()
        and not unicodedata.category(char).startswith("P")
    )


def tokenize(text: str) -> tuple[str, ...]:
    """Tokenize Han code points individually and retain alphanumeric runs."""

    normalized = unicodedata.normalize("NFKC", str(text)).casefold()
    tokens: list[str] = []
    alphanumeric: list[str] = []

    def flush() -> None:
        if alphanumeric:
            tokens.append("".join(alphanumeric))
            alphanumeric.clear()

    for char in normalized:
        if "\u4e00" <= char <= "\u9fff":
            flush()
            tokens.append(char)
        elif char.isalnum():
            alphanumeric.append(char)
        else:
            flush()
    flush()
    return tuple(tokens)


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ngrams(values: tuple[str, ...] | str, width: int) -> set[object]:
    if len(values) < width:
        return set()
    return {values[index : index + width] for index in range(len(values) - width + 1)}


def _sentences(text: str) -> tuple[str, ...]:
    return tuple(
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_RE.split(text)
        if sentence.strip()
    )


def _jaccard_sets(left_set: frozenset[str], right_set: frozenset[str]) -> float:
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


@dataclass(frozen=True)
class ForbiddenText:
    source_id: str
    kind: LeakKind
    text: str

    def __post_init__(self) -> None:
        for field_name in ("source_id", "text"):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"{field_name} must be non-empty")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True)
class ForbiddenCorpus:
    entries: tuple[ForbiddenText, ...]

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        if not entries or any(not isinstance(item, ForbiddenText) for item in entries):
            raise ValueError("forbidden corpus requires ForbiddenText entries")
        source_ids = tuple(item.source_id for item in entries)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("forbidden corpus source ids must be unique")
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class _PreparedForbiddenText:
    source: ForbiddenText
    char_stream: str
    char_ngrams: frozenset[object]
    tokens: tuple[str, ...]
    token_ngrams: frozenset[object]
    token_set: frozenset[str]


def _prepare_forbidden_text(value: ForbiddenText) -> _PreparedForbiddenText:
    char_stream = normalize_char_stream(value.text)
    tokens = tokenize(value.text)
    return _PreparedForbiddenText(
        source=value,
        char_stream=char_stream,
        char_ngrams=frozenset(_ngrams(char_stream, _CHAR_NGRAM)),
        tokens=tokens,
        token_ngrams=frozenset(_ngrams(tokens, _TOKEN_NGRAM)),
        token_set=frozenset(tokens),
    )


@dataclass(frozen=True)
class LeakFinding:
    relative_path: str
    source_id: str
    rule: LeakRule
    sentence_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "relative_path": self.relative_path,
            "source_id": self.source_id,
            "rule": self.rule,
            "sentence_sha256": self.sentence_sha256,
        }


@dataclass(frozen=True)
class SemanticLeakCandidate:
    relative_path: str
    source_id: str
    sentence: str
    token_jaccard: float

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "source_id": self.source_id,
            "sentence": self.sentence,
            "token_jaccard": round(self.token_jaccard, 6),
        }


@dataclass(frozen=True)
class LeakScanResult:
    status: Literal["passed", "rejected"]
    files_scanned: int
    findings: tuple[LeakFinding, ...]
    semantic_candidates: tuple[SemanticLeakCandidate, ...]
    scan_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "files_scanned": self.files_scanned,
            "findings": [item.to_dict() for item in self.findings],
            "semantic_candidates": [
                item.to_dict() for item in self.semantic_candidates
            ],
            "scan_sha256": self.scan_sha256,
        }


def _match_rule(
    *,
    candidate_chars: str,
    candidate_char_ngrams: frozenset[object],
    candidate_token_ngrams: frozenset[object],
    candidate_token_set: frozenset[str],
    forbidden: _PreparedForbiddenText,
) -> tuple[LeakRule | None, float]:
    if forbidden.char_stream and forbidden.char_stream in candidate_chars:
        return "full_normalized_match", 1.0
    if candidate_char_ngrams & forbidden.char_ngrams:
        return "character_ngram_match", 1.0
    if candidate_token_ngrams & forbidden.token_ngrams:
        return "token_ngram_match", 1.0
    score = _jaccard_sets(candidate_token_set, forbidden.token_set)
    if len(forbidden.tokens) >= 8 and score >= _JACCARD_THRESHOLD:
        return "token_jaccard_match", score
    return None, score


def scan_export(root: str | Path, corpus: ForbiddenCorpus) -> LeakScanResult:
    """Scan regular UTF-8 export files against the frozen forbidden corpus."""

    requested_root = Path(root)
    if (
        requested_root.is_symlink()
        or not requested_root.exists()
        or not requested_root.is_dir()
    ):
        raise ValueError("export root must be an existing regular directory")
    export_root = requested_root.resolve()
    findings: list[LeakFinding] = []
    semantic_candidates: list[SemanticLeakCandidate] = []
    files_scanned = 0
    prepared_corpus = tuple(_prepare_forbidden_text(item) for item in corpus.entries)
    for path in sorted(export_root.rglob("*")):
        relative = path.relative_to(export_root).as_posix()
        if path.is_symlink() or (path.exists() and not path.is_file()):
            if path.exists() and not path.is_dir():
                findings.append(
                    LeakFinding(
                        relative,
                        "export-boundary",
                        "non_regular_file",
                        hashlib.sha256(relative.encode("utf-8")).hexdigest(),
                    )
                )
            continue
        if not path.is_file():
            continue
        files_scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                LeakFinding(
                    relative,
                    "export-boundary",
                    "invalid_utf8",
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
            continue
        for sentence in _sentences(text) or (text,):
            sentence_hash = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
            candidate_chars = normalize_char_stream(sentence)
            candidate_tokens = tokenize(sentence)
            candidate_char_ngrams = frozenset(
                _ngrams(candidate_chars, _CHAR_NGRAM)
            )
            candidate_token_ngrams = frozenset(
                _ngrams(candidate_tokens, _TOKEN_NGRAM)
            )
            candidate_token_set = frozenset(candidate_tokens)
            for forbidden in prepared_corpus:
                rule, score = _match_rule(
                    candidate_chars=candidate_chars,
                    candidate_char_ngrams=candidate_char_ngrams,
                    candidate_token_ngrams=candidate_token_ngrams,
                    candidate_token_set=candidate_token_set,
                    forbidden=forbidden,
                )
                if rule is not None:
                    findings.append(
                        LeakFinding(
                            relative,
                            forbidden.source.source_id,
                            rule,
                            sentence_hash,
                        )
                    )
                    continue
                if (
                    len(forbidden.tokens) >= 8
                    and score >= _SEMANTIC_CANDIDATE_THRESHOLD
                ):
                    semantic_candidates.append(
                        SemanticLeakCandidate(
                            relative,
                            forbidden.source.source_id,
                            sentence[:500],
                            score,
                        )
                    )
    if files_scanned == 0:
        raise ValueError("export root must contain at least one regular file")
    deduped_findings = tuple(
        sorted(
            set(findings),
            key=lambda item: (item.relative_path, item.source_id, item.rule),
        )
    )
    deduped_candidates = tuple(
        sorted(
            set(semantic_candidates),
            key=lambda item: (
                item.relative_path,
                item.source_id,
                -item.token_jaccard,
            ),
        )
    )
    payload = {
        "status": "rejected" if deduped_findings else "passed",
        "files_scanned": files_scanned,
        "findings": [item.to_dict() for item in deduped_findings],
        "semantic_candidates": [item.to_dict() for item in deduped_candidates],
    }
    return LeakScanResult(
        status=payload["status"],
        files_scanned=files_scanned,
        findings=deduped_findings,
        semantic_candidates=deduped_candidates,
        scan_sha256=_sha256_json(payload),
    )


@dataclass(frozen=True)
class SemanticLeakReceipt:
    export_manifest_sha256: str
    deterministic_scan_sha256: str
    model: str
    prompt_sha256: str
    reviewer: str
    verdict: Literal["pass", "fail"]
    receipt_sha256: str

    @classmethod
    def create(
        cls,
        *,
        export_manifest_sha256: str,
        deterministic_scan_sha256: str,
        model: str,
        prompt_sha256: str,
        reviewer: str,
        verdict: Literal["pass", "fail"],
    ) -> SemanticLeakReceipt:
        payload = {
            "export_manifest_sha256": export_manifest_sha256,
            "deterministic_scan_sha256": deterministic_scan_sha256,
            "model": model,
            "prompt_sha256": prompt_sha256,
            "reviewer": reviewer,
            "verdict": verdict,
        }
        return cls(receipt_sha256=_sha256_json(payload), **payload)

    def payload(self) -> dict[str, str]:
        return {
            "export_manifest_sha256": self.export_manifest_sha256,
            "deterministic_scan_sha256": self.deterministic_scan_sha256,
            "model": self.model,
            "prompt_sha256": self.prompt_sha256,
            "reviewer": self.reviewer,
            "verdict": self.verdict,
        }

    def to_dict(self) -> dict[str, str]:
        return {**self.payload(), "receipt_sha256": self.receipt_sha256}


def validate_semantic_receipt(
    value: object,
    *,
    expected_export_manifest_sha256: str,
    expected_deterministic_scan_sha256: str,
    producer_identity: str,
) -> SemanticLeakReceipt:
    """Validate one independent semantic-leak review receipt."""

    if not isinstance(value, dict):
        raise ValueError("semantic receipt must be an object")
    receipt = SemanticLeakReceipt(
        export_manifest_sha256=str(value.get("export_manifest_sha256") or ""),
        deterministic_scan_sha256=str(
            value.get("deterministic_scan_sha256") or ""
        ),
        model=str(value.get("model") or ""),
        prompt_sha256=str(value.get("prompt_sha256") or ""),
        reviewer=str(value.get("reviewer") or ""),
        verdict=str(value.get("verdict") or ""),  # type: ignore[arg-type]
        receipt_sha256=str(value.get("receipt_sha256") or ""),
    )
    for field_name in (
        "export_manifest_sha256",
        "deterministic_scan_sha256",
        "prompt_sha256",
        "receipt_sha256",
    ):
        if not _SHA256_RE.fullmatch(getattr(receipt, field_name)):
            raise ValueError(f"semantic receipt {field_name} must be SHA-256")
    if receipt.model != "gpt-5.6-sol":
        raise ValueError("semantic receipt model must be gpt-5.6-sol")
    if (
        not receipt.reviewer.strip()
        or receipt.reviewer.strip() == str(producer_identity or "").strip()
    ):
        raise ValueError("semantic receipt requires an independent reviewer")
    if receipt.verdict != "pass":
        raise ValueError("semantic receipt verdict must be pass")
    if receipt.export_manifest_sha256 != expected_export_manifest_sha256:
        raise ValueError("semantic receipt export manifest hash mismatch")
    if receipt.deterministic_scan_sha256 != expected_deterministic_scan_sha256:
        raise ValueError("semantic receipt deterministic scan hash mismatch")
    if receipt.receipt_sha256 != _sha256_json(receipt.payload()):
        raise ValueError("semantic receipt self hash mismatch")
    return receipt


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read forbidden corpus source: {path.name}") from exc


def _case_records(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Mapping):
        return ()
    cases = value.get("cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        return ()
    return tuple(item for item in cases if isinstance(item, Mapping))


def _recursive_answers(value: object) -> tuple[str, ...]:
    answers: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in {"answer", "candidate_answer", "published_answer"}:
                text = str(item or "").strip()
                if text:
                    answers.append(text)
            else:
                answers.extend(_recursive_answers(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            answers.extend(_recursive_answers(item))
    return tuple(answers)


def build_forbidden_corpus(
    *,
    question_file: str | Path,
    reference_file: str | Path,
    prior_artifacts: Sequence[str | Path] = (),
    post_cutoff_documents: Sequence[str | Path] = (),
) -> ForbiddenCorpus:
    """Load every evaluator-owned leak source outside the sealed export."""

    entries: list[ForbiddenText] = []

    def add(kind: LeakKind, source: str, value: object) -> None:
        text = str(value or "").strip()
        if not text:
            return
        entries.append(
            ForbiddenText(
                source_id=f"{kind}:{source}:{len(entries) + 1}",
                kind=kind,
                text=text,
            )
        )

    for case in _case_records(_load_json(Path(question_file))):
        case_id = str(case.get("id") or "case")
        add("question", case_id, case.get("question"))
        context = case.get("conversation_context")
        if isinstance(context, Sequence) and not isinstance(context, (str, bytes)):
            for index, message in enumerate(context):
                if isinstance(message, Mapping):
                    add(
                        "conversation_context",
                        f"{case_id}:{index}",
                        message.get("content"),
                    )
        outputs = case.get("required_outputs")
        if isinstance(outputs, Sequence) and not isinstance(outputs, (str, bytes)):
            for output in outputs:
                add("required_output", case_id, output)

    for case in _case_records(_load_json(Path(reference_file))):
        case_id = str(case.get("id") or "case")
        add("reference_answer", case_id, case.get("answer"))
        targets = case.get("direct_targets")
        if isinstance(targets, Sequence) and not isinstance(targets, (str, bytes)):
            for target in targets:
                add("direct_target", case_id, target)
        requirements = case.get("requirements")
        if isinstance(requirements, Sequence) and not isinstance(
            requirements, (str, bytes)
        ):
            for requirement in requirements:
                if not isinstance(requirement, Mapping):
                    continue
                add("required_output", case_id, requirement.get("id"))
                expected = requirement.get("satisfy_any")
                if isinstance(expected, Sequence) and not isinstance(
                    expected, (str, bytes)
                ):
                    for item in expected:
                        add("expected_fact", case_id, item)
        add("pass_rule", case_id, case.get("pass_rule"))

    for path_value in prior_artifacts:
        path = Path(path_value)
        for index, answer in enumerate(_recursive_answers(_load_json(path))):
            add("prior_answer", f"{path.name}:{index}", answer)

    for path_value in post_cutoff_documents:
        path = Path(path_value)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(
                f"unable to read forbidden corpus source: {path.name}"
            ) from exc
        for index, sentence in enumerate(_sentences(text)):
            if len(normalize_char_stream(sentence)) >= _CHAR_NGRAM:
                add("post_cutoff_result", f"{path.name}:{index}", sentence)

    return ForbiddenCorpus(tuple(entries))
