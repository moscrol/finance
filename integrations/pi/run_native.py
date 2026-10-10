"""One Pi-native first attempt with the knevo skill layer mounted.

与 2026-10-09 同模型对照的 ``run_pair.py`` 同源，只保留 Pi 这一臂，并把 skill 层挂上：
``finance-mode`` 常驻、专项按需、``spawn_sub_agent`` 只读派单。数据仍走共享工具注册表
（``bridge.py``），库是只读 APFS 克隆，模型请求逐条落盘并做身份核对。

用法（都在被验证的工作树里跑，解释器用 ``.venv-workbench/bin/python``）::

    python integrations/pi/run_native.py prepare --root <产物目录> --db <源库> \
        --question-file q.txt --as-of 2026-09-30 [--today ...] [--latest-data-date ...] \
        [--skills finance-mode,finance-market-review,...] [--second-look]
    python integrations/pi/run_native.py run --root <产物目录>
    python integrations/pi/run_native.py run --root <产物目录> --dry-run   # 只打印命令，不花钱

prepare 把输入冻结进 plan.json（代码 revision、库哈希、kit 哈希、问题、截止日、skill 清单），
run 先校验冻结再执行；两者分开是为了让「跑之前输入是什么」永远可回读。
凭证从生产启动器的 ``export`` 行读取，不执行启动器本身。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
KIT_FILES = ("finance-mode.ts", "bridge.py", "rag_binding.py", "model_view.py", "delivery-prompts.json")
DEFAULT_SKILLS = ("finance-mode", "finance-market-review", "finance-analyze-stock",
                  "finance-industry-track", "finance-forecast-event")
DEFAULT_LAUNCHER = Path.home() / ".local/bin/start-finance-workbench"
PROCESSES: list[subprocess.Popen] = []


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(code: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=code, text=True).strip()


def require_clean_code(code: Path) -> None:
    if git(code, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("commit or isolate all source changes before freezing/running an experiment")


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().split("\n") if line.strip()]


def delivered_packet(source: Path) -> tuple[dict, dict, dict[str, str]]:
    """Recover only verified public tool deliveries, never drafts or private receipts."""
    source = source.resolve()
    if not (source / "capture-manifest.json").resolve().is_relative_to(source):
        raise ValueError("source manifest escapes its run directory")
    manifest = json.loads((source / "capture-manifest.json").read_text())
    names = ("plan.json", "RESULT.json", "pi-tools.jsonl", "pi-model-requests.jsonl")
    hashes = {"capture-manifest.json": digest(source / "capture-manifest.json")}
    for name in names:
        path = source / name
        if not path.resolve().is_relative_to(source):
            raise ValueError("source artifact escapes its run directory")
        expected = manifest.get(name, {})
        if digest(path) != expected.get("sha256") or path.stat().st_size != expected.get("bytes"):
            raise ValueError(f"source artifact does not match capture manifest: {name}")
        hashes[name] = expected["sha256"]
    plan = json.loads((source / "plan.json").read_text())
    result = json.loads((source / "RESULT.json").read_text())
    if (result.get("status") != "completed" or result.get("inputs_unchanged") is not True
            or result.get("processes_stopped") is not True or not arm_completed(result.get("arm", {}))):
        raise ValueError("source run lacks a complete, admitted and stable delivery")
    def canonical(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    sent = set()
    for request in read_jsonl(source / "pi-model-requests.jsonl"):
        for message in request["payload"].get("messages", []):
            if message.get("role") != "tool" or not isinstance(message.get("content"), str):
                continue
            try:
                content = json.loads(message["content"])
            except ValueError:
                continue
            if isinstance(content, dict) and isinstance(content.get("observation"), dict):
                sent.add(canonical(content["observation"]))
    observations = []
    for record in read_jsonl(source / "pi-tools.jsonl"):
        public = record.get("model_observation")
        if not isinstance(public, dict) or {"telemetry", "trace"} & public.keys():
            raise ValueError("source lacks a public-only model observation")
        if canonical(public) not in sent:
            raise ValueError("source observation was not delivered to the model")
        observations.append({"id": f"O{len(observations) + 1}", "tool": record["tool"],
                             "arguments": record.get("arguments", {}), "result": public})
    if not observations:
        raise ValueError("source has no delivered observations")
    return ({"question": plan["question"], "information_cutoff": plan["information_cutoff"],
             "observations": observations}, plan, hashes)


def _numeric_checker(code: Path):
    sys.path.insert(0, str(code))
    from intelligence.eval import frozen_numeric_checks  # noqa: PLC0415
    if Path(frozen_numeric_checks.__file__).resolve() != (code / "intelligence/eval/frozen_numeric_checks.py").resolve():
        raise RuntimeError("numeric checker was loaded from a different source tree")
    return frozen_numeric_checks


def numeric_check_receipt(packet: dict, code: Path) -> dict:
    return _numeric_checker(code).compile_numeric_checks(packet)


def numeric_check_document(receipt: dict, code: Path) -> str:
    return _numeric_checker(code).render_numeric_checks(receipt)


def delivery_method_received(plan: dict, requests: list[dict]) -> bool:
    if not requests:
        return False
    text = (Path(plan["code_root"]) / "skills" / plan["delivery_skill"] / "SKILL.md").read_text()
    _, separator, body = text.partition("\n---\n")
    body = body.strip() if separator else text.strip()
    system = []
    for message in requests[0]["payload"].get("messages", []):
        if message.get("role") != "system":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            system.append(content)
        elif isinstance(content, list):
            system.extend(part["text"] for part in content if part.get("type") == "text")
    return bool(body) and body in "\n".join(system)


def arm_completed(arm: dict) -> bool:
    return (arm.get("exit") == 0 and arm.get("stop_reason") == "stop"
            and arm.get("model_admission") is True and arm.get("answer_chars", 0) > 0)


def launcher_exports(path: Path) -> dict[str, str]:
    """Read ``export KEY=value`` lines without executing the launcher."""
    exports: dict[str, str] = {}
    if not path.is_file():
        return exports
    pattern = re.compile(r'^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$')
    for line in path.read_text().splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        exports[key] = value
    return exports


def resolve_api_key(value: str | None) -> str:
    """Resolve only literals or the launcher's read-only macOS Keychain reference."""
    if not value:
        raise RuntimeError("existing GLM credential unavailable; no request made")
    if "$" not in value and "`" not in value:
        return value
    if not (value.startswith("$(") and value.endswith(")")):
        raise ValueError("unresolved credential expression; pass a resolved key in the environment")
    tokens = shlex.split(value[2:-1])
    if tokens[-3:] == ["2>/dev/null", "||", "true"]:
        tokens = tokens[:-3]
    elif tokens[-1:] == ["2>/dev/null"]:
        tokens = tokens[:-1]
    if (len(tokens) != 7 or tokens[0] not in ("security", "/usr/bin/security")
            or tokens[1] != "find-generic-password" or tokens[-1] != "-w"
            or {tokens[2], tokens[4]} != {"-a", "-s"}
            or any(char in "".join(tokens[2:]) for char in ("$", "`", ";", "|", "&"))):
        raise ValueError("unsupported credential command; launcher is never executed")
    result = subprocess.run(["/usr/bin/security", *tokens[1:]], capture_output=True,
                            text=True, timeout=10, check=False)
    key = result.stdout.strip()
    if result.returncode != 0 or not key:
        raise RuntimeError("GLM Keychain credential unavailable; no request made")
    return key


_LAUNCHER_SKIP_PREFIXES = ("LLM_", "OPENAI_", "ASK_", "WORKBENCH_", "FORESIGHT_USER", "AGENT_RUNTIME_")
_LAUNCHER_SKIP_EXACT = {"PATH", "PYTHONPATH", "WORKBENCH_REPO_ROOT", "FORESIGHT_USERS_DIR", "FORESIGHT_USER"}


def environment(plan: dict, root: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("LLM_", "OPENAI_", "ASK_JUDGE")):
            env.pop(key, None)
    exports = launcher_exports(Path(plan["launcher"]))
    for key, value in exports.items():
        if key in _LAUNCHER_SKIP_EXACT or key.startswith(_LAUNCHER_SKIP_PREFIXES):
            continue
        env.setdefault(key, value)
    api_key = resolve_api_key(env.get("FORESIGHT_BUILTIN_LLM_API_KEY") or exports.get("FORESIGHT_BUILTIN_LLM_API_KEY"))
    base_url = env.get("FORESIGHT_BUILTIN_LLM_BASE_URL") or exports.get("FORESIGHT_BUILTIN_LLM_BASE_URL")
    assert api_key and base_url, "existing GLM credential unavailable; no request made"
    code = plan["code_root"]
    env.update({
        "FORESIGHT_BUILTIN_LLM_API_KEY": api_key, "FORESIGHT_BUILTIN_LLM_BASE_URL": base_url,
        "LLM_API_KEY": api_key, "LLM_BASE_URL": base_url,
        "LLM_MODEL": plan["model"], "FORESIGHT_BUILTIN_LLM_MODEL": plan["model"],
        "LLM_AGENT_MAX_TOKENS_BY_MODEL": "glm-5:32768",
        "LLM_THINKING": "disabled", "LLM_TIMEOUT": "300",
        "WORKBENCH_REPO_ROOT": code, "PYTHONPATH": code, "PYTHONDONTWRITEBYTECODE": "1",
        "FINANCE_WS": exports.get("FINANCE_WS", env.get("FINANCE_WS", str(Path.home() / "finance-workspace-private"))),
        "MARKET_FEATURE_STORE_DB": str(root / "market_feature_store.duckdb"),
        "FORESIGHT_USERS_DIR": str(root / "pi" / "users"),
        "FORESIGHT_EPISODE_STORE": str(root / "pi" / "native-store"),
        "FORESIGHT_USER": plan["user"],
        "FINANCE_MEMORY_VECTOR_CACHE_DIR": "off",
        "WORKBENCH_RESEARCH_TIER": plan["tier"], "WORKBENCH_TOOL_AUTHORIZATION": "all",
        "WORKBENCH_TOOL_MENU_HIDE": "off",
        "FINANCE_PI_ROOT": str(root), "FINANCE_PI_RAG_BINDINGS": plan["rag_bindings"],
        "FINANCE_PI_MODE": plan.get("mode", "research"),
        "FINANCE_PI_DELIVERY_STYLE": plan.get("delivery_style", "direct"),
        "FINANCE_PI_DELIVERY_SKILL": plan.get("delivery_skill") or "",
        "FINANCE_PI_BRIDGE_PORT": str(plan["bridge_port"]),
        "FINANCE_PI_BRIDGE_URL": f"http://127.0.0.1:{plan['bridge_port']}",
        "FINANCE_PI_CASE": plan["case"], "FINANCE_PI_MODEL": plan["model"],
        "FINANCE_PI_SKILL_ROOT": str(Path(code) / "skills"),
        "FINANCE_PI_OS_SKILL": plan["os_skill"],
        "FINANCE_PI_APP_SKILLS": ",".join(plan["app_skills"]),
        "FINANCE_PI_SUBAGENT_DEPTH": "0",
        "FINANCE_PI_SUBAGENTS": "1" if plan["subagents"] else "0",
        "FINANCE_PI_MENU_FILE": str(root / "pi" / "menu.json"),
        "PI_CODING_AGENT_DIR": str(root / "pi" / "agent"),
        "FINANCE_PI_SECOND_LOOK": "1" if plan["second_look"] else "0",
        "FINANCE_PI_THINKING": plan["thinking"], "FINANCE_PI_BIN": plan["pi_bin"],
    })
    return env


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def spawn(command: list[str], log: Path, env: dict[str, str], cwd: Path) -> subprocess.Popen:
    with log.open("xb") as stream:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    PROCESSES.append(process)
    return process


def call(port: int, path: str, payload=None, timeout: float = 15):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                     headers={} if data is None else {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def port_free(port: int) -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def prepare(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    code = Path(args.code_root).resolve()
    assert not root.exists(), "use a new experiment directory; existing evidence is never overwritten"
    require_clean_code(code)
    for name in (args.os_skill, *args.app_skills):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError(f"invalid skill name: {name}")
        assert (code / "skills" / name / "SKILL.md").is_file(), f"missing skill: {name}"
    assert port_free(args.bridge_port), f"port occupied: {args.bridge_port}"
    packet = source_plan = source_hashes = None
    if args.source_run:
        if args.analysis_only and (not args.numeric_checks or args.delivery_style != "direct"):
            raise ValueError("--analysis-only requires direct delivery with --numeric-checks")
        if not args.delivery_skill or args.delivery_skill not in args.app_skills:
            raise ValueError("delivery requires an explicit --delivery-skill from the mounted application skills")
        if args.question_file or args.as_of or args.second_look or args.subagents or args.rag_bindings not in (None, "off"):
            raise ValueError("delivery keeps the source question/cutoff and disables retrieval, second-look and subagents")
        packet, source_plan, source_hashes = delivered_packet(Path(args.source_run))
        if args.model != source_plan["model"]:
            raise ValueError("delivery comparison must keep the source model")
        args.as_of = source_plan["information_cutoff"]
        args.today = source_plan["today"]
        args.latest_data_date = source_plan["latest_data_date"]
        args.rag_bindings = "off"
        args.tool_cap = 0
    elif not args.question_file or not args.as_of or not args.rag_bindings:
        raise ValueError("research requires --db, --question-file, --as-of and --rag-bindings")
    elif args.delivery_style != "direct" or args.delivery_skill or args.numeric_checks or args.analysis_only:
        raise ValueError("delivery settings require --source-run")
    root.mkdir(parents=True, exist_ok=True)
    kit = root / "kit"
    kit.mkdir()
    for name in KIT_FILES:
        shutil.copyfile(HERE / name, kit / name)
    source_db = cloned = db_sha = None
    if packet is not None:
        save(root / "evidence-packet.json", packet)
        if args.numeric_checks:
            receipt = numeric_check_receipt(packet, code)
            save(root / "numeric-checks.json", receipt)
            if args.analysis_only:
                (root / "checked-facts.md").write_text(numeric_check_document(receipt, code))
        question = packet["question"]
    else:
        source_db = Path(args.db).resolve()
        sys.path.insert(0, str(code))
        from market_feature_store.db import clone_to_staging  # noqa: PLC0415
        cloned = clone_to_staging(source_db, root / "market_feature_store.duckdb")
        (root / "market_feature_store.duckdb").chmod(0o400)
        db_sha = digest(root / "market_feature_store.duckdb")
        question = Path(args.question_file).read_text().strip()
    (root / "question.txt").write_text(question + "\n")
    (root / "pi").mkdir()
    rag_bindings = "off"
    rag_hash = None
    if args.rag_bindings != "off":
        binding = root / "rag-bindings.json"
        shutil.copyfile(Path(args.rag_bindings).expanduser(), binding)
        rag_bindings, rag_hash = str(binding), digest(binding)
    plan = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "code_root": str(code), "revision": git(code, "rev-parse", "HEAD"),
        "dirty": bool(git(code, "status", "--porcelain")),
        "model": args.model, "thinking": args.thinking, "tier": args.tier, "user": args.user,
        "case": args.case, "question": question, "information_cutoff": args.as_of,
        "today": args.today, "latest_data_date": args.latest_data_date or args.as_of,
        "os_skill": args.os_skill, "app_skills": list(args.app_skills),
        "skill_hashes": {name: digest(code / "skills" / name / "SKILL.md") for name in (args.os_skill, *args.app_skills)},
        "second_look": bool(args.second_look), "subagents": bool(args.subagents),
        "mode": "delivery" if packet is not None else "research", "delivery_style": args.delivery_style,
        "delivery_skill": args.delivery_skill,
        "numeric_checks": bool(args.numeric_checks),
        "numeric_checks_sha256": digest(root / "numeric-checks.json") if args.numeric_checks else None,
        "analysis_only": bool(args.analysis_only),
        "checked_facts_sha256": digest(root / "checked-facts.md") if args.analysis_only else None,
        "source_run": str(Path(args.source_run).resolve()) if packet is not None else None,
        "source_revision": source_plan["revision"] if source_plan is not None else None,
        "source_hashes": source_hashes,
        "packet_sha256": digest(root / "evidence-packet.json") if packet is not None else None,
        "database_source": str(source_db) if source_db is not None else None,
        "database_sha256": db_sha, "clone": cloned,
        "turn_seconds": args.turn_seconds, "physical_calls": args.call_cap, "tool_calls": args.tool_cap,
        "first_attempts": 1, "resampling": False,
        "bridge_port": args.bridge_port, "pi_bin": args.pi_bin,
        "launcher": str(Path(args.launcher).expanduser()), "rag_bindings": rag_bindings,
        "rag_bindings_sha256": rag_hash,
        "kit_hashes": {p.name: digest(p) for p in kit.iterdir()},
        "runner_sha256": digest(Path(__file__).resolve()),
    }
    env = environment(plan, root)
    plan["endpoint_sha256"] = hashlib.sha256(env["LLM_BASE_URL"].encode()).hexdigest()
    save(root / "plan.json", plan)
    print(json.dumps({"status": "prepared", "revision": plan["revision"], "dirty": plan["dirty"],
                      "question_sha256": hashlib.sha256(question.encode()).hexdigest()}), flush=True)


def verify_plan(plan: dict, root: Path) -> None:
    code = Path(plan["code_root"])
    require_clean_code(code)
    if git(code, "rev-parse", "HEAD") != plan["revision"]:
        raise RuntimeError("code revision changed since prepare")
    expected = {Path(__file__).resolve(): plan["runner_sha256"]}
    if plan.get("mode", "research") == "delivery":
        expected[root / "evidence-packet.json"] = plan["packet_sha256"]
        expected.update({Path(plan["source_run"]) / name: sha for name, sha in plan["source_hashes"].items()})
        if (plan["subagents"] or plan["second_look"] or plan["tool_calls"] != 0 or plan["rag_bindings"] != "off"
                or plan.get("delivery_skill") not in plan["app_skills"]):
            raise RuntimeError("delivery mode cannot enable new research")
        try:
            packet, original_plan, hashes = delivered_packet(Path(plan["source_run"]))
        except (ValueError, OSError) as error:
            raise RuntimeError("frozen evidence origin changed") from error
        if (packet != json.loads((root / "evidence-packet.json").read_text()) or hashes != plan["source_hashes"]
                or any(plan[key] != original_plan[key] for key in ("question", "information_cutoff", "model"))
                or plan.get("delivery_style", "direct") not in ("direct", "aligned")):
            raise RuntimeError("delivery question, cutoff, model or packet differs from its origin")
        if plan.get("numeric_checks"):
            expected[root / "numeric-checks.json"] = plan["numeric_checks_sha256"]
            if json.loads((root / "numeric-checks.json").read_text()) != numeric_check_receipt(packet, code):
                raise RuntimeError("numeric checks do not reproduce from the frozen typed input")
        if plan.get("analysis_only"):
            if not plan.get("numeric_checks") or plan["delivery_style"] != "direct":
                raise RuntimeError("analysis-only mode requires checked facts and direct authoring")
            expected[root / "checked-facts.md"] = plan["checked_facts_sha256"]
            receipt = json.loads((root / "numeric-checks.json").read_text())
            if (root / "checked-facts.md").read_text() != numeric_check_document(receipt, code):
                raise RuntimeError("fixed numeric document no longer matches its checked fields")
    else:
        expected[root / "market_feature_store.duckdb"] = plan["database_sha256"]
    expected.update({root / "kit" / name: sha for name, sha in plan["kit_hashes"].items()})
    expected.update({code / "skills" / name / "SKILL.md": sha for name, sha in plan["skill_hashes"].items()})
    if plan["rag_bindings"] != "off":
        expected[Path(plan["rag_bindings"])] = plan["rag_bindings_sha256"]
    for path, sha in expected.items():
        if digest(path) != sha:
            raise RuntimeError(f"frozen input changed: {path}")


def pi_command(plan: dict, root: Path, prompt: str) -> list[str]:
    code = Path(plan["code_root"])
    tools = "read" if plan.get("mode") == "delivery" else "read,finance_call" + (",spawn_sub_agent" if plan["subagents"] else "")
    command = [plan["pi_bin"], "--print", "--mode", "json", "--offline", "--no-approve",
               "--no-extensions", "-e", str(root / "kit" / "finance-mode.ts"),
               "--no-skills"]
    for name in (plan["os_skill"], *plan["app_skills"]):
        command += ["--skill", str(code / "skills" / name)]
    command += ["--no-context-files", "--no-prompt-templates", "--no-themes",
                "--tools", tools,
                "--provider", "finance-eval", "--model", plan["model"], "--thinking", plan["thinking"],
                "--session-dir", str(root / "pi" / "sessions"), "--", prompt]
    return command


def build_prompt(plan: dict, menu: dict, root: Path | None = None) -> str:
    if plan.get("mode") == "delivery":
        if root is None:
            raise ValueError("delivery prompt requires its frozen artifact directory")
        prompts = json.loads((root / "kit" / "delivery-prompts.json").read_text())
        packet = json.loads((root / "evidence-packet.json").read_text())
        task = prompts["analysis_task"] if plan.get("analysis_only") else (
            prompts["audit_task"] if plan["delivery_style"] == "aligned" else prompts["direct_task"])
        text = task + "\n\n原问题：\n" + plan["question"]
        if plan.get("numeric_checks"):
            receipt = json.loads((root / "numeric-checks.json").read_text())
            text += "\n\n已有结构化输入的确定性核算（不认证解释或整篇正文）：\n" + json.dumps(receipt, ensure_ascii=False)
        if plan.get("analysis_only"):
            text += "\n\n已独立生成、无需重写的数字事实段：\n" + (root / "checked-facts.md").read_text()
        return text + "\n\n冻结的公开证据包：\n" + json.dumps(packet, ensure_ascii=False)
    return ("请用中文直接回答下面的A股研究问题。finance-mode 是常驻基础协议；命中的专项 skill 先用 read 读取再按其骨架执行。"
            "只能用 finance_call 获取可核验资料，遵守工具参数 schema 与数据截止，明确关键数据、来源和证据缺口；"
            "不把用户先验当市场事实。\n\n"
            + plan["question"] + "\n\n工具清单和截止日：\n"
            + json.dumps(menu, ensure_ascii=False))


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    plan = json.loads((root / "plan.json").read_text())
    verify_plan(plan, root)
    code = Path(plan["code_root"])
    env = environment(plan, root)
    if hashlib.sha256(env["LLM_BASE_URL"].encode()).hexdigest() != plan["endpoint_sha256"]:
        raise RuntimeError("model endpoint changed since prepare")
    result: dict = {"quality": "UNREVIEWED", "resampling": False}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "pi_command": pi_command(plan, root, "<prompt>"),
                          "bridge": [sys.executable, str(root / "kit" / "bridge.py")]}, ensure_ascii=False, indent=2))
        return 0
    assert not (root / "STARTED.json").exists(), "already started; first attempts are not resampled"
    save(root / "STARTED.json", {"at": time.time(), "pid": os.getpid(), "attempt": 1})
    try:
        assert port_free(plan["bridge_port"]), f"port occupied: {plan['bridge_port']}"
        save(root / "pi" / "agent" / "settings.json", {
            "retry": {"enabled": False}, "compaction": {"enabled": False},
            "cacheWarming": "off", "enableInstallTelemetry": False,
        })
        bridge = spawn([sys.executable, str(root / "kit" / "bridge.py")], root / "bridge.log", env, cwd=code)
        deadline = time.monotonic() + 90
        while True:
            assert bridge.poll() is None, "Pi bridge startup failed (see bridge.log)"
            if not port_free(plan["bridge_port"]) and (root / "pi-provider.json").exists():
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Pi bridge startup deadline")
            time.sleep(0.2)
        menu = call(plan["bridge_port"], "/configure", {
            "case": plan["case"], "question": plan["question"], "expected_as_of": plan["information_cutoff"],
            "today": plan["today"], "latest_data_date": plan["latest_data_date"], "research_tier": plan["tier"],
            "user": plan["user"], "users_root": str(root / "pi" / "users"),
            "absolute_deadline_epoch": time.time() + plan["turn_seconds"],
            "call_cap": plan["physical_calls"], "tool_cap": plan["tool_calls"],
            "mode": plan.get("mode", "research"),
        }, timeout=120)
        save(root / "pi" / "menu.json", menu)
        prompt = build_prompt(plan, menu, root)
        (root / "pi" / "prompt.txt").write_text(prompt)
        prompt_argument = "@" + str(root / "pi" / "prompt.txt") if plan.get("mode") == "delivery" else prompt
        command = pi_command(plan, root, prompt_argument)
        (root / "pi" / "command.json").write_text(json.dumps(command[:-1] + ["<prompt.txt>"], ensure_ascii=False, indent=2))
        print("Issuing the sole native Pi first turn.", flush=True)
        with (root / "pi" / "events.jsonl").open("xb") as out, (root / "pi" / "stderr.log").open("xb") as err:
            native = subprocess.Popen(command, cwd=root / "kit", env=env, stdin=subprocess.DEVNULL,
                                      stdout=out, stderr=err, start_new_session=True)
        PROCESSES.append(native)
        try:
            pi_exit = native.wait(timeout=plan["turn_seconds"] + 30)
        except subprocess.TimeoutExpired:
            stop(native)
            pi_exit = 124
        events = read_jsonl(root / "pi" / "events.jsonl")
        assistants = [e["message"] for e in events
                      if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant"]
        drafts = [{"stop_reason": message.get("stopReason"),
                   "text": "\n".join(c["text"] for c in message.get("content", []) if c.get("type") == "text")}
                  for message in assistants if message.get("stopReason") == "stop"]
        save(root / "pi" / "completed-drafts.json", drafts)
        final = assistants[-1] if assistants else {}
        text = "\n".join(c["text"] for c in final.get("content", []) if c.get("type") == "text")
        (root / "pi" / "answer.md").write_text(text)
        if plan.get("analysis_only"):
            (root / "pi" / "analysis.md").write_text(text)
            result["delivery_scope"] = "fixed_numeric_document_and_unreviewed_model_analysis"
            result["checked_facts_sha256"] = digest(root / "checked-facts.md")
        tool_calls = read_jsonl(root / "pi-tools.jsonl")
        responses = read_jsonl(root / "pi-model-responses.jsonl")
        requests = read_jsonl(root / "pi-model-requests.jsonl")
        admission = (bool(responses) and len(responses) == len(requests)
                     == len({r["index"] for r in requests})
                     and {r["index"] for r in responses} == {r["index"] for r in requests}
                     and all(r["response_models"] == [plan["model"]] for r in responses))
        skill_reads = [e for e in events if e.get("type") == "tool_execution_end"
                       and e.get("toolName") == "read" and e.get("isError") is False]
        sub_agents = [e for e in events if e.get("type") == "tool_execution_start" and e.get("toolName") == "spawn_sub_agent"]
        transport = call(plan["bridge_port"], "/health")
        if transport["case"] != plan["case"]:
            raise RuntimeError("bridge case changed during execution")
        tool_events = [e for e in events if e.get("toolName") == "finance_call"]
        result["arm"] = {
            "exit": pi_exit, "stop_reason": final.get("stopReason"), "model_admission": admission,
            "physical_requests": len(requests), "responses": len(responses),
            "tool_calls": transport["tool_calls"], "tool_observations": len(tool_calls),
            "parent_tool_attempts": sum(e.get("type") == "tool_execution_start" for e in tool_events),
            "parent_tool_errors": sum(e.get("type") == "tool_execution_end" and e.get("isError") is True for e in tool_events),
            "tools_used": sorted({t["tool"] for t in tool_calls}),
            "skill_reads": len(skill_reads), "sub_agent_calls": len(sub_agents),
            "answer_chars": len(text), "completed_drafts": len(drafts),
        }
        if plan.get("mode") == "delivery":
            result["arm"]["data_tools_disabled"] = transport.get("data_tools_enabled") is False
            result["arm"]["delivery_method_in_first_request"] = delivery_method_received(plan, requests)
            if plan.get("numeric_checks"):
                receipt = json.loads((root / "numeric-checks.json").read_text())
                expected_receipt = json.dumps(receipt, ensure_ascii=False)
                first_user = "\n".join(message["content"] for message in requests[0]["payload"].get("messages", [])
                                       if message.get("role") == "user" and isinstance(message.get("content"), str)) if requests else ""
                result["arm"]["numeric_checks_in_first_request"] = expected_receipt in first_user
                result["arm"]["numeric_checked_observations"] = len(receipt["checks"])
                if not result["arm"]["numeric_checks_in_first_request"]:
                    result["failure"] = {"type": "NumericReceiptNotDelivered", "message": "calculation receipt missing in first request"}
            expected_drafts = 2 if plan["delivery_style"] == "aligned" else 1
            if (not result["arm"]["data_tools_disabled"] or transport["tool_calls"] or tool_calls
                    or not result["arm"]["delivery_method_in_first_request"] or len(drafts) != expected_drafts):
                result["failure"] = {"type": "DeliveryContractFailure", "message": "new retrieval or unexpected delivery stages"}
        if not arm_completed(result["arm"]):
            result["failure"] = {"type": "IncompleteRun", "message": "Pi did not deliver a complete model-admitted answer"}
        stop(bridge)
    except BaseException as error:  # noqa: BLE001 — every failure is a recorded outcome, never a resample
        result["failure"] = {"type": type(error).__name__, "message": str(error)[:600]}
        print(json.dumps(result["failure"]), flush=True)
    finally:
        for process in reversed(PROCESSES):
            stop(process)
        result["processes_stopped"] = all(p.poll() is not None for p in PROCESSES)
        try:
            verify_plan(plan, root)
            result["inputs_unchanged"] = True
        except BaseException as error:  # noqa: BLE001
            result["inputs_unchanged"] = False
            result["identity_error"] = type(error).__name__
        if not result["inputs_unchanged"] or not result["processes_stopped"]:
            result.setdefault("failure", {"type": "IntegrityFailure", "message": "input verification or cleanup failed"})
        result["status"] = "failed" if result.get("failure") else "completed"
        save(root / "RESULT.json", result)
        files = {str(p.relative_to(root)): {"sha256": digest(p), "bytes": p.stat().st_size}
                 for p in root.rglob("*") if p.is_file() and p.name != "market_feature_store.duckdb"}
        save(root / "capture-manifest.json", files)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 1 if result.get("failure") else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare", help="freeze inputs into plan.json (no model call)")
    prep.add_argument("--root", required=True)
    source = prep.add_mutually_exclusive_group(required=True)
    source.add_argument("--db", help="source market_feature_store.duckdb (cloned read-only)")
    source.add_argument("--source-run", help="completed run whose exact public deliveries are replayed without retrieval")
    prep.add_argument("--delivery-style", choices=("direct", "aligned"), default="direct")
    prep.add_argument("--delivery-skill", help="application skill injected in full before the first delivery request")
    prep.add_argument("--numeric-checks", action="store_true", help="append deterministic checks of supported typed frozen inputs")
    prep.add_argument("--analysis-only", action="store_true", help="render numeric facts separately; the model writes only interpretation and hypotheses")
    prep.add_argument("--question-file")
    prep.add_argument("--as-of", help="information cutoff YYYY-MM-DD")
    prep.add_argument("--today", default=datetime.now().date().isoformat())
    prep.add_argument("--latest-data-date", default=None)
    prep.add_argument("--code-root", default=str(HERE.parents[1]))
    prep.add_argument("--model", default="glm-5.3-flash")
    prep.add_argument("--thinking", default="low")
    prep.add_argument("--tier", default="max")
    prep.add_argument("--user", default="probe-pi-native-knevo")
    prep.add_argument("--case", default="pi-native")
    prep.add_argument("--os-skill", default=DEFAULT_SKILLS[0])
    prep.add_argument("--skills", default=",".join(DEFAULT_SKILLS[1:]),
                      help="comma-separated app skills to mount (finance-mode is always the OS layer)")
    prep.add_argument("--second-look", action="store_true", help="enable one self-check continuation")
    prep.add_argument("--subagents", action="store_true", help="enable isolated research children (separate experimental variable)")
    prep.add_argument("--turn-seconds", type=int, default=600)
    prep.add_argument("--call-cap", type=int, default=120)
    prep.add_argument("--tool-cap", type=int, default=60)
    prep.add_argument("--bridge-port", type=int, default=18886)
    prep.add_argument("--pi-bin", default=shutil.which("pi") or "pi")
    prep.add_argument("--launcher", default=str(DEFAULT_LAUNCHER))
    prep.add_argument("--rag-bindings", help="managed RAG generation binding JSON; research requires it, delivery uses frozen evidence only")

    runp = sub.add_parser("run", help="execute the frozen first attempt")
    runp.add_argument("--root", required=True)
    runp.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "prepare":
        args.app_skills = tuple(s.strip() for s in args.skills.split(",") if s.strip())
        prepare(args)
        return 0
    return run(args)


if __name__ == "__main__":
    os.umask(0o077)
    sys.exit(main())
