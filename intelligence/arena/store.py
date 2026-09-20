from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import Match, Strategy

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, csrf TEXT NOT NULL, created REAL NOT NULL,
 reviewer TEXT UNIQUE, invite_id TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS invites (
 hash TEXT PRIMARY KEY, label TEXT NOT NULL, created REAL NOT NULL,
 expires REAL NOT NULL, redeemed REAL
);
CREATE TABLE IF NOT EXISTS matches (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL,
 provenance TEXT NOT NULL, category TEXT NOT NULL,
 published INTEGER NOT NULL DEFAULT 0, invalid_reason TEXT,
 created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 match_id TEXT NOT NULL REFERENCES matches(id), flipped INTEGER NOT NULL,
 created REAL NOT NULL, skipped INTEGER NOT NULL DEFAULT 0,
 UNIQUE(session_id, match_id)
);
CREATE TABLE IF NOT EXISTS votes (
 assignment_id TEXT PRIMARY KEY REFERENCES assignments(id),
 choice TEXT NOT NULL CHECK(choice IN ('left','right','tie','both_bad')),
 reasons TEXT NOT NULL, eligible INTEGER NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 question TEXT NOT NULL, category TEXT NOT NULL, created REAL NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', run_id TEXT
);
CREATE TABLE IF NOT EXISTS reports (
 assignment_id TEXT NOT NULL REFERENCES assignments(id),
 reason TEXT NOT NULL, detail TEXT NOT NULL, created REAL NOT NULL,
 UNIQUE(assignment_id, reason)
);
CREATE TABLE IF NOT EXISTS limits (
 bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, created REAL NOT NULL, status TEXT NOT NULL,
 payload TEXT NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS strategies (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL,
 registered REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS assignments_session ON assignments(session_id, created);
CREATE INDEX IF NOT EXISTS matches_public ON matches(published, provenance, category);
"""


class ArenaError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message, self.status = message, status
        super().__init__(message)


def canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


class ArenaStore:
    """Separate pilot ledger. Every write is transactional; no shared Workbench DB."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(_SCHEMA)
        path.chmod(0o600)

    @contextmanager
    def connect(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA foreign_keys=ON")
            if write:
                con.execute("BEGIN IMMEDIATE")
            with con:
                yield con
        finally:
            con.close()

    def session(self, token: str | None) -> tuple[dict, str | None]:
        with self.connect(write=True) as con:
            row = con.execute("SELECT * FROM sessions WHERE id=? AND created>?", (digest(token or ""), time.time() - 30 * 86400)).fetchone()
            if row:
                return dict(row), None
            token = secrets.token_urlsafe(32)
            result = {"id": digest(token), "csrf": secrets.token_urlsafe(32), "created": time.time(), "reviewer": None, "invite_id": None}
            con.execute("INSERT INTO sessions(id,csrf,created) VALUES (:id,:csrf,:created)", result)
            return result, token

    def limit(self, bucket: str, max_count: int, seconds: int) -> None:
        now = time.time()
        with self.connect(write=True) as con:
            con.execute("DELETE FROM limits WHERE expires<?", (now,))
            row = con.execute("SELECT count FROM limits WHERE bucket=?", (bucket,)).fetchone()
            if row and row[0] >= max_count:
                raise ArenaError("操作过于频繁，请稍后再试。", 429)
            con.execute("INSERT INTO limits VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1", (bucket, now + seconds))

    def issue_invite(self, label: str, days: int = 7) -> str:
        code = secrets.token_urlsafe(24)
        with self.connect(write=True) as con:
            con.execute("INSERT INTO invites VALUES (?,?,?,?,NULL)", (digest(code), label, time.time(), time.time() + days * 86400))
        return code

    def join(self, session_id: str, code: str) -> str:
        with self.connect(write=True) as con:
            session = con.execute("SELECT reviewer FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session["reviewer"]:
                return session["reviewer"]
            invitation = con.execute("SELECT * FROM invites WHERE hash=?", (digest(code),)).fetchone()
            if not invitation or invitation["redeemed"] or invitation["expires"] < time.time():
                raise ArenaError("邀请码无效、已使用或已过期。", 403)
            reviewer = "R-" + secrets.token_hex(4).upper()
            con.execute("UPDATE invites SET redeemed=? WHERE hash=?", (time.time(), digest(code)))
            con.execute("UPDATE sessions SET reviewer=?,invite_id=? WHERE id=?", (reviewer, digest(code), session_id))
            return reviewer

    def add_match(self, match: Match, *, published: bool = False) -> None:
        raw = canonical(match.model_dump(mode="json"))
        with self.connect(write=True) as con:
            old = con.execute("SELECT digest FROM matches WHERE id=?", (match.id,)).fetchone()
            if old:
                if old[0] != digest(raw):
                    raise ArenaError("已有对战不可改写；请创建新版本。", 409)
                return
            if match.provenance == "platform_run":
                run = con.execute("SELECT status,payload FROM runs WHERE id=?", (match.run_id,)).fetchone()
                if not run or run["status"] != "completed" or json.loads(run["payload"]).get("match_digest") != digest(raw):
                    raise ArenaError("正式对战必须与平台完成的原始运行一致。", 409)
            con.execute("INSERT INTO matches VALUES (?,?,?,?,?,?,NULL,?)", (match.id, raw, digest(raw), match.provenance, match.category, int(published), time.time()))

    def publish(self, match_id: str) -> None:
        with self.connect(write=True) as con:
            row = con.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
            if not row:
                raise ArenaError("对战不存在。", 404)
            if row["invalid_reason"]:
                raise ArenaError("撤销的对战不能重新发布。", 409)
            match = Match.model_validate_json(row["payload"])
            for answer in match.answers:
                for participant in (a.participant for a in match.answers):
                    if participant.name.casefold() in answer.content.casefold():
                        raise ArenaError("正文包含参赛名称，不满足匿名发布条件。", 409)
            con.execute("UPDATE matches SET published=1 WHERE id=?", (match_id,))
            if match.run_id:
                con.execute("UPDATE questions SET status='published' WHERE run_id=?", (match.run_id,))

    def invalidate(self, match_id: str, reason: str) -> None:
        if not reason.strip():
            raise ArenaError("撤销必须提供原因。")
        with self.connect(write=True) as con:
            result = con.execute("UPDATE matches SET published=0,invalid_reason=? WHERE id=? AND invalid_reason IS NULL", (reason, match_id))
            if not result.rowcount:
                raise ArenaError("对战不存在或已经撤销。", 409)
            con.execute("UPDATE questions SET status='withdrawn' WHERE run_id=(SELECT json_extract(payload,'$.run_id') FROM matches WHERE id=?)", (match_id,))

    def assign(self, session_id: str, mode: str, category: str | None, *, question_id: str | None = None) -> dict | None:
        provenance = "demo" if mode == "demo" else "platform_run"
        with self.connect(write=True) as con:
            target = None
            if question_id:
                question = con.execute("SELECT run_id,status FROM questions WHERE id=? AND session_id=?", (question_id, session_id)).fetchone()
                if not question or question["status"] != "published" or mode != "live":
                    raise ArenaError("该题尚未发布或不属于当前会话。", 404)
                target = "run-" + question["run_id"]
                previous = con.execute("SELECT id FROM assignments WHERE session_id=? AND match_id=?", (session_id, target)).fetchone()
                if previous:
                    return self.assignment(session_id, previous[0])
            # Resume an unfinished assignment instead of exposing more pairs on retries.
            current = con.execute("""SELECT a.id FROM assignments a JOIN matches m ON m.id=a.match_id
                LEFT JOIN votes v ON v.assignment_id=a.id
                WHERE a.session_id=? AND a.skipped=0 AND v.assignment_id IS NULL
                AND m.published=1 AND m.invalid_reason IS NULL AND m.provenance=?
                AND (? IS NULL OR m.category=?) AND (? IS NULL OR m.id=?)
                ORDER BY a.created DESC LIMIT 1""", (session_id, provenance, category, category, target, target)).fetchone()
            if current:
                assignment_id = current[0]
            else:
                row = con.execute("""SELECT m.id,COUNT(a.id) AS exposures FROM matches m
                    LEFT JOIN assignments a ON a.match_id=m.id
                    WHERE m.published=1 AND m.invalid_reason IS NULL AND m.provenance=?
                    AND (? IS NULL OR m.category=?) AND (? IS NULL OR m.id=?) AND m.id NOT IN
                    (SELECT match_id FROM assignments WHERE session_id=?)
                    GROUP BY m.id ORDER BY exposures, random() LIMIT 1""", (provenance, category, category, target, target, session_id)).fetchone()
                if not row:
                    return None
                assignment_id = uuid.uuid4().hex
                con.execute("INSERT INTO assignments VALUES (?,?,?,?,?,0)", (assignment_id, session_id, row["id"], secrets.randbelow(2), time.time()))
        return self.assignment(session_id, assignment_id)

    def _owned(self, con: sqlite3.Connection, session_id: str, assignment_id: str) -> sqlite3.Row:
        row = con.execute("""SELECT a.*,m.payload,m.provenance,m.digest,m.invalid_reason,m.published,
            v.choice,v.reasons,v.eligible,v.created AS voted_at
            FROM assignments a JOIN matches m ON m.id=a.match_id
            LEFT JOIN votes v ON v.assignment_id=a.id WHERE a.id=? AND a.session_id=?""", (assignment_id, session_id)).fetchone()
        if not row:
            raise ArenaError("评测不存在或不属于当前会话。", 404)
        return row

    def assignment(self, session_id: str, assignment_id: str) -> dict:
        with self.connect() as con:
            row = self._owned(con, session_id, assignment_id)
        match = Match.model_validate_json(row["payload"])
        answers = list(reversed(match.answers)) if row["flipped"] else match.answers
        revealed = row["choice"] is not None
        return {
            "id": assignment_id, "question": match.question, "category": match.category,
            "as_of": match.as_of, "evidence": [e.model_dump() for e in match.evidence],
            "mode": "demo" if row["provenance"] == "demo" else "live",
            "answers": [{"side": side, "content": answer.content, **({"participant": answer.participant.model_dump(), "duration_seconds": answer.duration_seconds} if revealed else {})} for side, answer in zip(["left", "right"], answers)],
            "vote": {"choice": row["choice"], "reasons": json.loads(row["reasons"]), "counted": bool(row["eligible"]) and not bool(row["invalid_reason"]), "created_at": iso(row["voted_at"])} if revealed else None,
            "skipped": bool(row["skipped"]), "invalid_reason": row["invalid_reason"],
            "receipt": {"match_sha256": row["digest"], "run_id": match.run_id} if revealed else None,
        }

    def vote(self, session_id: str, assignment_id: str, choice: str, reasons: list[str]) -> dict:
        with self.connect(write=True) as con:
            row = self._owned(con, session_id, assignment_id)
            if row["choice"]:
                if row["choice"] != choice:
                    raise ArenaError("投票已锁定，揭晓身份后不能改票。", 409)
            else:
                if row["skipped"] or row["invalid_reason"] or not row["published"]:
                    raise ArenaError("这场评测已跳过或撤销，不能投票。", 409)
                reviewer = con.execute("SELECT reviewer FROM sessions WHERE id=?", (session_id,)).fetchone()[0]
                eligible = bool(reviewer) and row["provenance"] == "platform_run"
                con.execute("INSERT INTO votes VALUES (?,?,?,?,?)", (assignment_id, choice, canonical(sorted(set(reasons))), int(eligible), time.time()))
        return self.assignment(session_id, assignment_id)

    def skip(self, session_id: str, assignment_id: str) -> None:
        with self.connect(write=True) as con:
            row = self._owned(con, session_id, assignment_id)
            if row["choice"]:
                raise ArenaError("已投票的评测不能跳过。", 409)
            con.execute("UPDATE assignments SET skipped=1 WHERE id=?", (assignment_id,))

    def report(self, session_id: str, assignment_id: str, reason: str, detail: str) -> None:
        with self.connect(write=True) as con:
            self._owned(con, session_id, assignment_id)
            con.execute("INSERT OR IGNORE INTO reports VALUES (?,?,?,?)", (assignment_id, reason, detail, time.time()))

    def question(self, session_id: str, question: str, category: str) -> str:
        identifier = uuid.uuid4().hex
        with self.connect(write=True) as con:
            con.execute("INSERT INTO questions(id,session_id,question,category,created) VALUES (?,?,?,?,?)", (identifier, session_id, question, category, time.time()))
        return identifier

    def history(self, session_id: str) -> dict:
        with self.connect() as con:
            votes = con.execute("""SELECT a.id,m.payload,m.provenance,v.choice,v.eligible,v.created,m.invalid_reason
                FROM votes v JOIN assignments a ON a.id=v.assignment_id JOIN matches m ON m.id=a.match_id
                WHERE a.session_id=? ORDER BY v.created DESC LIMIT 100""", (session_id,)).fetchall()
            questions = con.execute("SELECT id,question,category,status,created FROM questions WHERE session_id=? ORDER BY created DESC LIMIT 50", (session_id,)).fetchall()
        return {"votes": [{"id": r["id"], "question": json.loads(r["payload"])["question"], "category": json.loads(r["payload"])["category"], "mode": "demo" if r["provenance"] == "demo" else "live", "choice": r["choice"], "counted": bool(r["eligible"]) and not bool(r["invalid_reason"]), "created_at": iso(r["created"])} for r in votes], "questions": [dict(r) for r in questions]}

    def summary(self) -> dict:
        with self.connect() as con:
            counts = {r[0]: r[1] for r in con.execute("SELECT provenance,COUNT(*) FROM matches WHERE published=1 AND invalid_reason IS NULL GROUP BY provenance")}
            votes = con.execute("""SELECT COUNT(*),COUNT(DISTINCT a.session_id) FROM votes v
                JOIN assignments a ON a.id=v.assignment_id JOIN matches m ON m.id=a.match_id
                WHERE v.eligible=1 AND m.provenance='platform_run' AND m.invalid_reason IS NULL AND m.published=1""").fetchone()
        return {"live_cases": counts.get("platform_run", 0), "demo_cases": counts.get("demo", 0), "formal_votes": votes[0], "reviewers": votes[1]}

    def leaderboard(self, category: str | None = None) -> dict:
        with self.connect() as con:
            matches = con.execute("SELECT * FROM matches WHERE published=1 AND invalid_reason IS NULL AND provenance='platform_run' AND (? IS NULL OR category=?)", (category, category)).fetchall()
            votes = con.execute("""SELECT a.match_id,a.flipped,a.session_id,v.choice FROM votes v
                JOIN assignments a ON a.id=v.assignment_id JOIN matches m ON m.id=a.match_id
                WHERE v.eligible=1 AND m.published=1 AND m.invalid_reason IS NULL
                AND m.provenance='platform_run' AND (? IS NULL OR m.category=?)""", (category, category)).fetchall()
        rows: dict[str, dict] = {}
        pairs: dict[tuple[str, str], dict] = {}
        participants = {}
        task_fingerprints = {}
        seen_reviewers: dict[str, set] = defaultdict(set)
        seen_cases: dict[str, set] = defaultdict(set)
        for record in matches:
            match = Match.model_validate_json(record["payload"])
            keys = []
            for answer in match.answers:
                p = answer.participant
                rows.setdefault(p.key, {"key": p.key, **p.model_dump(), "wins": 0, "losses": 0, "ties": 0, "both_bad": 0})
                keys.append(p.key)
            participants[match.id] = keys
            task_fingerprints[match.id] = digest(canonical(match.model_dump(mode="json", include={"question", "category", "as_of", "evidence"})))
        for vote in votes:
            keys = participants[vote["match_id"]]
            if vote["flipped"]:
                keys = keys[::-1]
            pair = tuple(sorted(keys))
            p = pairs.setdefault(pair, {"a": pair[0], "b": pair[1], "a_wins": 0, "b_wins": 0, "ties": 0, "both_bad": 0})
            choice = vote["choice"]
            for key in keys:
                seen_reviewers[key].add(vote["session_id"])
                seen_cases[key].add(task_fingerprints[vote["match_id"]])
            if choice in ("left", "right"):
                winner, loser = keys if choice == "left" else keys[::-1]
                rows[winner]["wins"] += 1
                rows[loser]["losses"] += 1
                p["a_wins" if winner == pair[0] else "b_wins"] += 1
            else:
                metric = "ties" if choice == "tie" else "both_bad"
                p[metric] += 1
                for key in keys:
                    rows[key][metric] += 1
        for key, row in rows.items():
            decisive = row["wins"] + row["losses"]
            row.update({"decisive": decisive, "win_rate": row["wins"] / decisive if decisive else None, "votes": decisive + row["ties"] + row["both_bad"], "reviewers": len(seen_reviewers[key]), "cases": len(seen_cases[key]), "status": "observed" if decisive >= 30 and len(seen_reviewers[key]) >= 10 and len(seen_cases[key]) >= 5 else "collecting"})
        return {"rows": sorted(rows.values(), key=lambda r: (r["name"], r["version"])), "pairs": list(pairs.values()), "formal_votes": len(votes), "method": "decisive-v1", "minimum": {"decisive": 30, "reviewers": 10, "cases": 5}}

    def create_run(self, payload: dict, question_id: str | None = None) -> str:
        identifier = uuid.uuid4().hex
        with self.connect(write=True) as con:
            if question_id:
                question = con.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
                task = payload.get("task", {})
                if not question or question["status"] != "pending" or (question["question"], question["category"]) != (task.get("question"), task.get("category")):
                    raise ArenaError("题目不匹配或已执行；不能重复发起付费运行。", 409)
                con.execute("UPDATE questions SET status='running',run_id=? WHERE id=?", (identifier, question_id))
            con.execute("INSERT INTO runs VALUES (?,?, 'running',?,NULL)", (identifier, time.time(), canonical(payload)))
        return identifier

    def finish_run(self, identifier: str, payload: dict, error: str | None = None) -> None:
        with self.connect(write=True) as con:
            result = con.execute("UPDATE runs SET status=?,payload=?,error=? WHERE id=? AND status='running'", ("failed" if error else "completed", canonical(payload), error, identifier))
            if not result.rowcount:
                raise ArenaError("运行已结束或不存在，不能覆盖。", 409)
            con.execute("UPDATE questions SET status=? WHERE run_id=?", ("failed" if error else "review", identifier))

    def add_strategy(self, strategy: Strategy) -> None:
        if strategy.starts_at <= datetime.now(timezone.utc):
            raise ArenaError("策略必须在生效前登记，不能回填历史业绩。")
        raw = canonical(strategy.model_dump(mode="json"))
        with self.connect(write=True) as con:
            run = con.execute("SELECT status,payload FROM runs WHERE id=?", (strategy.source_run_id,)).fetchone()
            if not run or run["status"] != "completed":
                raise ArenaError("策略需要绑定平台已完成的运行。")
            participants = json.loads(run["payload"]).get("participants", [])
            if strategy.participant.model_dump() not in participants:
                raise ArenaError("策略身份与来源运行不一致。")
            try:
                con.execute("INSERT INTO strategies VALUES (?,?,?,?)", (strategy.id, raw, digest(raw), time.time()))
            except sqlite3.IntegrityError as exc:
                raise ArenaError("策略已登记，不允许覆盖。", 409) from exc

    def strategies(self) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM strategies ORDER BY registered DESC").fetchall()
        now = datetime.now(timezone.utc)
        result = []
        for row in rows:
            strategy = Strategy.model_validate_json(row["payload"])
            result.append({"id": strategy.id, "title": strategy.title, "participant": strategy.participant.model_dump(), "benchmark": strategy.benchmark, "starts_at": strategy.starts_at.isoformat(), "ends_at": strategy.ends_at.isoformat(), "registered_at": iso(row["registered"]), "sha256": row["digest"], "holdings_count": len(strategy.holdings), "status": "scheduled" if now < strategy.starts_at else "awaiting_audit" if now >= strategy.ends_at else "observing", "net_return": None, "excess_return": None})
        return result
