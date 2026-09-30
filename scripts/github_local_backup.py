#!/usr/bin/env python3
"""GitHub -> local Gitea backup, with standalone bundles and read-only API exports.

The installed copy lives outside any development worktree. Only Gitea receives
pushes. Source deletions are retained; non-fast-forward tips get archival refs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

LABEL = "com.a77.finance-github-local-backup"


def command(argv: list[str], *, check: bool = True, timeout: int = 600) -> str:
    result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout,
                            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if check and result.returncode:
        # Credentials and untrusted response bodies must not enter service logs.
        operation = argv[3] if len(argv) > 3 and argv[1] == "--git-dir" else argv[1]
        raise RuntimeError(f"{Path(argv[0]).name} {operation} command failed (exit {result.returncode})")
    return result.stdout.strip()


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".partial")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temp.chmod(0o600)
    temp.replace(path)


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def validate(settings: dict, *, local_fixture: bool = False) -> None:
    source, target = settings["source"], settings["target"]
    if source == target:
        raise ValueError("source and backup destination must differ")
    if local_fixture:
        if not all(Path(url).is_absolute() for url in (source, target)):
            raise ValueError("fixtures require absolute local repository paths")
        return
    github, gitea = urllib.parse.urlsplit(source), urllib.parse.urlsplit(target)
    if (github.scheme != "https" or github.hostname != "github.com"
            or github.username or github.password or github.query or github.fragment):
        raise ValueError("source must be a credential-free GitHub HTTPS URL")
    if (gitea.scheme not in {"http", "https"}
            or gitea.hostname not in {"localhost", "127.0.0.1", "::1"}
            or gitea.username or gitea.password or gitea.query or gitea.fragment):
        raise ValueError("backup destination must be credential-free local Gitea")
    if len(github.path.strip("/").removesuffix(".git").split("/")) != 2:
        raise ValueError("GitHub source must name owner/repository")


def git(repository: Path, *args: str) -> str:
    return command(["git", "--git-dir", str(repository), *args])


def remote_refs(repository: Path, remote: str) -> dict[str, str]:
    rows = git(repository, "ls-remote", "--heads", "--tags", remote)
    return {ref: sha for sha, ref in (row.split() for row in rows.splitlines())
            if not ref.endswith("^{}")}


def gitea_api(settings: dict, path: str) -> object:
    url = urllib.parse.urlsplit(settings["target"])
    repo = url.path.removesuffix(".git").strip("/")
    token = command(["security", "find-generic-password", "-s", "gitea-local",
                     "-a", "a77-token", "-w"], timeout=30)
    request = urllib.request.Request(f"{url.scheme}://{url.netloc}/api/v1/repos/{repo}{path}")
    request.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def export_metadata(settings: dict, directory: Path) -> dict:
    slug = urllib.parse.urlsplit(settings["source"]).path.strip("/").removesuffix(".git")
    prefix = f"repos/{slug}"
    exports = {
        "issues": "issues?state=all&per_page=100",
        "pulls": "pulls?state=all&per_page=100",
        "issue-comments": "issues/comments?per_page=100",
        "pull-comments": "pulls/comments?per_page=100",
        "releases": "releases?per_page=100",
        "labels": "labels?per_page=100",
        "milestones": "milestones?state=all&per_page=100",
    }
    write_json(directory / "repository.json", json.loads(command(["gh", "api", prefix])))
    counts = {}
    for name, endpoint in exports.items():
        pages = json.loads(command(["gh", "api", "--paginate", "--slurp", f"{prefix}/{endpoint}"]))
        rows = [row for page in pages for row in page]
        write_json(directory / f"{name}.json", rows)
        counts[name] = len(rows)
        if name == "pulls":
            for pull in rows:
                number = int(pull["number"])
                reviews = json.loads(command(["gh", "api", "--paginate", "--slurp",
                                              f"{prefix}/pulls/{number}/reviews?per_page=100"]))
                write_json(directory / f"pull-{number}-reviews.json",
                           [row for page in reviews for row in page])
    # Existing Gitea work stays discoverable without re-publishing its branches.
    write_json(directory / "legacy-gitea-open-pulls.json",
               gitea_api(settings, "/pulls?state=open&limit=50"))
    return counts


def backup(settings: dict, *, local_fixture: bool = False) -> dict:
    validate(settings, local_fixture=local_fixture)
    state = Path(settings["state_dir"])
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    repository = state / "repository.git"
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    day = now.astimezone(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
    snapshot = Path(settings["snapshot_dir"]) / day
    snapshot.mkdir(parents=True, exist_ok=True)
    snapshot.chmod(0o700)
    if not repository.exists():
        command(["git", "init", "--bare", "--initial-branch=main", str(repository)])
        git(repository, "remote", "add", "github", settings["source"])
        git(repository, "remote", "add", "gitea", settings["target"])
    for remote, expected in (("github", settings["source"]), ("gitea", settings["target"])):
        if git(repository, "remote", "get-url", remote) != expected:
            raise ValueError("installed remote changed; inspect before running backup")
        git(repository, "config", f"remote.{remote}.mirror", "false")
    git(repository, "remote", "set-url", "--push", "github", str(state / "SOURCE_PUSH_DISABLED"))
    git(repository, "config", "remote.pushDefault", "gitea")
    git(repository, "fetch", "--no-tags", "--no-prune", "github",
        "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*")
    source = remote_refs(repository, "github")
    if "refs/heads/main" not in source:
        raise ValueError("GitHub main is missing; keep existing backup unchanged")
    # Pin exact observed objects even if another agent pushes during this run.
    for ref, sha in source.items():
        exists = subprocess.run(["git", "--git-dir", str(repository), "cat-file", "-e", sha],
                                capture_output=True).returncode == 0
        if not exists:
            git(repository, "fetch", "--no-tags", "github", sha)
        git(repository, "update-ref", ref, sha)
    fingerprint = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    bundle = snapshot / "repository.bundle"
    previous_path = snapshot / "manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    if previous.get("source_fingerprint") != fingerprint or not bundle.exists():
        pending = snapshot / "repository.partial.bundle"
        git(repository, "bundle", "create", str(pending), "--all")
        git(repository, "bundle", "verify", str(pending))
        pending.replace(bundle)
    bundle_sha = digest(bundle)
    if previous.get("source_fingerprint") == fingerprint and previous.get("bundle_sha256"):
        if bundle_sha != previous["bundle_sha256"]:
            raise ValueError("existing daily bundle checksum changed")
    result = dict(schema_version="github-local-backup/v1", started_at=now.isoformat(),
                  source_fingerprint=fingerprint, source_refs=source, bundle=str(bundle),
                  bundle_sha256=bundle_sha, backup_refs={}, archived=[], updated=[],
                  retained_only=[], metadata={}, status="local_snapshot_ready")
    write_json(snapshot / "manifest.json", result)
    write_json(state / "status.json", result)
    if not local_fixture and gitea_api(settings, "/push_mirrors"):
        raise ValueError("Gitea push mirror is active; backup push refused")
    target = remote_refs(repository, "gitea")
    operations = []
    for ref, sha in source.items():
        destination = ref
        old = target.get(ref)
        if old and old != sha:
            ancestor = False
            if ref.startswith("refs/heads/"):
                git(repository, "fetch", "--no-tags", "gitea", old)
                ancestor = subprocess.run(["git", "--git-dir", str(repository),
                                           "merge-base", "--is-ancestor", old, sha],
                                          capture_output=True).returncode == 0
            if not ancestor:
                kind, name = ref.removeprefix("refs/").split("/", 1)
                destination = f"refs/{kind}/backup/github/{stamp}/{name}"
                result["archived"].append(dict(source_ref=ref, backup_ref=destination, sha=sha))
        result["backup_refs"][ref] = destination
        if target.get(destination) != sha:
            operations.append(f"{sha}:{destination}")
            result["updated"].append(destination)
    if operations:
        git(repository, "push", "--atomic", "gitea", *operations)
    observed = remote_refs(repository, "gitea")
    for ref, destination in result["backup_refs"].items():
        if observed.get(destination) != source[ref]:
            raise ValueError("Gitea readback differs from the pinned source snapshot")
    # An append-only backup must not delete or silently change historical tips.
    for ref, sha in target.items():
        if ref not in result["updated"] and observed.get(ref) != sha:
            raise ValueError("pre-existing backup ref changed during synchronization")
    result["retained_only"] = sorted(set(target) - set(source))
    if not local_fixture:
        result["metadata"] = export_metadata(settings, snapshot / "metadata")
    result.update(status="success", finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
    write_json(snapshot / "manifest.json", result)
    write_json(state / "status.json", result)
    write_json(state / "last-success.json", result)
    return result


def run(settings: dict) -> int:
    state = Path(settings["state_dir"])
    state.mkdir(parents=True, exist_ok=True)
    with (state / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("backup already running", flush=True)
            return 0
        try:
            result = backup(settings)
            print(json.dumps({"status": result["status"], "source_refs": len(result["source_refs"]),
                              "updated": len(result["updated"]), "archived": len(result["archived"]),
                              "bundle": result["bundle"], "finished_at": result["finished_at"]}), flush=True)
            return 0
        except Exception as exc:
            error = {"status": "failed", "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                     "error_type": type(exc).__name__}
            if isinstance(exc, (ValueError, RuntimeError)):
                error["reason"] = str(exc)
            # Keep the previous successful status/snapshot for recovery.
            write_json(state / "last-error.json", error)
            print(json.dumps(error), flush=True)
            return 1


def install(repo: Path, state: Path, snapshots: Path, interval: int) -> None:
    settings = dict(source=command(["git", "-C", str(repo), "remote", "get-url", "origin"]),
                    target=command(["git", "-C", str(repo), "remote", "get-url", "gitea"]),
                    state_dir=str(state), snapshot_dir=str(snapshots), interval_seconds=interval)
    validate(settings)
    if interval < 300:
        raise ValueError("backup interval must be at least five minutes")
    gh = shutil.which("gh")
    if gh is None:
        raise ValueError("gh must be installed and authenticated before installing backup")
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    runner = state / "runner.py"
    if Path(__file__).resolve() != runner.resolve():
        shutil.copy2(__file__, runner)
    runner.chmod(0o700)
    write_json(state / "config.json", settings)
    logs = Path.home() / "Library/Logs" / f"{LABEL}.log"
    logs.parent.mkdir(parents=True, exist_ok=True)
    logs.touch(exist_ok=True)
    logs.chmod(0o600)
    plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    definition = dict(Label=LABEL, RunAtLoad=True, StartInterval=interval,
                      ProgramArguments=[sys.executable, str(runner), "run", "--config", str(state / "config.json")],
                      WorkingDirectory=str(state), StandardOutPath=str(logs), StandardErrorPath=str(logs),
                      ProcessType="Background", EnvironmentVariables={
                          "PATH": f"{Path(gh).parent}:/usr/bin:/bin",
                          "HOME": str(Path.home()), "GIT_TERMINAL_PROMPT": "0"})
    if plist.exists():
        shutil.copy2(plist, state / "previous-launch-agent.plist")
        command(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], check=False, timeout=30)
    plist.write_bytes(plistlib.dumps(definition))
    plist.chmod(0o600)
    command(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)], timeout=30)
    print(json.dumps({"installed": LABEL, "interval_seconds": interval, "config": str(state / "config.json")}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    setup = sub.add_parser("install")
    setup.add_argument("--repo", type=Path, required=True)
    setup.add_argument("--state-dir", type=Path, default=Path.home() / ".finance-runtime/github-backup/finance")
    setup.add_argument("--snapshot-dir", type=Path, default=Path.home() / "backups/github-finance")
    setup.add_argument("--interval", type=int, default=3600)
    execute = sub.add_parser("run")
    execute.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "install":
        install(args.repo.resolve(), args.state_dir.expanduser().resolve(),
                args.snapshot_dir.expanduser().resolve(), args.interval)
        return 0
    return run(json.loads(args.config.read_text()))


if __name__ == "__main__":
    raise SystemExit(main())
