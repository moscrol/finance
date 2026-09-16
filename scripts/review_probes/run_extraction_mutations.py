"""工单 #53 有牙验收：固定 revision，在独占临时 worktree 拆保护、验红、还原验绿。

旧运行器只存 /tmp，锚点失效会继续跑、错误收集也可能被当成「红」。本入口把
变异定义入库，唯一锚点 / 可编译 / 实际执行非空 / 无 collection error 均硬断言；
每次改坏与还原保存完整日志、JUnit、diff 和字节指纹。不会修改调用者工作树，
不会写真人台账；局部变异不生成全量测试收据。不代表独立评审或真人效果验证。

用法（在仓根，用 test-environment.json 指定的 Python）：
    python scripts/review_probes/run_extraction_mutations.py --output <新证据目录>
    python scripts/review_probes/run_extraction_mutations.py --revision <sha> --output <目录>

只测试已提交 revision；未提交源码或定义不会被悄悄混进证据。证据目录必须新建。
临时 worktree 在成功后移除；失败则保留还原后的树用于诊断，路径写入 results.json。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

TESTS = [
    "intelligence/tests/test_observation_extraction_first.py",
    "intelligence/tests/test_extraction_first_review_fixes.py",
    "intelligence/tests/test_extraction_closeout.py",
]
DEFINITIONS = "scripts/review_probes/extraction_mutations.json"


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run_tests(root: Path, out: Path, label: str, targets: list[str] | None = None) -> dict:
    junit = out / f"{label}.xml"
    cmd = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:randomly",
           "-p", "no:cacheprovider", "--tb=short", "--junitxml", str(junit), *TESTS]
    if targets:
        cmd += ["-k", " or ".join(targets)]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "PYTHONPATH": str(root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "FWP_TEST_RECEIPT": "0",
        "FORESIGHT_USERS_DIR": str(out / "isolated-users"),
    }
    proc = subprocess.run(cmd, cwd=root, env=env, text=True, capture_output=True, timeout=180)
    (out / f"{label}.log").write_text(
        json.dumps({"command": cmd, "cwd": str(root), "revision": git(root, "rev-parse", "HEAD")})
        + "\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr + f"\nEXIT={proc.returncode}\n",
        encoding="utf-8",
    )
    cases = list(ET.parse(junit).getroot().iter("testcase"))
    result = {
        "label": label, "exit": proc.returncode, "executed": len(cases),
        "failures": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases),
        "skipped": sum(c.find("skipped") is not None for c in cases),
        "failed_cases": [
            {"class": c.get("classname"), "name": c.get("name"),
             "message": c.find("failure").get("message", "")}
            for c in cases if c.find("failure") is not None
        ],
    }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def check_result(result: dict, *, red: bool = False) -> None:
    assert result["executed"] > 0, result
    assert result["errors"] == result["skipped"] == 0, result
    assert result["exit"] == (1 if red else 0), result
    assert (result["failures"] > 0) if red else (result["failures"] == 0), result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    revision = git(repo, "rev-parse", f"{args.revision}^{{commit}}")
    out = args.output.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False)
    parent = Path(tempfile.mkdtemp(prefix="extraction-closeout-mutations-")).resolve()
    root = parent / "tree"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(root), revision], check=True)
    report = {"revision": revision, "tree": str(root), "python": sys.executable,
              "complete": False, "runs": [], "mutations": []}
    try:
        assert git(root, "status", "--porcelain") == ""
        definitions_raw = (root / DEFINITIONS).read_bytes()
        mutations = json.loads(definitions_raw)
        assert mutations and len({m["id"] for m in mutations}) == len(mutations)
        (out / "definitions.json").write_bytes(definitions_raw)
        report["definitions_sha256"] = digest(definitions_raw)
        # 确保实际执行的 runner 也是该 revision 的版本。
        relative_runner = "scripts/review_probes/run_extraction_mutations.py"
        assert Path(__file__).read_bytes() == (root / relative_runner).read_bytes()
        baseline = run_tests(root, out, "baseline")
        report["runs"].append(baseline)
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
                red = run_tests(root, out, f"{ident}-red", mutation["targets"])
            finally:
                path.write_bytes(before)
            assert path.read_bytes() == before
            green = run_tests(root, out, f"{ident}-green", mutation["targets"])
            report["runs"].extend([red, green])
            report["mutations"].append({"id": ident, "path": relative, "before_sha256": digest(before),
                                        "mutated_sha256": digest(changed.encode("utf-8")),
                                        "restored_sha256": digest(path.read_bytes())})
            (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            check_result(red, red=True)
            check_result(green)
        restored = run_tests(root, out, "restored-full")
        report["runs"].append(restored)
        check_result(restored)
        assert git(root, "status", "--porcelain") == ""
        report["complete"] = True
    finally:
        report["final_status"] = git(root, "status", "--porcelain")
        (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", str(root)], check=True)
    parent.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
