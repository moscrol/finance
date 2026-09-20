from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path

from .app import data_path
from .models import Strategy
from .runner import Task, load_agents, run_pair
from .store import ArenaStore


def main() -> None:
    parser = argparse.ArgumentParser(description="FinArena operator commands (no public admin API)")
    parser.add_argument("--db", type=Path, default=data_path())
    commands = parser.add_subparsers(dest="command", required=True)
    invite = commands.add_parser("invite")
    invite.add_argument("--label", required=True)
    invite.add_argument("--days", type=int, default=7, choices=range(1, 31))
    run = commands.add_parser("run")
    run.add_argument("--agents", type=Path, required=True)
    run.add_argument("--task", type=Path, required=True)
    run.add_argument("--question-id", help="Optional queued question ID; task question/category must match exactly")
    run.add_argument("--timeout", type=float, default=120)
    run.add_argument("--allow-local-endpoints", action="store_true")
    publish = commands.add_parser("publish")
    publish.add_argument("--match", required=True)
    publish.add_argument("--reviewed-for-identity-and-data-rights", action="store_true", required=True)
    revoke = commands.add_parser("invalidate")
    revoke.add_argument("--match", required=True)
    revoke.add_argument("--reason", required=True)
    recover = commands.add_parser("recover-run", help="确认远端已停止后，将遗留 running 运行标记为失败")
    recover.add_argument("--run", required=True)
    recover.add_argument("--reason", required=True)
    strategy = commands.add_parser("register-strategy")
    strategy.add_argument("--file", type=Path, required=True)
    commands.add_parser("queue")
    commands.add_parser("runs")
    commands.add_parser("reports")
    args = parser.parse_args()
    store = ArenaStore(args.db)
    if args.command == "invite":
        print(store.issue_invite(args.label, args.days))
    elif args.command == "run":
        print(asyncio.run(run_pair(store, Task.model_validate_json(args.task.read_text()), load_agents(args.agents), timeout=args.timeout, allow_local=args.allow_local_endpoints, question_id=args.question_id)))
    elif args.command == "publish":
        actor = os.environ.get("ARENA_OPERATOR", getpass.getuser())
        store.publish(args.match, actor=actor, review_attested=args.reviewed_for_identity_and_data_rights)
        print("Published:", args.match)
    elif args.command == "invalidate":
        actor = os.environ.get("ARENA_OPERATOR", getpass.getuser())
        store.invalidate(args.match, args.reason, actor=actor)
        print("Invalidated:", args.match)
    elif args.command == "recover-run":
        actor = os.environ.get("ARENA_OPERATOR", getpass.getuser())
        store.recover_run(args.run, args.reason, actor=actor)
        print("Recovered as failed:", args.run)
    elif args.command == "register-strategy":
        store.add_strategy(Strategy.model_validate_json(args.file.read_text()))
        print("Registered; no performance asserted")
    else:
        query = {"queue": "SELECT id,question,category,status FROM questions ORDER BY created DESC LIMIT 100", "runs": "SELECT id,status,error,payload FROM runs ORDER BY created DESC LIMIT 100", "reports": "SELECT * FROM reports ORDER BY created DESC LIMIT 100"}[args.command]
        with store.connect() as con:
            print(json.dumps([dict(r) for r in con.execute(query)], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
