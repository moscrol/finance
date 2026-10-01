"""Offline quantity-role sidecar contract, NOT a production release gate.

Bind a candidate annotation to one frozen native judge request and exact Unicode
occurrences. A fresh nonce separates dispatches of identical text. Hashes detect
mismatches, not authorship; transport/model admission is a separate requirement.
Even a structurally consistent historical role can be semantically wrong. This
probe always returns release_authorized=False and never changes the native
verifier, its prompt, numeric marks, repairs, deadlines or request budget.

prepare consumes a native projected request and explicit occurrence spans.
check requires the CURRENT request too, so callers cannot silently re-use a
receipt after editing the draft, evidence, question, bindings or date context.
R21 shadow JSON has neither a native verdict nor these bindings and is rejected.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import secrets
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REQUEST_SCHEMA = "quantity_role_request_v1"
RESPONSE_SCHEMA = "quantity_role_response_v1"
ROLES = frozenset(
    {"historical_set_cardinality", "future_duration_condition", "other", "unknown"}
)
ROW_KEYS = frozenset(
    {
        "target_id",
        "role",
        "evidence_ids",
        "historical_source_dates",
        "historical_cardinality",
        "reason",
    }
)


class ContractError(ValueError):
    """Invalid or stale diagnostic input; never a release decision."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _canonical(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        _require(json.loads(encoded) == value, "input must be lossless JSON")
        return encoded
    except (TypeError, ValueError) as exc:
        raise ContractError("input must be finite JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _native_indexes(request: object) -> tuple[dict[int, str], dict[str, dict]]:
    _require(isinstance(request, dict), "native request must be an object")
    sentences = request.get("sentences")
    evidence = request.get("evidence_registry")
    _require(
        isinstance(sentences, list) and bool(sentences), "missing native sentences"
    )
    _require(isinstance(evidence, list), "missing native evidence registry")
    texts = {}
    for expected, row in enumerate(sentences, 1):
        _require(isinstance(row, dict), "invalid sentence")
        _require(
            type(row.get("index")) is int and row["index"] == expected,
            "noncontiguous or duplicate sentence index",
        )
        _require(
            isinstance(row.get("text"), str) and bool(row["text"].strip()),
            "invalid sentence text",
        )
        texts[expected] = row["text"]
    registry = {}
    for row in evidence:
        _require(isinstance(row, dict), "invalid evidence row")
        identifier = row.get("evidence_id")
        _require(
            isinstance(identifier, str) and bool(identifier),
            "invalid evidence identifier",
        )
        _require(identifier not in registry, "duplicate evidence identifier")
        registry[identifier] = row
    return texts, registry


def prepare_review(
    native_request: dict, spans: list[dict], *, nonce: str | None = None
) -> dict:
    """Freeze context and occurrence spans. No language classification is done."""
    native = json.loads(_canonical(native_request))
    texts, _ = _native_indexes(native)
    _require(
        isinstance(spans, list) and 0 < len(spans) <= 128,
        "expected 1..128 occurrence spans",
    )
    nonce = secrets.token_hex(16) if nonce is None else nonce
    _require(
        isinstance(nonce, str) and 16 <= len(nonce) <= 128, "invalid dispatch nonce"
    )
    normalized = []
    for span in spans:
        _require(
            isinstance(span, dict) and set(span) == {"sentence_index", "start", "end"},
            "invalid span keys",
        )
        index, start, end = (span[k] for k in ("sentence_index", "start", "end"))
        _require(
            all(type(v) is int for v in (index, start, end)),
            "span indexes must be integers, not booleans",
        )
        _require(
            index in texts and 0 <= start < end <= len(texts[index]),
            "span outside native sentence",
        )
        text = texts[index][start:end]
        _require(bool(text.strip()), "empty quantity span")
        normalized.append({**span, "text": text})
    normalized.sort(key=lambda row: (row["sentence_index"], row["start"], row["end"]))
    for left, right in zip(normalized, normalized[1:]):
        _require(
            left["sentence_index"] != right["sentence_index"]
            or left["end"] <= right["start"],
            "duplicate or overlapping quantity occurrences",
        )
    targets = [{"target_id": f"q{i}", **row} for i, row in enumerate(normalized, 1)]
    body = {
        "schema": REQUEST_SCHEMA,
        "nonce": nonce,
        "native_request": native,
        "targets": targets,
    }
    return {**body, "review_id": _digest(body)}


def _strings(value: object, name: str) -> list[str]:
    _require(
        isinstance(value, list) and all(isinstance(v, str) and v for v in value),
        f"invalid {name}",
    )
    _require(len(value) == len(set(value)), f"duplicate {name}")
    return value


def _iso(value: object) -> str:
    _require(isinstance(value, str), "date must be explicit ISO text")
    try:
        _require(date.fromisoformat(value).isoformat() == value, "noncanonical date")
    except ValueError as exc:
        raise ContractError("invalid source date") from exc
    return value


def check_review(
    bundle: dict, response: dict, *, current_request: dict
) -> dict[str, Any]:
    """Validate bindings and the native core independently; never grant release.

    Source-date equality is only a structural cross-reference. It does not prove
    that source_date is a trading/measurement date, that the quantity text means
    the proposed cardinality, or that the model assigned the right semantic role.
    """
    _require(
        isinstance(bundle, dict)
        and set(bundle)
        == {"schema", "nonce", "native_request", "targets", "review_id"},
        "invalid frozen request",
    )
    _require(
        bundle["schema"] == REQUEST_SCHEMA and isinstance(bundle["targets"], list),
        "invalid request schema",
    )
    try:
        spans = [
            {k: row[k] for k in ("sentence_index", "start", "end")}
            for row in bundle["targets"]
        ]
    except (KeyError, TypeError) as exc:
        raise ContractError("invalid frozen targets") from exc
    rebuilt = prepare_review(bundle["native_request"], spans, nonce=bundle["nonce"])
    _require(
        _canonical(rebuilt) == _canonical(bundle), "frozen request or target drift"
    )
    _require(
        _canonical(current_request) == _canonical(bundle["native_request"]),
        "current request differs from reviewed context",
    )
    texts, registry = _native_indexes(current_request)
    _require(
        isinstance(response, dict)
        and set(response)
        == {"schema", "review_id", "grounding_report", "quantity_roles"},
        "invalid response envelope",
    )
    _require(
        response["schema"] == RESPONSE_SCHEMA
        and response["review_id"] == bundle["review_id"],
        "response belongs to another dispatch",
    )
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier

    diagnostics: list[str] = []
    native_report = SemanticEpisodeVerifier._parse_report(
        response["grounding_report"],
        len(texts),
        material_claims=current_request.get("material_claims"),
        material_outputs=current_request.get("material_outputs"),
        diagnostics=diagnostics,
    )
    _require(
        native_report is not None,
        "invalid native grounding report: " + ",".join(diagnostics),
    )
    raw = response["quantity_roles"]
    _require(isinstance(raw, list), "quantity roles must be a list")
    targets = {row["target_id"]: row for row in bundle["targets"]}
    seen = set()
    annotations = []
    for row in raw:
        _require(
            isinstance(row, dict) and set(row) == ROW_KEYS, "invalid role record keys"
        )
        identifier = row["target_id"]
        _require(
            isinstance(identifier, str)
            and identifier in targets
            and identifier not in seen,
            "unknown or duplicate target",
        )
        seen.add(identifier)
        role = row["role"]
        _require(isinstance(role, str) and role in ROLES, "unknown quantity role")
        _require(
            isinstance(row["reason"], str) and bool(row["reason"].strip()),
            "missing explicit reason",
        )
        references = _strings(row["evidence_ids"], "evidence references")
        _require(set(references) <= set(registry), "foreign evidence reference")
        dates = _strings(row["historical_source_dates"], "historical source dates")
        for value in dates:
            _iso(value)
        cardinality = row["historical_cardinality"]
        if role == "historical_set_cardinality":
            _require(
                type(cardinality) is int and cardinality > 0,
                "invalid historical cardinality",
            )
            _require(
                bool(references) and bool(dates),
                "historical role needs explicit references and dates",
            )
            source_dates = {
                _iso(registry[key].get("source_date")) for key in references
            }
            _require(
                set(dates) == source_dates and cardinality == len(source_dates),
                "historical cardinality/source-date mismatch",
            )
        else:
            _require(
                cardinality is None and not dates,
                "nonhistorical role cannot inherit historical cardinality",
            )
        annotations.append({**targets[identifier], **json.loads(_canonical(row))})
    _require(seen == set(targets), "missing quantity occurrence coverage")
    return {
        "schema": "quantity_role_diagnostic_v1",
        "review_id": bundle["review_id"],
        "diagnostic_only": True,
        "release_authorized": False,
        "model_identity_verified": False,
        "native_report": native_report.to_dict(),
        "annotations": annotations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--native-request", required=True, type=Path)
    prep.add_argument("--spans", required=True, type=Path)
    prep.add_argument("--out", required=True, type=Path)
    check = sub.add_parser("check")
    check.add_argument("--bundle", required=True, type=Path)
    check.add_argument("--response", required=True, type=Path)
    check.add_argument("--current-request", required=True, type=Path)
    check.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    def load(path: Path):
        return json.loads(path.read_text())

    try:
        if args.command == "prepare":
            result = prepare_review(load(args.native_request), load(args.spans))
        else:
            result = check_review(
                load(args.bundle),
                load(args.response),
                current_request=load(args.current_request),
            )
        with args.out.open("x") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
        print(
            json.dumps(
                {
                    "schema": result["schema"],
                    "review_id": result["review_id"],
                    "release_authorized": False,
                }
            )
        )
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(
            f"quantity-role probe rejected: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
