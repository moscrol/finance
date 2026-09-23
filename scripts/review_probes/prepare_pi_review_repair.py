"""Build fresh PR868 review inputs; never edit a sealed batch or start a model.

The archived runner is deliberately retained as a hash-checked migration source.
CLI wiring, causal gateway protocol and controller-owned identity are replaced. Historical
receipts, model outputs, and authorization are not inherited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ARCHIVE = REPO / "docs/verification/2026-09-23-adaptive-qc-glm-roundtrip"
STAGE_TOOLS = {
    "gateway": ["read", "write"],
    "explore": ["read", "write", "deliver_stage"],
    "execute": ["read", "write", "bash", "deliver_stage"],
    "report": ["deliver_stage"],
}
AXIS_FILES = {
    "config.json", "review.mjs", "gateway.mjs", "run_stage.py", "run_control.py",
    "file_tool.py", "tools.sb", "sandbox_preflight.mjs", "provider-template.json",
    "pi-config/settings.json", "prompt-explore.md", "prompt-execute.md", "prompt-report.md",
}
ROOT_FILES = {"glm_credential.py", "glm_review_shim.py", "probe_adapter.py", "bridge_stage.py"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(body: str, old: str, new: str) -> str:
    if body.count(old) != 1:
        raise ValueError(f"migration anchor is not unique: {old!r}")
    return body.replace(old, new, 1)


def prepare(destination: Path, archive: Path = ARCHIVE) -> dict:
    destination = destination.resolve()
    manifest = json.loads((archive / "archive-manifest.json").read_text())
    original = Path(manifest["protocol.json"]["source"]).parent
    if destination.is_relative_to(archive.resolve()) or destination.is_relative_to(original):
        raise ValueError("cannot write into sealed evidence")
    frozen = json.loads((archive / "frozen-inputs.json").read_text())
    inputs = {}
    for name, sha in frozen.items():
        archived = archive / name
        if not archived.is_file():
            archived = archive / (name + ".txt")
        data = archived.read_bytes()
        if digest(data) != sha:
            raise ValueError(f"sealed input changed: {name}")
        parts = Path(name).parts
        if name in ROOT_FILES or (
            parts[0] in {"spec", "quality"}
            and (str(Path(*parts[1:])) in AXIS_FILES or parts[1] == "inputs")
        ):
            inputs[name] = data.decode().replace(str(original), str(destination))

    helper = Path(__file__).with_name("pi_review_protocol.mjs").read_text()
    for axis in ("spec", "quality"):
        config_name = f"{axis}/config.json"
        config = json.loads(inputs[config_name])
        config["stage_tools"] = STAGE_TOOLS
        inputs[config_name] = json.dumps(config, indent=2) + "\n"
        inputs[f"{axis}/pi_review_protocol.mjs"] = helper
        inputs[f"{axis}/gateway.mjs"] = "export { default } from './review.mjs';\n"
        name = f"{axis}/review.mjs"
        inputs[name] = replace_once(inputs[name], "import fs from 'node:fs';",
                                   "import { installStageGuard, installGateway, bindStageResult } from './pi_review_protocol.mjs';\nimport fs from 'node:fs';")
        inputs[name] = replace_once(inputs[name], "  const stage = process.env.REVIEW_PHASE;",
                                   "  const stage = process.env.REVIEW_PHASE;\n"
                                   "  installStageGuard(pi, {out, stage, tools: CONFIG.stage_tools, terminate});\n"
                                   "  if (stage === 'gateway') installGateway(pi, {out, tree, terminate});")
        inputs[name] = replace_once(inputs[name],
                                   "const allowed = stage === 'report' ? ['deliver_stage'] : stage === 'explore' ? ['read', 'write', 'deliver_stage'] : ['read', 'write', 'bash', 'deliver_stage'];",
                                   "const allowed = CONFIG.stage_tools[stage];")
        inputs[name] = replace_once(
            inputs[name], "      const data = JSON.parse(params.result);",
            "      let data;\n"
            "      try { data = bindStageResult(params.result, {...CONFIG, stage}); }\n"
            "      catch (error) { return deny('delivery_content_invalid: ' + error.message); }",
        )
        inputs[name] = replace_once(
            inputs[name],
            "Complete JSON object required by the stage prompt, serialized as a string. Never fabricate evidence.",
            "Stage content JSON as a string: complete=true and the required evidence fields. "
            "Do NOT include stage, axis, revision or baseline; the controller owns these fields. Never fabricate evidence.",
        )
        for stage in ("explore", "execute", "report"):
            prompt = f"{axis}/prompt-{stage}.md"
            inputs[prompt] = replace_once(
                inputs[prompt],
                f"It must contain stage, axis='{axis}', revision, baseline, complete=true;",
                "Submit content only: complete=true and required evidence fields. "
                "Do NOT supply stage, axis, revision or baseline; those fields are controller-owned. "
                "Identity injection is rejected, never normalized;",
            )
            if stage == "execute":
                inputs[prompt] = replace_once(
                    inputs[prompt], "Stage EXECUTE: first read ",
                    "Stage EXECUTE: your first two tool calls MUST be bash: run the intentional "
                    "failing control below exactly once, then the prescribed pure author tests "
                    "exactly once. Preserve both outcomes even if later probes cannot run. "
                    "Do not spend these calls on reading or debugging. After those two calls, read ",
                )
            if stage == "explore":
                inputs[prompt] += (
                    "\nBefore writing a probe, verify every called API signature in candidate source. "
                    "Each probe must separately report whether its target trigger was reached; "
                    "an exception alone does not prove cancellation, body timeout or late rejection. "
                    "Exit nonzero if any non-control assertion fails; report subcase counts separately "
                    "from script invocations. Keep probes small enough to run after mandatory controls "
                    "within the existing execute budget.\n"
                )
            if stage == "report":
                inputs[prompt] = replace_once(
                    inputs[prompt],
                    "Return required fields stage='report', axis, revision, baseline, complete=true, verdict",
                    "Return required content fields complete=true, verdict",
                )
        name = f"{axis}/run_stage.py"
        inputs[name] = replace_once(inputs[name], "'--tools', 'read,bash,write'",
                                   "'--tools', ','.join(CONFIG['stage_tools'][STAGE])")
        inputs[name] = replace_once(inputs[name], "'config.json', 'review.mjs', 'tools.sb'",
                                   "'config.json', 'review.mjs', 'pi_review_protocol.mjs', 'tools.sb'")
        name = f"{axis}/run_control.py"
        inputs[name] = replace_once(inputs[name], "'--tools', 'read,bash,write'", "'--tools', 'read,write'")
        inputs[name] = replace_once(inputs[name], "    passed = (proc.returncode", "    state_path = out / 'gateway-state.json'\n"
                                   "    state = json.loads(state_path.read_text()) if state_path.is_file() else {}\n"
                                   "    passed = (state.get('phase') == 'complete' and proc.returncode")
        inputs[name] = replace_once(inputs[name], "'exit_code': proc.returncode, 'timed_out': timed_out,",
                                   "'exit_code': proc.returncode, 'timed_out': timed_out, 'protocol_state': state,")
        name = f"{axis}/sandbox_preflight.mjs"
        inputs[name] = replace_once(inputs[name], "const hooks = {}; const tools = {};",
                                   "process.env.REVIEW_PHASE = 'execute';\nconst hooks = {}; const tools = {};")

    # Nothing from the previous run's work/, receipts, transcripts, or approvals.
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, body in inputs.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as stream:
            stream.write(body)
    for axis in ("spec", "quality"):
        for name in ("tmp", "users", "probes"):
            (destination / axis / "work" / name).mkdir(parents=True)
    receipt = {
        "status": "PREPARED_NOT_AUTHORIZED", "source_archive": str(archive),
        "sealed_inputs_checked": len(frozen), "real_model_requests": 0,
        "prior_stage_receipts_inherited": False, "prior_model_outputs_inherited": False,
        "historical_author_inputs_preserved": True,
        "delivery_identity_owner": "controller; reviewer identity fields are forbidden",
        "stage_tools": STAGE_TOOLS,
        "inputs_sha256": {name: digest(body.encode()) for name, body in inputs.items()},
    }
    (destination / "repair-inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New, nonexistent evidence root")
    args = parser.parse_args()
    result = prepare(args.destination)
    print(json.dumps({k: v for k, v in result.items() if k != "inputs_sha256"}, indent=2))


if __name__ == "__main__":
    main()
