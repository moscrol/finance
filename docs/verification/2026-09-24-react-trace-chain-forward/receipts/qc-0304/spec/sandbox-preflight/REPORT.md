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
    "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_admission.py",
    "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_misleading_output.py"
  ],
  "stage": "preflight",
  "axis": "spec",
  "revision": "27034ce44ed41b1af0a570c2ccc534066a1656f6",
  "baseline": "3bb81b9638f97b4773ce0f338df3a505b7c0162f",
  "complete": true,
  "delivery_gaps": [],
  "test_runs": [
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_admission.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/tmp/preflight-004-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/tmp/preflight-004-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 0,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 916,
      "output_sha256": "72a5ab32730b2dd09e44d8ce28e63a5a77ab83238fc82109cf0f9b687b0f7461",
      "suite": "probes",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_admission.py"
      ],
      "counts": {
        "tests": 2,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "passed": 2
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_admission.py": "8d41d9ad0da749cc1133c7d1f0267af664b5bff447ed3439d4aed3b231c9b074"
      },
      "inputs_unchanged": true,
      "junit_sha256": "2a710c2720d28032f83c40ed001a0e257e304e09bbc5e503dc533da6f01dc12a",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/004-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/004-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_condition_reference_seams.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_episode_numeric_citations.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_episode_protocol.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_finance_query_repair_feedback.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_agent_episode_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_research_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/tests/test_history_model_projection.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/tmp/preflight-005-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/tmp/preflight-005-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 0,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 14162,
      "output_sha256": "b3e6d9b4e9b10c91dab434fbde4a6dbea3b13b8875ccaca99f2065f394da204b",
      "suite": "author",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_condition_reference_seams.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_episode_numeric_citations.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_episode_protocol.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_finance_query_repair_feedback.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_agent_episode_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_research_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/tests/test_history_model_projection.py"
      ],
      "counts": {
        "tests": 232,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "passed": 232
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_condition_reference_seams.py": "1da6c231ec6f6dbf7c59f33421bd993e627eadef0af862525705c6e06615eccf",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_episode_numeric_citations.py": "3ba5b72798f9dbd43e048416ffad0a982856135aea0a3b51c4325c57523f3adf",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_episode_protocol.py": "7baa5d08d3ce8ac9148305e3765b47787311dd05bdc42351929ada599b657b05",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_finance_query_repair_feedback.py": "ca54928b284e978c504723e16de9540b53eeff862b79af15bd246c6aa5e07cd9",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_agent_episode_progress.py": "163cc2d1590897957b739030a80d677ab7980805ff4ae8ebc4760b6d884fc202",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/intelligence/tests/test_research_progress.py": "072ce684cfbdb0dab99deb4874bfb9a4d408207f49743d8f1fa990a458b9f06c",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private/tests/test_history_model_projection.py": "fce0c1146f55a5656988f840e3b42e328cf302c942032b57e7b065b152e23d62"
      },
      "inputs_unchanged": true,
      "junit_sha256": "9d76d116fe7a71f4a276f0a527cc0a9fa722be36c3393f85c8f226a74a91f72f",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/005-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/005-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/tools.sb",
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
      "elapsed_ms": 79,
      "output_sha256": "c0441086a31b6eacefccdba15ddcb8f7496ecd7f7f468759cc3094e462a39d8c",
      "suite": "control",
      "files": [],
      "counts": null,
      "input_sha256": {},
      "inputs_unchanged": true,
      "junit_sha256": null,
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/006-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/006-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_misleading_output.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/tmp/preflight-008-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/tmp/preflight-008-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 1,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 598,
      "output_sha256": "e064404881855a2c0ea3a3b4098c97d82e0453d092f5ad9cea69dc46b26e2b5c",
      "suite": "probes",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_misleading_output.py"
      ],
      "counts": {
        "tests": 1,
        "failed": 1,
        "errors": 0,
        "skipped": 0,
        "passed": 0
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/work/probes/test_harness_misleading_output.py": "a6fdfd3940384131de1c79d7f34296ce94e85bbebd19582777ed08e1b61e74d9"
      },
      "inputs_unchanged": true,
      "junit_sha256": "3711a95ec367e2c69c9bf4b35f47d92966c5a2b36ff0cf4af5d0564d3ba5c07e",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/008-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0304/spec/sandbox-preflight/commands/008-run_tests/output.log"
    }
  ],
  "host_bound": true
}
```
