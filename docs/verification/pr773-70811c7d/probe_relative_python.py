"""PR 773 review probe: documented relative FINANCE_PYTHON breaks after cd."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).expanduser().resolve()
PIPELINE = ROOT / "scripts/moneyflow/run_l2_pipeline.sh"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pr773-python-") as temp:
        sandbox = Path(temp)
        code = sandbox / "code"
        data = sandbox / "data"
        moneyflow = code / "scripts/moneyflow"
        moneyflow.mkdir(parents=True)
        (code / "market_feature_store").symlink_to(ROOT / "market_feature_store")
        (data / "state").mkdir(parents=True)
        (data / "state/l2-baidu-share.json").write_text("{}")
        interpreter = data / ".venv-workbench/bin/python"
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(sys.executable)
        for file in (moneyflow / "write_to_duckdb.py", moneyflow / "run_l2_from_share.py", code / "scripts/render_moneyflow_html.py"):
            file.write_text("print('SAFE_STUB')\n")
        env = dict(
            os.environ,
            FINANCE_CODE_ROOT=str(code),
            FINANCE_DATA_ROOT=str(data),
            MARKET_FEATURE_STORE_DB=str(data / "nonexistent.duckdb"),
            MONEYFLOW_OUTPUT_DIR=str(data / "outputs"),
            L2_LOCK_HELD="1",
            HOME=str(sandbox),
        )
        results = []
        for python in (".venv-workbench/bin/python", sys.executable):
            proc = subprocess.run(
                ["/bin/zsh", str(PIPELINE), "2026-09-16"],
                cwd=data,
                env={**env, "FINANCE_PYTHON": python},
                capture_output=True,
                text=True,
                timeout=30,
            )
            results.append({"python": python, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        print(json.dumps(results, ensure_ascii=False, indent=2))
        assert results[0]["returncode"] == 127
        assert results[1]["returncode"] == 0
        print("REPRODUCED: relative interpreter fails after cd; identical absolute interpreter succeeds")


if __name__ == "__main__":
    main()
