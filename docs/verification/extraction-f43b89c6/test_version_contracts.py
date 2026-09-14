"""Read-only candidate review. All product writes use Base's TemporaryDirectory."""
import json

from intelligence.services import observation_extraction as ox
from intelligence.services import observation_script as osc
from intelligence.tests.test_observation_extraction_first import AS_OF, Base, CANON, ENTITY, _run


class DraftReversionContracts(Base):
    A = ["题材轨：题材所处阶段是否推进"]
    B = ["资金轨：板块 / 题材资金流是否延续"]

    def test_every_new_draft_version_has_one_visible_success_event(self):
        for variables in (self.A, self.B, self.A):
            code, out = self.draft(variables=variables, extra=["--json"])
            self.assertEqual(code, 0, out)
        raw = osc.load_raw(self.ledger())
        drafts = osc.user_drafts(raw, key=ox.make_key("u1", AS_OF, CANON))
        code, out = _run(["observation", "list", "--user", "u1", "--events", "--json"])
        self.assertEqual(code, 0, out)
        events = [e for e in json.loads(out)["events"] if e["event"] == osc.EVENT_DRAFT_SUBMITTED]
        print(json.dumps({"draft_ids": [d["draft_id"] for d in drafts],
                          "inline_event_ids": [d["action_event"]["event_id"] for d in drafts],
                          "visible_event_draft_ids": [e["draft_id"] for e in events]}, ensure_ascii=False))
        self.assertEqual(len(drafts), 3, "A→B→A contains three successful versions")
        self.assertEqual([e["draft_id"] for e in events], [d["draft_id"] for d in drafts],
                         "Every persisted new draft version needs its own visible submitted event")
        self.assertEqual(len({e["event_id"] for e in events}), 3)

    def test_confirm_after_reversion_preserves_the_current_source_version(self):
        records = []
        for variables in (self.A, self.B, self.A):
            code, out = self.draft(variables=variables, extra=["--json"])
            self.assertEqual(code, 0, out)
            submitted = json.loads(out)
            code, out = _run(["observation", "confirm", "--user", "u1", "--as-of", AS_OF,
                              "--from-draft", ENTITY, "--db-path", "/tmp/no-such.duckdb", "--json"])
            self.assertEqual(code, 0, out)
            records.append((submitted, json.loads(out)))
        print(json.dumps({"submitted_versions": [d["draft_id"] for d, _ in records],
                          "confirmed_source_versions": [c["source_draft_id"] for _, c in records]}, ensure_ascii=False))
        newest_draft, newest_confirmation = records[-1]
        self.assertTrue(newest_draft["created"])
        self.assertEqual(newest_confirmation["source_draft_id"], newest_draft["draft_id"],
                         "Confirmation must link the version selected now, not the first equal-content version")

    def test_immediate_retry_remains_one_version_and_one_event(self):
        for _ in range(2):
            self.assertEqual(self.draft(variables=self.A)[0], 0)
        drafts = osc.user_drafts(osc.load_raw(self.ledger()), key=ox.make_key("u1", AS_OF, CANON))
        events = self.kinds(osc.EVENT_DRAFT_SUBMITTED)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(events), 1)

    def test_persisted_version_event_bijection_regression(self):
        """Green on old (two versions), red on new (three versions but two events)."""
        for variables in (self.A, self.B, self.A):
            self.assertEqual(self.draft(variables=variables)[0], 0)
        drafts = osc.user_drafts(osc.load_raw(self.ledger()), key=ox.make_key("u1", AS_OF, CANON))
        self.assertEqual([e["draft_id"] for e in self.kinds(osc.EVENT_DRAFT_SUBMITTED)],
                         [d["draft_id"] for d in drafts])

    def test_confirmation_matches_actually_selected_latest_version_regression(self):
        """Green on old (latest remains B), red on new (latest v3, confirm replays v1)."""
        for variables in (self.A, self.B, self.A):
            self.assertEqual(self.draft(variables=variables)[0], 0)
            selected = osc.latest_user_draft(osc.load_raw(self.ledger()), key=ox.make_key("u1", AS_OF, CANON))
            code, out = _run(["observation", "confirm", "--user", "u1", "--as-of", AS_OF,
                              "--from-draft", ENTITY, "--db-path", "/tmp/no-such.duckdb", "--json"])
            self.assertEqual(code, 0, out)
            self.assertEqual(json.loads(out)["source_draft_id"], selected["draft_id"])
