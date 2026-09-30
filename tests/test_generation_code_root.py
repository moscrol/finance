"""#50：真实 Python/CLI/子进程 + 隔离数据。只替换 SQL 计算/质量结果，不替换路径接线。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
import pytest


requires_zsh = pytest.mark.skipif(
    not os.path.exists("/bin/zsh"),
    reason="需要 /bin/zsh（macOS 默认 shell）；Linux 上跳过，Mac 上照常跑",
)

ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-09-11"


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def rig(tmp_path):
    code, data, elsewhere = (tmp_path / n for n in ("code snapshot", "data", "elsewhere"))
    for p in (code, data, elsewhere):
        p.mkdir()
    # 复制可执行代码而不是软链：__file__.resolve() 必须真指向隔离代码根。
    for package in ("intelligence", "market_feature_store", "scripts", "evolution"):
        for src in (ROOT / package).rglob("*.py"):
            if any(part in {"tests", "users", "__pycache__", "node_modules", "webapp"}
                   for part in src.relative_to(ROOT).parts):
                continue
            target = code / src.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    for name in ("intelligence/contracts/stream_events.json",
                 "market_feature_store/consumption_registry.yaml", "market_feature_store/schema.sql",
                 "scripts/lib/ops_python.sh", "skills/strategy1-matrix/scripts/update_matrix.py",
                 "skills/daily-full-review/scripts/export_increment.py",
                 "skills/daily-full-review/scripts/nightly_full_review.sh"):
        target = code / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    (data / "db").mkdir()
    with duckdb.connect(str(data / "db/market_feature_store.duckdb")) as con:
        con.execute("CREATE TABLE fact_probe (trade_date DATE, value INTEGER)")
        con.execute("INSERT INTO fact_probe VALUES (?, 1)", [DAY])
    # poison tree：错误加载不能仅仅碰巧也成功。
    for package in ("intelligence", "market_feature_store", "scripts"):
        (data / package).mkdir(exist_ok=True)
        (data / package / "__init__.py").write_text("raise RuntimeError('DATA_TREE_CODE_EXECUTED')\n")
    (data / "scripts/check_daily_review_data.py").write_text("raise RuntimeError('STALE_GATE')\n")
    (data / "scripts/render_daily_review_briefing.py").write_text("raise RuntimeError('STALE_RENDERER')\n")
    # 质量不在本测试判据里：不读生产库，不用放宽生产门来凑根测试。
    (code / "scripts/check_daily_review_data.py").write_text("""
import os
raise SystemExit(int(os.environ.get('TEST_GATE_RC', '0')))
""")
    cli = code / "market_feature_store/cli.py"
    injection = '''
from market_feature_store import quality
from market_feature_store.reports import daily_review as report

def fixture_check(trade_date=None, **kwargs):
    return dict(trade_date=trade_date, plan=kwargs.get("plan"), ok=True, brief="fixture",
                gaps=[], row_anomalies=[], range_violations=[])
quality.check_daily = fixture_check

def fixture_collect(con, date, *, out_path, chart_path):
    from intelligence.services.episode_store import JsonlEpisodeStore, EpisodeState, resolve_episode_store_root
    import intelligence
    from intelligence import userspace
    import os
    us = userspace.user_space("root-test")
    us.ensure_dir()
    us.corrections_path.write_text('{"fixture": true}\\n')
    store = JsonlEpisodeStore(resolve_episode_store_root())
    store.put_state("fixture-episode", EpisodeState(episode_id="fixture-episode", phase="done"))
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(b"fixture-png")
    return dict(trade_date=date, chart_path=str(chart_path), loaded=intelligence.__file__,
                model=os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL"),
                db_value=con.execute("SELECT value FROM fact_probe").fetchone()[0])
report.collect_daily_review = fixture_collect
report.render_daily_review_markdown = lambda r: "# Report\\n## Fixture\\n" + r["trade_date"]
'''
    text = cli.read_text()
    cli.write_text(text.replace('if __name__ == "__main__":', injection + '\nif __name__ == "__main__":'))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FINANCE_", "FORESIGHT_", "REVIEW_", "MARKET_", "DUCKDB_", "PYTHON"))}
    env.update(FINANCE_CODE_ROOT=str(code), FINANCE_DATA_ROOT=str(data),
               FORESIGHT_USERS_DIR=str(data / "app/users"), FORESIGHT_USER="root-test",
               FORESIGHT_BUILTIN_LLM_MODEL="fixture-model-no-key",
               KNOWLEDGE_WIKI=str(data / "wiki"), HOME=str(data / "home"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(data))
    return code, data, elsewhere, env


def launch(rig, *args, cwd=None):
    code, data, elsewhere, env = rig
    return subprocess.run([sys.executable, "-P", str(code / "scripts/run_daily_generation.py"),
                           "--date", DAY, "--plan", "local", "--skip-sync", "--no-alert", *args],
                          cwd=cwd or elsewhere, env=env, text=True, capture_output=True, timeout=45)


@pytest.mark.parametrize("destination", ["file-link", "directory-link", "home-in-code", "external", "disabled"])
def test_failure_alert_respects_generation_code_boundary(rig, destination):
    code, data, elsewhere, env = rig
    env["TEST_GATE_RC"] = "3"
    bindir = data / "notification-stub"
    bindir.mkdir()
    stub = bindir / "osascript"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    if destination == "home-in-code":
        env["HOME"] = str(code / "home")
    alert = Path(env["HOME"]) / ".finance-runtime/alerts.log"
    if destination in {"file-link", "disabled"}:
        alert.parent.mkdir(parents=True)
        alert.symlink_to(code / "alert.log")
    elif destination == "directory-link":
        target = code / "alert-dir"
        target.mkdir()
        alert.parent.parent.mkdir(parents=True)
        alert.parent.symlink_to(target, target_is_directory=True)
    before = inventory(code)
    command = [sys.executable, "-P", str(code / "scripts/run_daily_generation.py"),
               "--date", DAY, "--plan", "local", "--skip-sync", "--only-step", "daily-review"]
    if destination == "disabled":
        command.append("--no-alert")
    result = subprocess.run(command, cwd=elsewhere, env=env, text=True,
                            capture_output=True, timeout=45)
    assert inventory(code) == before, result.stdout + result.stderr
    if destination in {"external", "disabled"}:
        assert result.returncode == 1
        assert "generation code/data root invalid" not in result.stderr
        assert alert.exists() is (destination == "external")
        if destination == "external":
            assert "FAIL" in alert.read_text()
    else:
        assert result.returncode == 2
        assert "CODE_ROOT" in result.stderr
        assert not alert.exists()


@pytest.mark.parametrize("cwd_name", ["data", "elsewhere"])
def test_real_cli_is_cwd_independent_and_keeps_code_tree_unchanged(rig, cwd_name):
    code, data, elsewhere, _ = rig
    before = inventory(code)
    result = launch(rig, "--dry-run", "--summary-json", "market_feature_store/exports/plan.json",
                    cwd=data if cwd_name == "data" else elsewhere)
    assert result.returncode == 0, result.stderr
    assert f"generation_import={code}/intelligence/__init__.py" in result.stderr
    summary = json.loads((data / "market_feature_store/exports/plan.json").read_text())
    assert summary["inputs"]["plan"] == "local"
    assert all(s["command"].startswith(sys.executable) for s in summary["steps"])
    assert inventory(code) == before


def test_real_child_writes_report_user_state_episode_and_html_to_data(rig):
    code, data, _, _ = rig
    before = inventory(code)
    result = launch(rig, "--only-step", "daily-review", "--summary-json", "report-summary.json")
    assert result.returncode == 0, result.stdout + result.stderr
    exports = data / "market_feature_store/exports"
    report = json.loads((exports / f"{DAY}-daily-review.json").read_text())
    assert Path(report["loaded"]).is_relative_to(code)
    assert report["model"] == "fixture-model-no-key"
    assert report["db_value"] == 1
    assert (data / "app/users/root-test/corrections.jsonl").is_file()
    assert (data / "app/users/root-test/workflow_metrics.jsonl").is_file()
    assert (data / "state/episodes/fixture-episode/state.json").is_file()
    assert list((data / "db/snapshots/increments").glob("*.tar.gz"))
    result = launch(rig, "--only-step", "daily-review-html")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (data / f"复盘/daily/{DAY}/{DAY}-daily-review.html").is_file()
    assert inventory(code) == before


@pytest.mark.parametrize("missing", ["intelligence/cli.py", "intelligence/__init__.py", "market_feature_store/__init__.py"])
def test_incomplete_code_root_never_falls_back_to_poison_data(rig, missing):
    code, data, _, _ = rig
    (code / missing).unlink()
    result = launch(rig, "--dry-run")
    assert result.returncode == 2
    assert "refusing workspace fallback" in result.stderr
    assert "DATA_TREE_CODE_EXECUTED" not in result.stderr
    assert not (data / "market_feature_store/exports").exists()


def test_symlink_code_root_resolves_to_same_snapshot(rig):
    code, _, elsewhere, env = rig
    link = elsewhere / "runtime"
    link.symlink_to(code, target_is_directory=True)
    env["FINANCE_CODE_ROOT"] = str(link)
    result = launch(rig, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert f"generation_import={code}/intelligence/__init__.py" in result.stderr


@pytest.mark.parametrize("variable", ["FORESIGHT_USERS_DIR", "FORESIGHT_EPISODE_STORE",
                                      "MARKET_FEATURE_STORE_DB", "DUCKDB_SNAPSHOT_OUT_ROOT"])
def test_writable_state_inside_code_root_is_rejected(rig, variable):
    code, _, _, env = rig
    env[variable] = str(code / "state")
    before = inventory(code)
    result = launch(rig, "--dry-run")
    assert result.returncode == 2
    assert "writable path is in CODE_ROOT" in result.stderr
    assert inventory(code) == before


def test_child_gate_failure_propagates_and_writes_no_report(rig):
    _, data, _, env = rig
    env["TEST_GATE_RC"] = "3"
    result = launch(rig, "--only-step", "daily-review", "--summary-json", "failed.json")
    assert result.returncode != 0
    summary = json.loads((data / "failed.json").read_text())
    assert summary["steps"][0]["returncode"] == 3
    assert not (data / f"market_feature_store/exports/{DAY}-daily-review.json").exists()


@pytest.mark.parametrize("root_value", ["missing", "unset", "wrong"])
def test_invalid_configured_root_fails_before_daily(rig, root_value):
    _, data, elsewhere, env = rig
    if root_value == "unset":
        env.pop("FINANCE_CODE_ROOT")
    else:
        env["FINANCE_CODE_ROOT"] = str(elsewhere / "absent" if root_value == "missing" else data)
    result = launch(rig, "--dry-run")
    assert result.returncode == 2
    assert "refusing workspace fallback" in result.stderr


def test_package_symlink_outside_code_root_is_rejected(rig):
    code, data, _, _ = rig
    target = code / "intelligence/cli.py"
    target.unlink()
    target.symlink_to(data / "intelligence/__init__.py")
    result = launch(rig, "--dry-run")
    assert result.returncode == 2
    assert "code escapes FINANCE_CODE_ROOT" in result.stderr


def test_relative_overrides_are_data_relative_and_external_users_are_preserved(rig):
    code, data, elsewhere, env = rig
    shared_users = elsewhere / "existing-users"
    (shared_users / "root-test").mkdir(parents=True)
    sentinel = shared_users / "root-test/profile.json"
    sentinel.write_text('{"existing": true}')
    env.update(FORESIGHT_USERS_DIR=str(shared_users), FORESIGHT_EPISODE_STORE="relative-episodes",
               MARKET_FEATURE_STORE_DB="db/market_feature_store.duckdb", DUCKDB_SNAPSHOT_OUT_ROOT="snapshots")
    before = inventory(code)
    result = launch(rig, "--only-step", "daily-review")
    assert result.returncode == 0, result.stdout + result.stderr
    assert sentinel.read_text() == '{"existing": true}'
    assert (shared_users / "root-test/workflow_metrics.jsonl").is_file()
    assert (data / "relative-episodes/fixture-episode/state.json").is_file()
    assert list((data / "snapshots/increments").glob("*.tar.gz"))
    assert inventory(code) == before


def test_summary_inside_code_root_is_rejected(rig):
    code, _, _, _ = rig
    before = inventory(code)
    result = launch(rig, "--dry-run", "--summary-json", str(code / "summary.json"))
    assert result.returncode == 2
    assert "writable path is in CODE_ROOT" in result.stderr
    assert inventory(code) == before


def test_direct_renderers_and_queues_use_data_paths(rig):
    code, data, _, _ = rig
    exports = data / "market_feature_store/exports"
    exports.mkdir(parents=True)
    (exports / f"{DAY}-theme-candidates.json").write_text(json.dumps({"trade_date": DAY, "candidates": []}))
    (data / "复盘/matrices").mkdir(parents=True)
    before = inventory(code)
    for step in ("daily-review", "daily-review-html", "theme-backfill-queue", "theme-backfill-review-queue",
                 "theme-candidates-html", "review-workbench", "cockpit"):
        result = launch(rig, "--only-step", step, "--summary-json", "step.json")
        assert result.returncode == 0, step + result.stdout + result.stderr
        summary = json.loads((data / "step.json").read_text())
        for output in summary["steps"][-1]["outputs"]:
            assert Path(output).is_file(), output
    assert inventory(code) == before


def test_all_plan_executables_and_matrix_constants_belong_to_the_right_root(rig):
    """补足未实际跑 SQL/模型的叶子：仅证明可执行位置与默认读写根，不冒称业务验收。"""
    code, data, elsewhere, env = rig
    env.update(PYTHONPATH=str(code), FINANCE_WS=str(data),
               MARKET_FEATURE_STORE_DB=str(data / "db/market_feature_store.duckdb"))
    probe = '''
import importlib, importlib.util, json
from intelligence.workflows.daily_review import DailyReviewOptions, build_daily_review_plan
plan = build_daily_review_plan(DailyReviewOptions(date="2026-09-11", skip_sync=True))
executables = []
for step in plan:
    target = step.argv[3] if step.argv[2] == "-m" else step.argv[2]
    executables.append(importlib.util.find_spec(target).origin if step.argv[2] == "-m" else target)
constants = {}
for name, attrs in {
    "generate_strategy1_mechanical_row": ["DB", "MATRIX", "UPDATER"],
    "backfill_strategy3_touch_matrix": ["DB", "MATRIX"],
    "render_strategy4_dual_engine_matrix": ["DB", "OUT"],
    "build_market_triggered_theme_brief": ["ROOT", "EXPORT_DIR"],
    "render_market_triggered_theme_brief_html": ["ROOT"],
}.items():
    module = importlib.import_module("scripts." + name)
    constants[name] = {attr: str(getattr(module, attr)) for attr in attrs}
print(json.dumps(dict(executables=executables, constants=constants)))
'''
    before = inventory(code)
    result = subprocess.run([sys.executable, "-P", "-c", probe], cwd=elsewhere, env=env,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    for filename in info["executables"]:
        assert Path(filename).is_file() and Path(filename).is_relative_to(code), filename
    for attrs in info["constants"].values():
        for attr, filename in attrs.items():
            assert Path(filename).is_relative_to(code if attr in {"ROOT", "UPDATER"} else data)
    assert inventory(code) == before


def test_missing_direct_script_does_not_search_data_tree(rig):
    code, _, _, _ = rig
    (code / "scripts/render_daily_review_briefing.py").unlink()
    result = launch(rig, "--only-step", "daily-review-html")
    assert result.returncode != 0
    assert "No such file or directory" in result.stdout
    assert "STALE_RENDERER" not in result.stdout + result.stderr


@requires_zsh
def test_nightly_callsite_real_regression_and_restore(rig):
    """仅在夹具副本变异；真实 shell → 启动器 → CLI → 子进程，不与工作树测试抢文件。"""
    code, data, elsewhere, env = rig
    script = code / "skills/daily-full-review/scripts/nightly_full_review.sh"
    original = script.read_text()
    # 本测试只验生成链；L2/通知/方法飞轮由已有 wiring 测试负责。
    dispatcher = elsewhere / "python-dispatch"
    dispatcher.write_text(f'''#!{sys.executable}
import os, sys
args = sys.argv[1:]
if any(a.endswith("run_daily_generation.py") for a in args) or "intelligence.cli" in args:
    args[args.index("--from-step")] = "--only-step"
    os.execv(sys.executable, [sys.executable, *args, "--no-alert"])
sys.exit(0)
''')
    dispatcher.chmod(0o755)
    l2 = code / "scripts/moneyflow/run_l2_pipeline.sh"
    l2.parent.mkdir(exist_ok=True)
    l2.write_text("#!/bin/sh\nexit 0\n")
    l2.chmod(0o755)
    noop = elsewhere / "osascript"
    noop.write_text("#!/bin/sh\nexit 0\n")
    noop.chmod(0o755)
    env.update(FINANCE_PYTHON=str(dispatcher), FINANCE_LOCK_DIR=str(data / "locks"),
               FINANCE_OPS_HEALTH_LOG=str(data / "health.log"),
               METHOD_STUDY_DIR=str(data / "method"), PATH=f"{elsewhere}:{env['PATH']}")
    def run():
        return subprocess.run(["/bin/zsh", str(script), "finalize", DAY], cwd=elsewhere,
                              env=env, text=True, capture_output=True, timeout=45)
    before = inventory(code)
    good = run()
    assert good.returncode == 0, good.stdout + good.stderr
    assert f"generation_import={code}/intelligence/__init__.py" in good.stderr
    assert inventory(code) == before
    assert '"$OPS_PYTHON" -P "$generation_launcher"' in original
    # 保留 PYTHONPATH=CODE_ROOT，唯独回到历史裸 -m/cwd；它仍会优先加载 DATA_ROOT。
    mutated = original.replace('PYTHONSAFEPATH=1 ', '').replace(
        '"$OPS_PYTHON" -P "$generation_launcher"', '"$OPS_PYTHON" -m intelligence.cli daily')
    try:
        script.write_text(mutated)
        bad = run()
        assert bad.returncode != 0
        assert "DATA_TREE_CODE_EXECUTED" in bad.stderr
    finally:
        script.write_text(original)
    restored = run()
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert inventory(code) == before


@pytest.mark.parametrize("destination,step", [
    ("app/users/root-test", "framework-interpretation"),
    (f"复盘/daily/{DAY}", "daily-review-html"),
    ("skills/daily-full-review/state", "daily-review"),
    (f"market_feature_store/exports/{DAY}-daily-review.json", "daily-review"),
    ("app/users/root-test/workflow_metrics.jsonl", "framework-interpretation"),
    ("state/episodes/fixture-episode", "daily-review"),
    ("db/snapshots/increments", "daily-review"),
])
def test_existing_write_destination_symlink_into_code_is_rejected_before_steps(rig, destination, step):
    code, data, _, _ = rig
    target = code / "qc-wrong-output"
    if destination.endswith((".json", ".jsonl")):
        target.write_text("keep me")
    else:
        target.mkdir()
    link = data / destination
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=target.is_dir())
    before_code, before_data = inventory(code), inventory(data)
    result = launch(rig, "--only-step", step)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "writable path is in CODE_ROOT" in result.stderr
    assert inventory(code) == before_code
    assert inventory(data) == before_data


@pytest.mark.parametrize("variant", ["abbreviation", "equals", "duplicate-last-unsafe"])
def test_summary_guard_uses_same_argument_meaning_as_daily_cli(rig, variant):
    code, data, _, _ = rig
    unsafe = str(code / "qc-summary.json")
    args = {"abbreviation": ["--summary-j", unsafe],
            "equals": [f"--summary-json={unsafe}"],
            "duplicate-last-unsafe": ["--summary-json", "safe.json", "--summary-json", unsafe]}[variant]
    before = inventory(code)
    result = launch(rig, "--dry-run", *args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "writable path is in CODE_ROOT" in result.stderr
    assert not (data / "safe.json").exists()
    assert inventory(code) == before


def test_summary_last_value_and_safe_external_user_symlinks_are_preserved(rig):
    code, data, elsewhere, _ = rig
    target = elsewhere / "existing-user"
    target.mkdir()
    sentinel = target / "profile.json"
    sentinel.write_text('{"existing": true}')
    user = data / "app/users/root-test"
    user.parent.mkdir(parents=True)
    user.symlink_to(target, target_is_directory=True)
    before = inventory(code)
    result = launch(rig, "--only-step", "framework-interpretation", "--summary-json",
                    str(code / "unused.json"), "--summary-j=safe.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (data / "safe.json").is_file()
    assert (target / "workflow_metrics.jsonl").is_file()
    assert sentinel.read_text() == '{"existing": true}'
    assert inventory(code) == before


@pytest.mark.parametrize("relative", [
    "scripts/render_daily_review_briefing.py",
    "scripts/build_market_triggered_theme_brief.py",
    "skills/strategy1-matrix/scripts/update_matrix.py",
    "intelligence/workflows/daily_review.py",
])
@pytest.mark.parametrize("raises", [False, True])
def test_code_symlink_escape_is_rejected_before_any_stale_code_executes(rig, relative, raises):
    code, data, _, _ = rig
    stale = data / "stale.py"
    marker = "QC_DATA_TREE_SCRIPT_EXECUTED"
    stale.write_text(f"raise RuntimeError({marker!r})\n" if raises else f"print({marker!r})\n")
    link = code / relative
    link.unlink()
    link.symlink_to(stale)
    before_code, before_data = inventory(code), inventory(data)
    result = launch(rig, "--only-step", "daily-review-html")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "code escapes FINANCE_CODE_ROOT" in result.stderr
    assert marker not in result.stdout + result.stderr
    assert inventory(code) == before_code
    assert inventory(data) == before_data


def test_internal_code_symlink_still_uses_same_snapshot(rig):
    code, _, _, _ = rig
    original = code / "scripts/render_daily_review_briefing.py"
    target = code / "scripts/pinned_renderer.py"
    original.rename(target)
    original.symlink_to(target)
    result = launch(rig, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr


def test_safe_external_directory_link_does_not_hide_nested_code_write(rig):
    code, data, elsewhere, _ = rig
    target = elsewhere / "external-user"
    target.mkdir()
    (target / "workflow_metrics.jsonl").symlink_to(code / "qc-metrics.jsonl")
    user = data / "app/users/root-test"
    user.parent.mkdir(parents=True)
    user.symlink_to(target, target_is_directory=True)
    before = inventory(code)
    result = launch(rig, "--only-step", "framework-interpretation")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "writable path is in CODE_ROOT" in result.stderr
    assert inventory(code) == before


def test_safe_user_directory_cycle_is_bounded_and_not_rejected(rig):
    code, data, _, _ = rig
    user = data / "app/users/root-test"
    user.mkdir(parents=True)
    (user / "cycle").symlink_to(user, target_is_directory=True)
    before = inventory(code)
    result = launch(rig, "--only-step", "framework-interpretation")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (user / "workflow_metrics.jsonl").is_file()
    assert inventory(code) == before


@pytest.mark.parametrize("gate", ["write-tree", "summary", "source-snapshot"])
def test_removed_guard_reproduces_defect_then_restore_blocks_it(rig, gate):
    """Mutate only rig's isolated copy: witness the forbidden side effect, not argv."""
    code, data, _, _ = rig
    marker = "QC_NESTED_CODE_EXECUTED"
    if gate == "write-tree":
        target = code / "qc-user"
        target.mkdir()
        user = data / "app/users/root-test"
        user.parent.mkdir(parents=True)
        user.symlink_to(target, target_is_directory=True)
        source = code / "intelligence/workflows/generation_paths.py"
        old = "        _validate_write_tree(target, code=code, data=data, seen=seen)"
        replacement = "        pass  # mutation: bypass descendant checks"
        args = ["--only-step", "framework-interpretation"]
        forbidden = target / "workflow_metrics.jsonl"
    elif gate == "summary":
        source = code / "intelligence/workflows/generation_paths.py"
        old = "        _outside_code(Path(summary_json), code=code, data=data)"
        replacement = "        pass  # mutation: bypass summary validation"
        forbidden = code / "qc-summary.json"
        args = ["--dry-run", "--summary-j", str(forbidden)]
    else:
        source = code / "scripts/run_daily_generation.py"
        old = "        _validate_code_snapshot(code)"
        replacement = "        pass  # mutation: bypass source snapshot validation"
        stale = data / "stale.py"
        stale.write_text(f"raise RuntimeError({marker!r})\n")
        link = code / "intelligence/workflows/daily_review.py"
        link.unlink()
        link.symlink_to(stale)
        args = ["--dry-run"]
        forbidden = None
    original = source.read_text()
    assert original.count(old) == 1
    good = launch(rig, *args)
    assert good.returncode == 2 and marker not in good.stdout + good.stderr
    try:
        source.write_text(original.replace(old, replacement))
        broken = launch(rig, *args)
        if forbidden:
            assert broken.returncode == 0, broken.stdout + broken.stderr
            assert forbidden.is_file()
            forbidden.unlink()
        else:
            assert marker in broken.stdout + broken.stderr
    finally:
        source.write_text(original)
    restored = launch(rig, *args)
    assert restored.returncode == 2 and marker not in restored.stdout + restored.stderr
    if forbidden:
        assert not forbidden.exists()


def test_queue_archive_cannot_write_inside_code_snapshot(rig):
    code, data, _, _ = rig
    before = inventory(code)
    result = launch(rig, "--only-step", "kb-ingest-receive", "--kb-receive-wiki", str(code / "wiki"))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "generation writable path is in CODE_ROOT" in result.stderr
    assert inventory(code) == before
