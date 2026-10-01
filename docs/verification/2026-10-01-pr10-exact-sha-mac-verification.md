# PR10精确SHA本机范围验证

不是新修复、不更新他人PR10分支，仅补已有验收门。本次独立detached树锁定PR10当前HEAD `983590438bd48cd1fef4b435dd2276961948e532`，Mac Python3.12.13。

**1107 passed / 114.21s，exit0**；前后clean、真实待重判队列7385行及hash不变。收据 `20261001T092848Z-98359043-7846cfc5a301.json`。没有模型调用、没有开默认关闭的语义召回。

范围在开跑前冻结：对main3a2718c6有变更的21个测试文件，加5个直接近邻。26文件是本次明确集合，不冒称复刻旧Linux的26文件清单；不是全仓结果，也不以跨平台计数差推断收益。

启动协调器曾因Mac kqueue不支持上下文管理而在pytest前退出，失败日志保留；修正为closing后，在R16全仓结束后串行开跑。没有失败用例选优或扩大跳过。

## 冻结文件列表

- `intelligence/tests/test_llm_rate_limit_retry.py`
- `intelligence/tests/test_memory_semantic.py`
- `intelligence/tests/test_method_flywheel.py`
- `intelligence/tests/test_model_admission.py`
- `intelligence/tests/test_model_harness_2x2.py`
- `intelligence/tests/test_numeric_note_false_positives.py`
- `intelligence/tests/test_rejudge_pending_isolation.py`
- `tests/test_agent_hook_roots.py`
- `tests/test_audit_episode_tool_outcomes.py`
- `tests/test_check_regex_routes.py`
- `tests/test_daily_full_preflight.py`
- `tests/test_eval_launchd_installer.py`
- `tests/test_eval_launchd_wiring.py`
- `tests/test_generation_code_root.py`
- `tests/test_market_feature_store_staging_swap.py`
- `tests/test_numeric_gate_label_ab.py`
- `tests/test_prediction_ledger_status.py`
- `tests/test_skill_view_supersession.py`
- `tests/test_swap_lock_platform_probe.py`
- `tests/test_trading_day_vs_data_arrival.py`
- `tests/test_worktree_closeout.py`
- `intelligence/tests/test_episode_semantic_verifier.py`
- `intelligence/tests/test_finance_query.py`
- `intelligence/tests/test_user_memory.py`
- `tests/test_main_gate_receipt.py`
- `intelligence/tests/test_llm_refine_tool_stream.py`

## 仍阻断的验收

PR10的原严格真实A/B问题没有被测试绿灯替代。后继PR11 d177的真实结果仍966/955/11、exit2；11份范围未批准。不能把它称为PR10原HEAD的全通过A/B，也没有在这里重跑旧缺陷脚本冒领exit0。PR10继续draft，未合并部署。

私有 `~/.finance-runtime/pr10-exact-sha-20261001/` 保存plan、日志、JUnit、start/result、失败协调器记录。
