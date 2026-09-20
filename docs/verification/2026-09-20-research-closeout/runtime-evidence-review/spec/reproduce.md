两条探针均只调用脚本化模型/本地 TestClient，临时存储在本目录。退出 1 表示合同反例复现；不代表脚本崩溃。Timer 探针在 finally 中释放并 join 所有测试线程。

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/probe_future_evidence.py /Users/a77/fwp-wt-runtime-contracts-0918

/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/probe_future_evidence.py /Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/base-6b70e540

/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/probe_api_timer.py /Users/a77/fwp-wt-runtime-contracts-0918
```

期望当前 a7 第一条 exit 1（全未来两格失败，混合两格正常），6b70 第二条 exit 0（四格正常），第三条 exit 1（drain 返回时 Timer 仍 alive）。基线目录由候选仓的完整 `git archive 6b70e540` 导出，身份见 `base-identity.json`。不是混用候选模块的动态替换。

固定旧收据复核：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/verify_old_receipts.py
```

本轮所选回归命令与80P含义：

```bash
cd /Users/a77/fwp-wt-runtime-contracts-0918
FWP_TEST_RECEIPT=0 FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/users /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_episode_evidence_snapshot.py intelligence/tests/test_api_fixture_lifecycle.py intelligence/tests/test_sub_research_persistence.py::test_linked_nonterminal_restore_refuses_without_mutating_logs -o cache_dir=/Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/pytest-cache --basetemp=/Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/pytest-tmp --junitxml=/Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-review/spec/selected.xml
```
