"""Episode-level evidence_bound 量具。

旧口径（十题窗 / 长尾 ``_bindings_rate``）：所有 binding 进分母，
``hashes and not gap`` 才算绑定。

#72 之后观点题判断槽是 ``grounding_mode=model_reasoning``，协议不要求哈希。
分层口径把这类槽移出分母，只评 ``evidence`` 槽。旧口径仍可算，供对照。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

MODEL_REASONING = "model_reasoning"


def extract_bindings(episode: Mapping[str, Any] | None) -> list[Any]:
    if not isinstance(episode, Mapping):
        return []
    outcome = episode.get("outcome")
    if isinstance(outcome, Mapping):
        raw = outcome.get("bindings")
        if isinstance(raw, list) and raw:
            return raw
    verifier = episode.get("semantic_verifier") or episode.get("structural_verifier")
    if isinstance(verifier, Mapping):
        verified = verifier.get("verified") if isinstance(verifier.get("verified"), Mapping) else verifier
        nested = verified.get("outcome") if isinstance(verified, Mapping) else None
        if isinstance(nested, Mapping) and isinstance(nested.get("bindings"), list):
            return list(nested["bindings"])
    return []


def grounding_modes(episode: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(episode, Mapping):
        return {}
    contract = episode.get("contract")
    if not isinstance(contract, Mapping):
        return {}
    modes: dict[str, str] = {}
    for item in contract.get("required_outputs") or ():
        if not isinstance(item, Mapping):
            continue
        output_id = str(item.get("output_id") or "").strip()
        mode = str(item.get("grounding_mode") or "").strip()
        if output_id and mode:
            modes[output_id] = mode
    return modes


def output_grounding_mode(
    item: Mapping[str, Any],
    modes: Mapping[str, str],
) -> str:
    output_id = str(item.get("output_id") or "").strip()
    if output_id and output_id in modes:
        return modes[output_id]
    return str(item.get("basis") or "").strip()


def is_bound(item: Mapping[str, Any]) -> bool:
    hashes = item.get("evidence_hashes") or ()
    gap = str(item.get("gap") or "").strip()
    return bool(hashes) and not gap


def bindings_rate(
    episode: Mapping[str, Any] | None,
    *,
    exclude_grounding_modes: Sequence[str] = (),
) -> float | None:
    """旧口径：``exclude_grounding_modes=()``。分层：排除 ``model_reasoning``。

    ``episode is None``（无 episode 文件）→ ``None``，不进窗均值。
    有 episode 但无 binding → ``0.0``。
    排除后分母为空 → ``None``。
    """

    if episode is None:
        return None
    bindings = extract_bindings(episode)
    if not bindings:
        return 0.0
    modes = grounding_modes(episode)
    excluded = {str(item) for item in exclude_grounding_modes}
    scored: list[Mapping[str, Any]] = []
    for item in bindings:
        if not isinstance(item, Mapping):
            continue
        if output_grounding_mode(item, modes) in excluded:
            continue
        scored.append(item)
    if not scored:
        return None
    return sum(1 for item in scored if is_bound(item)) / len(scored)


def legacy_bindings_rate(episode: Mapping[str, Any] | None) -> float | None:
    return bindings_rate(episode)


def stratified_evidence_bound_rate(episode: Mapping[str, Any] | None) -> float | None:
    return bindings_rate(episode, exclude_grounding_modes=(MODEL_REASONING,))


def judgment_hash_rate(episode: Mapping[str, Any] | None) -> float | None:
    """只评 ``model_reasoning`` 槽的哈希率；没有判断槽则 ``None``。"""

    if episode is None:
        return None
    bindings = extract_bindings(episode)
    modes = grounding_modes(episode)
    scored = [
        item
        for item in bindings
        if isinstance(item, Mapping)
        and output_grounding_mode(item, modes) == MODEL_REASONING
    ]
    if not scored:
        return None
    return sum(1 for item in scored if is_bound(item)) / len(scored)
