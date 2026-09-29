"""Opt-in isolated Workbench experiment; never imported by production startup.

Both arms pin the existing writer to glm-5.3-flash, with no other provider
fallback. Only ON omits H rows in the compact author request. Real provider
transport, cancellation, timeouts, repair, validator and judge stay unchanged.
Run only on an isolated users/episode root and protected code/data paths.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
from typing import Any

from scripts.redraft_projection import ProjectionRefused, project_standalone_redraft

WRITER = "glm-5.3-flash"


def select_writer_provider(providers):
    matches = tuple(p for p in providers if p.model == WRITER)
    if len(matches) != 1:
        raise ProjectionRefused("exactly one configured flash writer is required")
    return matches


def verify_effective_provider(providers):
    if len(providers) != 1 or providers[0].model != WRITER:
        raise ProjectionRefused("writer override or fallback would change the fixed model")


def _contains_text(value, text: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_text(item, text) for item in value.values())
    if isinstance(value, list):
        return any(_contains_text(item, text) for item in value)
    if isinstance(value, str):
        if text in value:
            return True
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return False
        return _contains_text(decoded, text)
    return False


def transform_messages(messages: list[dict[str, Any]], *, clean: bool):
    """OFF is byte-identical; ON changes only the compact H catalogue rows."""
    candidates = []
    for i, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        try:
            value = json.loads(message.get("content", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict) and "research_contract" in value and "task_frame" in value:
            candidates.append((i, value))
    if len(candidates) != 1:
        raise ProjectionRefused("expected exactly one compact research payload")
    index, payload = candidates[0]
    # Even OFF must pass the same structural eligibility check before transport.
    projected = project_standalone_redraft(payload, standalone_redraft=True)
    before_sources = payload["material_grounding"]["sources"]
    if not any(row["ref"].startswith("H") for row in before_sources):
        raise ProjectionRefused("the ablation needs an explicit historical source")
    if json.dumps(payload, ensure_ascii=False) != messages[index]["content"]:
        raise ProjectionRefused("unexpected serializer; refuse whitespace confounding")
    if clean:
        output = deepcopy(messages)
        output[index]["content"] = json.dumps(projected.author_view, ensure_ascii=False)
        # The synthetic cases never quote the complete old answer in the user
        # instruction. Detect a duplicate full old-answer copy outside H too.
        for row in before_sources:
            if row["ref"].startswith("H") and _contains_text(output, row["text"]):
                raise ProjectionRefused("full old-answer copy remains outside H catalogue")
    else:
        output = messages
    metadata = {
        "arm": "ON" if clean else "OFF",
        "omitted_refs": list(projected.omitted_refs) if clean else [],
        "sources_before": [row["ref"] for row in before_sources],
        "sources_after": [row["ref"] for row in (projected.author_view if clean else payload)["material_grounding"]["sources"]],
        "input_before_sha256": hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
        "input_after_sha256": hashlib.sha256(json.dumps(output, ensure_ascii=False).encode()).hexdigest(),
    }
    return output, metadata


def serve(*, arm: str, port: int, capture_dir: Path):
    """Install process-local experiment seams before serving isolated API turns."""
    import importlib
    import uvicorn
    from intelligence.services import llm_refine

    if arm not in {"OFF", "ON"} or not 10000 <= port <= 65535:
        raise ProjectionRefused("isolated arm/port required")
    capture_dir.mkdir(parents=True, exist_ok=False)
    configured = select_writer_provider(llm_refine.detect_providers())
    (capture_dir / "writer-preflight.json").write_text(json.dumps({
        "writer": WRITER, "configured_matches": len(configured),
        "cross_model_fallback": False, "arm": arm,
    }))
    app_module = importlib.import_module("intelligence.api.app")
    original_factory = app_module._build_continuous_turn_adapter
    original_chat = llm_refine.chat_with_tools
    lock = threading.Lock()
    calls = 0

    def factory(**kwargs):
        kwargs["providers"] = select_writer_provider(kwargs["providers"])
        return original_factory(**kwargs)

    def guarded_chat(**kwargs):
        nonlocal calls
        effective = llm_refine.detect_providers(kwargs.get("model_override"))
        verify_effective_provider(effective)  # BEFORE the real HTTP transport
        if kwargs.get("tools"):
            raise ProjectionRefused("ablation task unexpectedly exposes tools")
        messages, meta = transform_messages(kwargs["messages"], clean=arm == "ON")
        with lock:
            calls += 1
            number = calls
        record = {
            **meta, "effective_writer": effective[0].model,
            "timeout_requested": kwargs.get("timeout"),
            "messages_before": kwargs["messages"], "messages_after": messages,
            "tools": kwargs["tools"],
        }
        with (capture_dir / f"request-{number:03d}.json").open("x") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return original_chat(**{**kwargs, "messages": messages})

    app_module._build_continuous_turn_adapter = factory
    llm_refine.chat_with_tools = guarded_chat
    uvicorn.run(app_module.app, host="127.0.0.1", port=port, log_level="info")


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=["OFF", "ON"], required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    args = parser.parse_args()
    serve(arm=args.arm, port=args.port, capture_dir=args.capture_dir)


if __name__ == "__main__":
    main()
