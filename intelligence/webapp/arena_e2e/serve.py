"""Isolated E2E fixture server; never use this entrypoint for public service."""
from __future__ import annotations

import tempfile
from pathlib import Path

import uvicorn

from intelligence.arena.app import create_app
from intelligence.arena.demo import demo_matches
from intelligence.arena.models import Match
from intelligence.arena.store import ArenaStore, canonical, digest


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="arena-e2e-") as directory:
        store = ArenaStore(Path(directory) / "arena.sqlite3")
        fixture = demo_matches()[0].model_dump(mode="json")
        run_id = store.create_run({"fixture_only": True})
        fixture.update(id="fixture-live", provenance="platform_run", run_id=run_id)
        for i, answer in enumerate(fixture["answers"]):
            answer["participant"] = {"id": f"fixture-{i}", "name": f"E2E Fixture {i}", "version": "test-v1", "kind": "agent"}
        match = Match.model_validate(fixture)
        payload = {"fixture_only": True, "match_digest": digest(canonical(fixture))}
        store.complete_run_with_match(run_id, payload, match)
        store.publish(match.id, actor="e2e-fixture", review_attested=True)
        app = create_app(store)

        @app.post("/__fixture__/invite")
        def invitation():
            return {"code": store.issue_invite("browser-test")}

        uvicorn.run(app, host="127.0.0.1", port=8826, log_level="warning")


if __name__ == "__main__":
    main()
