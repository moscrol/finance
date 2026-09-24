"""工单 #53 有牙验收：固定 revision，在独占临时 worktree 拆保护、验红、还原验绿。

旧运行器只存 /tmp，锚点失效会继续跑、错误收集也可能被当成「红」。本入口把
变异定义入库，唯一锚点 / 可编译 / 实际执行非空 / 无 collection error 均硬断言；
每次改坏与还原保存持续输出、进程状态、JUnit、diff 和字节指纹。180秒帽不变；
单项测试45秒未返回时转储线程栈，超时杀独占进程组。缺JUnit不冒充零执行。
不会修改调用者工作树，
不会写真人台账；局部变异不生成全量测试收据。不代表独立评审或真人效果验证。

用法（在仓根，用 test-environment.json 指定的 Python）：
    python scripts/review_probes/run_extraction_mutations.py --output <新证据目录>
    python scripts/review_probes/run_extraction_mutations.py --revision <sha> --output <目录>
    python scripts/review_probes/run_extraction_mutations.py --suite financial-r6 --output <新目录>
    python scripts/review_probes/run_extraction_mutations.py --suite research-delivery --output <新目录>
    python scripts/review_probes/run_extraction_mutations.py --suite publication --output <新目录>
    python scripts/review_probes/run_extraction_mutations.py --suite rag-transport --output <新目录>

默认仍跑工单 #53；其他合同复用 --definitions <仓内 JSON> --tests <测试路径...>，
不复制 runner。只测试已提交 revision；未提交源码或定义不会被悄悄混进证据。证据目录必须新建。
临时 worktree 在成功后移除；失败则保留还原后的树用于诊断，路径写入 results.json。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

TESTS = [
    "intelligence/tests/test_observation_extraction_first.py",
    "intelligence/tests/test_extraction_first_review_fixes.py",
    "intelligence/tests/test_extraction_closeout.py",
]
DEFINITIONS = "scripts/review_probes/extraction_mutations.json"
SUITES = {
    "extraction": (TESTS, DEFINITIONS),
    "financial-r6": ([
        "intelligence/tests/test_financial_r6_regressions.py",
    ], "scripts/review_probes/financial_r6_mutations.json"),
    "financial-delivery": ([
        "intelligence/tests/test_financial_delivery_integration.py",
    ], "scripts/review_probes/financial_delivery_mutations.json"),
    "publication": ([
        "intelligence/tests/test_workbench_api.py",
        "intelligence/tests/test_workbench_conversation_integration.py",
        "intelligence/tests/test_financial_publication_integration.py",
        "tests/test_workbench_probe.py",
    ], "scripts/review_probes/publication_mutations.json"),
    "rag-transport": ([
        "intelligence/tests/test_rag_worker_transport.py",
        "intelligence/tests/test_rag_worker.py",
        "intelligence/tests/test_rag_worker_keepalive.py",
    ], "scripts/review_probes/rag_transport_mutations.json"),
    "research-delivery": ([
        "intelligence/tests/test_calculation_result_delivery.py",
        "intelligence/tests/test_research_delivery_checks.py",
        "intelligence/tests/test_research_delivery_retention.py",
        "intelligence/tests/test_research_delivery_review_regressions.py",
        "intelligence/tests/test_research_delivery_ratio_scope.py",
        "intelligence/tests/test_research_delivery_repair.py",
        "intelligence/tests/test_frozen_research_delivery.py",
        "intelligence/tests/test_research_delivery_live_products.py",
        "intelligence/tests/test_research_delivery_disclosure_binding.py",
        "intelligence/tests/test_research_delivery_ratio_boundaries.py",
    ], "scripts/review_probes/research_delivery_mutations.json"),
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _run_logged_command(
    root: Path, out: Path, label: str, cmd: list[str], env: dict[str, str],
    *, timeout: float = 180,
) -> dict:
    """输出直接落盘，不在communicate内存中等到成功才留证；只管理自己的进程组。"""
    state_path = out / f"{label}.process.json"
    log_path = out / f"{label}.log"
    if state_path.exists() or log_path.exists():
        raise FileExistsError(f"refusing to overwrite run evidence: {label}")
    result = {
        "label": label, "command": cmd, "cwd": str(root),
        "revision": git(root, "rev-parse", "HEAD"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": timeout, "status": "starting", "exit": None,
        "timed_out": False, "executed": None, "failures": None,
        "errors": None, "skipped": None, "failed_cases": [],
        "junit_status": "not_evaluated", "output_mode": "combined_stdout_stderr",
    }
    save_json(state_path, result)
    started = time.monotonic()
    proc = None
    with log_path.open("xb", buffering=0) as log:
        log.write((json.dumps(result, ensure_ascii=False) + "\n").encode("utf-8"))
        try:
            proc = subprocess.Popen(
                cmd, cwd=root, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            result.update(status="running", pid=proc.pid, process_group=proc.pid)
            save_json(state_path, result)
            proc.wait(timeout=max(0, timeout - (time.monotonic() - started)))
            result["status"] = "completed"
        except subprocess.TimeoutExpired:
            result.update(status="timed_out", timed_out=True)
        except BaseException as exc:
            result.update(
                status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "runner_error",
                error_type=type(exc).__name__,
            )
            raise
        finally:
            # 即使leader已退出，也收掉本组遗留子进程；不按名字全局pkill。
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                    result["process_group_cleanup"] = "sigkill_sent"
                except ProcessLookupError:
                    result["process_group_cleanup"] = "already_absent"
                except OSError as exc:
                    result.update(status="cleanup_error", cleanup_error=type(exc).__name__)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    result.update(status="cleanup_error", cleanup_error="leader_not_reaped")
                result["exit"] = proc.returncode
            result.update(
                finished_at=datetime.now(timezone.utc).isoformat(),
                elapsed_seconds=time.monotonic() - started,
            )
            log.write(f"\nEXIT={result['exit']} STATUS={result['status']}\n".encode("utf-8"))
            os.fsync(log.fileno())
            save_json(state_path, result)
    return result


def run_tests(
    root: Path, out: Path, label: str, tests: list[str],
    targets: list[str] | None = None,
) -> dict:
    junit = out / f"{label}.xml"
    if junit.exists() or (out / f"{label}.result.json").exists():
        raise FileExistsError(f"refusing to reuse JUnit/result evidence: {label}")
    cmd = [sys.executable, "-u", "-B", "-m", "pytest", "-vv", "--capture=tee-sys",
           "-p", "no:randomly", "-p", "no:cacheprovider", "--tb=short",
           "-o", "faulthandler_timeout=45", "--junitxml", str(junit), *tests]
    if targets:
        cmd += ["-k", " or ".join(targets)]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "PYTHONPATH": str(root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "FWP_TEST_RECEIPT": "0",
        "FORESIGHT_USERS_DIR": str(out / "isolated-users"),
        "FORESIGHT_LLM_KEYCHAIN": "0",
        **{k: os.environ[k] for k in ("LANG", "TMPDIR", "KNOWLEDGE_WIKI") if k in os.environ},
    }
    result = _run_logged_command(root, out, label, cmd, env)
    try:
        cases = list(ET.parse(junit).getroot().iter("testcase"))
    except (OSError, ET.ParseError) as exc:
        result.update(junit_status="missing_or_invalid", junit_error=type(exc).__name__)
    else:
        result.update(
            junit_status="parsed", executed=len(cases),
            failures=sum(c.find("failure") is not None for c in cases),
            errors=sum(c.find("error") is not None for c in cases),
            skipped=sum(c.find("skipped") is not None for c in cases),
            failed_cases=[
                {"class": c.get("classname"), "name": c.get("name"),
                 "message": c.find("failure").get("message", "")}
                for c in cases if c.find("failure") is not None
            ],
        )
    save_json(out / f"{label}.result.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def check_result(result: dict, *, red: bool = False) -> None:
    assert result["status"] == "completed" and not result["timed_out"], result
    assert result["junit_status"] == "parsed", result
    assert result["executed"] > 0, result
    assert result["errors"] == result["skipped"] == 0, result
    assert result["exit"] == (1 if red else 0), result
    assert (result["failures"] > 0) if red else (result["failures"] == 0), result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--suite", choices=tuple(SUITES), default="extraction")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--definitions", help="仓内已提交的变异定义 JSON；优先于 --suite")
    parser.add_argument("--tests", nargs="+", help="仓内已提交的测试路径；优先于 --suite")
    args = parser.parse_args(argv)
    suite_tests, suite_definitions = SUITES[args.suite]
    overridden = args.tests is not None or args.definitions is not None
    args.tests = args.tests if args.tests is not None else suite_tests
    args.definitions = args.definitions if args.definitions is not None else suite_definitions
    # 显式选择器覆盖了 --suite 时，results.json 的 suite 标签不能再冒充某个冻结套件。
    args.suite = "custom" if overridden else args.suite
    return args


def main() -> int:
    args = _parse_args()
    tests, definitions = args.tests, args.definitions
    os.umask(0o022)
    repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    revision = git(repo, "rev-parse", f"{args.revision}^{{commit}}")
    out = args.output.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False)
    parent = Path(tempfile.mkdtemp(prefix="contract-mutations-")).resolve()
    root = parent / "tree"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(root), revision], check=True)
    report = {"revision": revision, "suite": args.suite, "tree": str(root), "python": sys.executable,
              "tests": tests, "definitions": definitions,
              "complete": False, "runs": [], "mutations": []}

    def execute(label: str, targets: list[str] | None = None) -> dict:
        report["active_run"] = label
        save_json(out / "results.json", report)
        try:
            return run_tests(root, out, label, tests, targets)
        finally:
            # 中断亦保留进程收据；没有最终JUnit只能记执行数未知，不能记0。
            for suffix in ("result.json", "process.json"):
                receipt = out / f"{label}.{suffix}"
                if receipt.exists():
                    report["runs"].append(json.loads(receipt.read_text(encoding="utf-8")))
                    break
            report["active_run"] = None
            save_json(out / "results.json", report)

    try:
        assert git(root, "status", "--porcelain") == ""
        definitions_path = (root / definitions).resolve()
        assert definitions_path.is_relative_to(root), "definitions must belong to the frozen tree"
        for test_path in tests:
            assert (root / test_path).resolve().is_relative_to(root), test_path
        definitions_raw = definitions_path.read_bytes()
        mutations = json.loads(definitions_raw)
        assert mutations and len({m["id"] for m in mutations}) == len(mutations)
        (out / "definitions.json").write_bytes(definitions_raw)
        report["definitions_sha256"] = digest(definitions_raw)
        # 确保实际执行的 runner 也是该 revision 的版本。
        relative_runner = "scripts/review_probes/run_extraction_mutations.py"
        assert Path(__file__).read_bytes() == (root / relative_runner).read_bytes()
        baseline = execute("baseline")
        check_result(baseline)
        for mutation in mutations:
            ident, relative = mutation["id"], mutation["path"]
            path = (root / relative).resolve()
            assert path.is_relative_to(root), relative
            before = path.read_bytes()
            source = before.decode("utf-8")
            old, new = mutation["old"], mutation["new"]
            assert source.count(old) == 1, (ident, "anchor must match exactly once")
            changed = source.replace(old, new, 1)
            compile(changed, relative, "exec")
            try:
                path.write_text(changed, encoding="utf-8")
                (out / f"{ident}.diff").write_text(git(root, "diff", "--", relative) + "\n", encoding="utf-8")
                red = execute(f"{ident}-red", mutation["targets"])
            finally:
                path.write_bytes(before)
            assert path.read_bytes() == before
            check_result(red, red=True)
            green = execute(f"{ident}-green", mutation["targets"])
            report["mutations"].append({"id": ident, "path": relative, "before_sha256": digest(before),
                                        "mutated_sha256": digest(changed.encode("utf-8")),
                                        "restored_sha256": digest(path.read_bytes())})
            save_json(out / "results.json", report)
            check_result(green)
        restored = execute("restored-full")
        check_result(restored)
        assert git(root, "status", "--porcelain") == ""
        report["complete"] = True
    finally:
        report["final_status"] = git(root, "status", "--porcelain")
        save_json(out / "results.json", report)
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", str(root)], check=True)
    parent.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
