"""Offline embedding readiness worker with flushed phases and periodic stacks.

Run only through prepare_adaptive_l6.retrieval_probe, which owns the 120s limit.
The stdlib-only startup stays observable even when a model import stalls.
"""
from __future__ import annotations

import faulthandler
import json
from pathlib import Path
import sys
import time


def probe(library: Path) -> int:
    started = time.monotonic()

    def emit(event, **fields):
        print(json.dumps({"event": event, "elapsed_seconds": round(time.monotonic() - started, 6), **fields}), flush=True)

    emit("started")
    faulthandler.dump_traceback_later(30, repeat=True)
    try:
        sys.path.insert(0, str(library))
        emit("import_started")
        from rag.embedder import get_embedder

        emit("import_complete")
        emit("load_started")
        encoder = get_embedder("bge-m3")
        emit("load_complete")
        emit("encode_started")
        vector = encoder.encode(["local readiness probe"])
        shape = list(vector.shape)
        ready = shape == [1, 1024]
        emit("complete", ready=ready, shape=shape)
        return 0 if ready else 1
    except Exception as exc:
        emit("failed", ready=False, error_type=type(exc).__name__, detail=str(exc)[:1600])
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    raise SystemExit(probe(Path(sys.argv[1])))
