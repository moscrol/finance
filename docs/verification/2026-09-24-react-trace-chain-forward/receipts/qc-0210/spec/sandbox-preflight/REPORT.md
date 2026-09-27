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
    "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_admission.py",
    "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_misleading_output.py"
  ],
  "stage": "preflight",
  "axis": "spec",
  "revision": "f7d525ca0bdc33df2bbbed96bdb8a8af3b58ddf0",
  "baseline": "3bb81b9638f97b4773ce0f338df3a505b7c0162f",
  "complete": true,
  "delivery_gaps": [],
  "test_runs": [
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_admission.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/tmp/preflight-004-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/tmp/preflight-004-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 0,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 620,
      "output_sha256": "295e6dda8c152848d2179f797ff03b9eaf3d0e5c0dec1bf749559f5530bcc953",
      "suite": "probes",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_admission.py"
      ],
      "counts": {
        "tests": 2,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "passed": 2
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_admission.py": "b92edf70401042d494a4ffcc957950ae1ba7b099982e0330dde439ccf6e61de7"
      },
      "inputs_unchanged": true,
      "junit_sha256": "6f0d0fcbf989c3be25cfe9695162c58a1fab5fd367044a6a5cf37d325397d3e3",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/004-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/004-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_condition_reference_seams.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_episode_numeric_citations.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_episode_protocol.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_finance_query_repair_feedback.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_agent_episode_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_research_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/tests/test_history_model_projection.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/tmp/preflight-005-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/tmp/preflight-005-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 0,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 12078,
      "output_sha256": "723151f502c907e5209dd6b4319014785605728886dee52e780492329aa25d7a",
      "suite": "author",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_condition_reference_seams.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_episode_numeric_citations.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_episode_protocol.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_finance_query_repair_feedback.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_agent_episode_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_research_progress.py",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/tests/test_history_model_projection.py"
      ],
      "counts": {
        "tests": 186,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "passed": 186
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_condition_reference_seams.py": "099e92c8f46827cfd819afbb759d75ccb5d3afeb712a38ee5541dacba55ec5b5",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_episode_numeric_citations.py": "3ba5b72798f9dbd43e048416ffad0a982856135aea0a3b51c4325c57523f3adf",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_episode_protocol.py": "7baa5d08d3ce8ac9148305e3765b47787311dd05bdc42351929ada599b657b05",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_finance_query_repair_feedback.py": "ca54928b284e978c504723e16de9540b53eeff862b79af15bd246c6aa5e07cd9",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_agent_episode_progress.py": "163cc2d1590897957b739030a80d677ab7980805ff4ae8ebc4760b6d884fc202",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/intelligence/tests/test_research_progress.py": "072ce684cfbdb0dab99deb4874bfb9a4d408207f49743d8f1fa990a458b9f06c",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private/tests/test_history_model_projection.py": "fce0c1146f55a5656988f840e3b42e328cf302c942032b57e7b065b152e23d62"
      },
      "inputs_unchanged": true,
      "junit_sha256": "d1178a8d903d5f997d5839e7af6c7af4db9229db199b76cc5e09c5138d57d812",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/005-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/005-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/tools.sb",
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
      "elapsed_ms": 53,
      "output_sha256": "c0441086a31b6eacefccdba15ddcb8f7496ecd7f7f468759cc3094e462a39d8c",
      "suite": "control",
      "files": [],
      "counts": null,
      "input_sha256": {},
      "inputs_unchanged": true,
      "junit_sha256": null,
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/006-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/006-run_tests/output.log"
    },
    {
      "command": [
        "/usr/bin/sandbox-exec",
        "-f",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/tools.sb",
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-B",
        "-m",
        "pytest",
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_misleading_output.py",
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/candidate/finance-workspace-private",
        "--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/tmp/preflight-008-run_tests",
        "--junitxml=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/tmp/preflight-008-run_tests.xml"
      ],
      "shell": false,
      "target_exit_code": 1,
      "signal": null,
      "killed": false,
      "spawn_error": null,
      "elapsed_ms": 768,
      "output_sha256": "0a2c9789c4b076a272d1a192457e63aa728c5bf850affe4a6332e9cc70b53ea7",
      "suite": "probes",
      "files": [
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_misleading_output.py"
      ],
      "counts": {
        "tests": 1,
        "failed": 1,
        "errors": 0,
        "skipped": 0,
        "passed": 0
      },
      "input_sha256": {
        "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/work/probes/test_harness_misleading_output.py": "a6fdfd3940384131de1c79d7f34296ce94e85bbebd19582777ed08e1b61e74d9"
      },
      "inputs_unchanged": true,
      "junit_sha256": "76bc690f985040f15e4eed51eddbb1851739c6124d206cfe6f869fa756f33754",
      "receipt": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/008-run_tests/result.json",
      "output": "/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260924-0210/spec/sandbox-preflight/commands/008-run_tests/output.log"
    }
  ],
  "host_bound": true
}
```
