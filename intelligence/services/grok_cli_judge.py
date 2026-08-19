"""Grok CLI as an independent semantic judge (L4).

The composer talks HTTP (GLM/GPT 中转).  Grok Build TUI is a different
model family and a different client, so it breaks the correlated-judge
failure: the same model no longer writes and marks its own homework.

This module only runs when ``LLM_JUDGE_BACKEND=grok-cli`` (aliases
``grok`` / ``cli``).  Presence of ``grok`` on PATH does not auto-enable —
flipping production without that env would silently change repair quality.

Isolation (judge must not peek at the repo or browse the web):

- empty temp ``--cwd`` (not the finance checkout; AGENTS.md would leak)
- ``--system-prompt-override`` (skip default system prompt)
- no shell / web / subagents; ``--max-turns 1``
- ``--json-schema`` so stdout ``text`` is the judge object
- vendor skill scans off via env

Auth stays the user's existing ``grok login`` / ``XAI_API_KEY``.  We never
copy ``auth.json`` and never log it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any

CLI_GROK_URL = "cli://grok"
BACKEND_ALIASES = frozenset({"grok", "grok-cli", "cli"})
DEFAULT_MODEL = "grok-4.6"
DEFAULT_EFFORT = "low"
DEFAULT_SANDBOX = "read-only"

JUDGE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "passed": {"type": "boolean"},
        "rejected_sentence_indexes": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["passed", "rejected_sentence_indexes", "issues"],
}

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def judge_backend_from_env(env: Mapping[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    raw = str(source.get("LLM_JUDGE_BACKEND") or source.get("LLM_JUDGE") or "")
    return raw.strip().lower()


def grok_cli_backend_enabled(env: Mapping[str, str] | None = None) -> bool:
    return judge_backend_from_env(env) in BACKEND_ALIASES


def is_cli_judge_provider(provider: object) -> bool:
    transport = str(getattr(provider, "transport", "") or "")
    base = str(getattr(provider, "base_url", "") or "")
    return transport == "cli" or base.startswith("cli://")


def resolve_grok_binary(env: Mapping[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    explicit = str(source.get("LLM_JUDGE_GROK_BIN") or source.get("GROK_BIN") or "").strip()
    if explicit:
        return explicit
    found = shutil.which("grok")
    return found or None


def grok_cli_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Keep auth/PATH; turn off Claude/Cursor skill+memory discovery."""

    env = dict(os.environ if base is None else base)
    env["GROK_CLAUDE_SKILLS_ENABLED"] = "false"
    env["GROK_CURSOR_SKILLS_ENABLED"] = "false"
    env["GROK_MEMORY"] = "0"
    return env


def _split_messages(messages: Sequence[Mapping[str, object]]) -> tuple[str, str]:
    system_parts: list[str] = []
    user_parts: list[str] = []
    for item in messages:
        role = str(item.get("role") or "")
        content = item.get("content")
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        if role == "system":
            system_parts.append(text)
        else:
            user_parts.append(text)
    system = "\n\n".join(part for part in system_parts if part.strip())
    user = "\n\n".join(part for part in user_parts if part.strip())
    return system, user


def build_grok_judge_argv(
    *,
    binary: str,
    cwd: str,
    prompt_file: str,
    model: str,
    system_prompt: str,
    effort: str = DEFAULT_EFFORT,
    sandbox: str = DEFAULT_SANDBOX,
) -> list[str]:
    argv = [
        binary,
        "--cwd",
        cwd,
        "--system-prompt-override",
        system_prompt,
        "--prompt-file",
        prompt_file,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(JUDGE_JSON_SCHEMA, ensure_ascii=False, separators=(",", ":")),
        "--disable-web-search",
        "--no-subagents",
        "--no-plan",
        "--verbatim",
        "--max-turns",
        "1",
        "--disallowed-tools",
        "Agent,web_search,web_fetch,run_terminal_cmd,search_replace",
        "--reasoning-effort",
        effort,
        "-m",
        model,
    ]
    if sandbox and sandbox != "off":
        argv.extend(["--sandbox", sandbox])
    return argv


def _extract_text(stdout: str) -> str:
    raw = stdout.strip()
    if not raw:
        raise RuntimeError("GrokCliEmpty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GrokCliInvalidJson") from exc
    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        text = payload["text"].strip()
    elif isinstance(payload, dict) and "passed" in payload:
        return json.dumps(payload, ensure_ascii=False)
    else:
        text = raw
    text = _FENCE.sub("", text).strip()
    if not text:
        raise RuntimeError("GrokCliEmpty")
    return text


def complete_grok_cli(
    provider: object,
    messages: Sequence[Mapping[str, object]],
    timeout: float,
    *,
    runner: Any = subprocess.run,
) -> str:
    """Return the judge JSON string. Raises on any CLI failure."""

    binary = resolve_grok_binary()
    if not binary:
        raise FileNotFoundError("grok CLI not found")
    system, user = _split_messages(messages)
    if not user:
        raise RuntimeError("GrokCliEmptyPrompt")
    model = str(getattr(provider, "model", "") or DEFAULT_MODEL)
    effort = str(os.environ.get("LLM_JUDGE_GROK_EFFORT") or DEFAULT_EFFORT)
    sandbox = str(os.environ.get("LLM_JUDGE_GROK_SANDBOX") or DEFAULT_SANDBOX)
    limit = max(1.0, float(timeout))
    with tempfile.TemporaryDirectory(prefix="grok-judge-") as cwd:
        prompt_path = os.path.join(cwd, "request.json")
        with open(prompt_path, "w", encoding="utf-8") as handle:
            handle.write(user)
        argv = build_grok_judge_argv(
            binary=binary,
            cwd=cwd,
            prompt_file=prompt_path,
            model=model,
            system_prompt=system or "You are a JSON judge. Output only the schema.",
            effort=effort,
            sandbox=sandbox,
        )
        try:
            completed = runner(
                argv,
                cwd=cwd,
                env=grok_cli_env(),
                capture_output=True,
                text=True,
                timeout=limit,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("grok CLI timed out") from exc
        if int(getattr(completed, "returncode", 1) or 0) != 0:
            stderr = str(getattr(completed, "stderr", "") or "")[:400]
            raise RuntimeError(f"GrokCliExit {completed.returncode}: {stderr}")
        return _extract_text(str(getattr(completed, "stdout", "") or ""))
