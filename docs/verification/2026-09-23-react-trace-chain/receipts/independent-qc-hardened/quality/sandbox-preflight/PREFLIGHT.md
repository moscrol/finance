Offline harness control only.

```json
{
  "verdict": "STAGE_COMPLETE",
  "summary": "Offline harness control only.",
  "claims": [
    {
      "id": "C1",
      "status": "not_verified",
      "evidence": [],
      "note": "not a product review"
    },
    {
      "id": "C2",
      "status": "not_verified",
      "evidence": [],
      "note": "not a product review"
    },
    {
      "id": "C3",
      "status": "not_verified",
      "evidence": [],
      "note": "not a product review"
    },
    {
      "id": "C4",
      "status": "not_verified",
      "evidence": [],
      "note": "not a product review"
    },
    {
      "id": "C5",
      "status": "not_verified",
      "evidence": [],
      "note": "not a product review"
    },
    {
      "id": "C6",
      "status": "not_verified",
      "evidence": [],
      "note": "not a product review"
    }
  ],
  "findings": [],
  "limits": [
    "zero model; host-only admission"
  ],
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_admission.py",
    "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_misleading_output.py"
  ],
  "stage": "preflight",
  "axis": "quality",
  "revision": "d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c",
  "baseline": "626d8a508c1c988ff094110b371987e6afdcdd15",
  "complete": true,
  "delivery_gaps": [],
  "test_runs": [
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_admission.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/tmp/preflight-004-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/tmp/preflight-004-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 0,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 551,
      "output_sha256": "940b3f4c6b90804ff0473749b198025c6af1ba4a645173f504aa4136283bfc2d",
      "suite": "probes",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_admission.py"
      ],
      "counts": {
        "tests": 2,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "passed": 2
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_admission.py": "9a9d19fa735e016febe60829737db070a1eda635fd8800fb1824481148102f6d"
      },
      "inputs_unchanged": true,
      "junit_sha256": "78a0720728e48014c0ede5cb41fe20016ec030ddc20e9ad60ddf4039b9bfa182",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/sandbox-preflight/commands/004-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/sandbox-preflight/commands/004-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-c",
        "assert 1 == 2, \"intentional_positive_control\""
      ],
      "shell": false,
      "target_exit_code": 1,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 67,
      "output_sha256": "c0441086a31b6eacefccdba15ddcb8f7496ecd7f7f468759cc3094e462a39d8c",
      "suite": "control",
      "files": [],
      "counts": null,
      "input_sha256": {},
      "inputs_unchanged": true,
      "junit_sha256": null,
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/sandbox-preflight/commands/005-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/sandbox-preflight/commands/005-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_misleading_output.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/tmp/preflight-007-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/tmp/preflight-007-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 1,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 439,
      "output_sha256": "9101fe3ed8ef2f2fd39a33dc4a93e69062528d56b2dd17c8df406d95e0d6d202",
      "suite": "probes",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_misleading_output.py"
      ],
      "counts": {
        "tests": 1,
        "failed": 1,
        "errors": 0,
        "skipped": 0,
        "passed": 0
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/work/probes/test_harness_misleading_output.py": "a6fdfd3940384131de1c79d7f34296ce94e85bbebd19582777ed08e1b61e74d9"
      },
      "inputs_unchanged": true,
      "junit_sha256": "046dc6a76b0f0c8e928be855cda977c1b938064aa111f32935cdbbbcdeabfb6b",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/sandbox-preflight/commands/007-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/quality/sandbox-preflight/commands/007-run_tests/output.log"
    }
  ],
  "host_bound": true
}
```
