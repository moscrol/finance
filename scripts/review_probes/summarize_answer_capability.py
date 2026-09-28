"""Collect paired Workbench observables without grading by headings or run status.

Usage: python -m scripts.review_probes.summarize_answer_capability EVIDENCE_DIR
Reads the saved evaluation-manifest.json and workbench_probe logs; never sends
requests. Reuses the Knevo inspector to verify question/run identity and hash
artifacts. Missing episodes remain unknown, rather than becoming zero tool use.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re

from intelligence.eval.knevo_regression import RegressionCase, inspect_run


def summarize(directory: Path) -> dict:
    manifest = json.loads((directory / "evaluation-manifest.json").read_text())
    results = []
    for arm in ("baseline", "candidate"):
        for case in manifest["cases"]:
            log = directory / f"{arm}-{case['id']}.txt"
            match = re.search(r"^run_id=(\S+)", log.read_text(), re.M) if log.exists() else None
            if match is None:
                continue
            run_dir = directory / f"{arm}-users" / f"answer-{arm}-0928" / "runs" / match[1]
            if not (run_dir / "report.json").exists():
                continue  # Only inspect settled artifacts.
            selected = RegressionCase(
                case_id=case["id"], question=case["question"], source="evaluation-manifest.json",
                mode="revealed_regression", pass_rules=(), fail_rules=(),
                not_tested="Blind quality assessment and general performance",
            )
            result = inspect_run(run_dir, selected)
            run = json.loads((run_dir / "run.json").read_text())
            if run.get("finished_at"):
                result["seconds"] = (
                    datetime.fromisoformat(run["finished_at"])
                    - datetime.fromisoformat(run["created_at"])
                ).total_seconds()
            episode_path = run_dir / "continuous-episode.json"
            if episode_path.exists():
                episode = json.loads(episode_path.read_text())
                result["usage"] = episode.get("outcome", {}).get("usage")
                result["required_outputs"] = episode.get("task_frame", {}).get("required_outputs")
                for event in episode.get("events", []):
                    if event.get("kind") == "prompt_assembled":
                        payload = event["payload"]
                        result["prompt_chars"] = {k: payload.get(f"{k}_chars") for k in ("system", "user")}
                    if event.get("kind") == "model_turn" and "first_input_tokens" not in result:
                        result["first_input_tokens"] = event["payload"].get("input_tokens")
            result.update(arm=arm, run_directory=str(run_dir))
            results.append(result)
    return {"boundary": manifest["boundary"], "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
