from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "launch_workbench_sidecar.sh"
ZSH = shutil.which("zsh")


@pytest.mark.skipif(ZSH is None, reason="sidecar launcher requires zsh")
@pytest.mark.parametrize("launcher_overrides_episode_store", [False, True])
def test_sidecar_isolates_episode_store_after_loading_production_config(
    tmp_path: Path, launcher_overrides_episode_store: bool,
) -> None:
    production = tmp_path / "production"
    production.mkdir()
    repo = tmp_path / "candidate"
    (repo / "intelligence").mkdir(parents=True)
    users = tmp_path / "isolated users"
    observed = tmp_path / "observed.json"
    launcher = tmp_path / "launcher"
    lines = [f"export FINANCE_WS={shlex.quote(str(production))}"]
    if launcher_overrides_episode_store:
        lines.append(
            "export FORESIGHT_EPISODE_STORE="
            + shlex.quote(str(production / "state" / "episodes"))
        )
    launcher.write_text("\n".join(lines) + "\n")
    fake_python = tmp_path / "python"
    fake_python.write_text(
        f"#!{sys.executable}\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "keys = ('FINANCE_WS', 'WORKBENCH_REPO_ROOT', 'PYTHONPATH', "
        "'FORESIGHT_USERS_DIR', 'FORESIGHT_USER', 'FORESIGHT_EPISODE_STORE')\n"
        "values = {key: os.environ.get(key) for key in keys}\n"
        "Path(os.environ['SIDECAR_TEST_OUTPUT']).write_text(json.dumps(values))\n"
    )
    fake_python.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    lsof = fake_bin / "lsof"
    lsof.write_text("#!/bin/sh\nexit 1\n")
    lsof.chmod(0o755)
    env = {
        **os.environ,
        "WORKBENCH_LAUNCHER": str(launcher),
        "WORKBENCH_PYTHON": str(fake_python),
        "SIDECAR_TEST_OUTPUT": str(observed),
        "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
    }
    env.pop("FORESIGHT_EPISODE_STORE", None)
    result = subprocess.run(
        [str(ZSH), str(SCRIPT), "19051", str(repo), str(users), "probe-user"],
        env=env, capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    actual = json.loads(observed.read_text())
    assert actual == {
        "FINANCE_WS": str(production),
        "WORKBENCH_REPO_ROOT": str(repo),
        "PYTHONPATH": str(repo),
        "FORESIGHT_USERS_DIR": str(users),
        "FORESIGHT_USER": "probe-user",
        "FORESIGHT_EPISODE_STORE": str(users / ".episodes"),
    }
    assert users.is_dir()
    assert not list(production.iterdir())
