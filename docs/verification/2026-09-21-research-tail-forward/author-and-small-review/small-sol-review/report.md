审核完成，结论为 **PASS**。两份合同均未发现 P0–P3 缺陷；未改源码、未合并、未部署、未联网查询金融数据。

## 规格审核

### 合同 1：API 测试 Timer 归属与生命周期

**PASS**

静态阅读：

- `intelligence/tests/fixtures/run_supervisor.py:28-33` 在测试提交任务前，把 supervisor 的 `_timers` 替换为 `_OwnedTimers`。
- `intelligence/tests/fixtures/run_supervisor.py:19-25` 即使 `_forget()` 从活动表移除 Timer，仍保留在 `owned` 列表。
- `intelligence/tests/fixtures/run_supervisor.py:45-56` 只取消并 join 当前 supervisor 所登记的 Timer，不扫描全局线程。
- 三个真实消费者均在提交任务前登记：
  - `intelligence/tests/test_api_credits.py:678`
  - `intelligence/tests/test_api_quota.py:129`
  - `intelligence/tests/test_api_run_admission.py:95`
- `intelligence/api/app.py` 未出现在候选增量中，生产 `RunSupervisor.shutdown()` 未被修改。

动态验证：

```text
umask 022; env -i PATH=/Users/a77/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin HOME=/Users/a77 FWP_TEST_RECEIPT=0 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_api_fixture_lifecycle.py tests/test_code_map.py intelligence/tests/test_api_quota.py intelligence/tests/test_api_credits.py intelligence/tests/test_api_run_admission.py
```

结果：

```text
105 passed, 1 skipped in 31.11s
```

新增生命周期测试实际验证了：Timer 已从 supervisor 活动表移除后仍被等待，且无关 Timer 不会阻塞 fixture 退出。

### 合同 2：code-map 原始查询、单次别名、失败分类

**PASS**

静态阅读：

- `scripts/code_map.py:517-525` 始终保留原问句，最多追加一次连字符到下划线别名。
- `scripts/code_map.py:567-590` 对两次查询结果做去重，并执行全局 `STRUCTURE_HIT_CAP` 限额。
- `scripts/code_map.py:528-539` 将非零退出、空响应、非法 JSON、缺失 `results` 明确分类为不可用；不会伪装成正常零命中。
- 正常 `status=ok, results=[]` 会继续返回正常无匹配；对应真实消费者是 `collect_query()`。

独立动态探针：

```text
umask 022; env -i PATH=/Users/a77/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin HOME=/Users/a77 FWP_TEST_RECEIPT=0 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-tail-integration-20260921/small-sol-review/independent_probe.py
```

结果：

```text
independent probes: PASS
```

探针覆盖：

- 原问句 `daily-full` 与别名 `daily_full` 均被发送；
- 结果去重且不超过总限额；
- 普通无匹配只发送一次；
- 后端非零失败返回 `search_failed`，不变成零命中成功；
- Timer 回调完成前 fixture 不退出；
- 无关 Timer 未被等待。

## 质量审核

**PASS，无独立质量缺陷。**

实际检查：

```text
.../.venv-workbench/bin/python -m ruff check \
  intelligence/tests/fixtures/run_supervisor.py \
  intelligence/tests/test_api_fixture_lifecycle.py \
  intelligence/tests/test_api_credits.py \
  intelligence/tests/test_api_quota.py \
  intelligence/tests/test_api_run_admission.py \
  scripts/code_map.py \
  tests/test_code_map.py
```

结果：

```text
All checks passed!
```

另行执行 `git diff --check`，无输出、通过。

## 未验证边界

- 未跑全量测试，只跑了本 PR 相关定向测试。
- 未调用真实 `code-review-graph` 后端；独立探针使用离线模拟响应，符合“不联网”要求。
- 未对 #798/#800 中未被本候选带入的领域代码作外推结论。
- 独立探针首次运行时脚本自身有一个分支错误，修正后重跑通过；该失败不是源码失败。

最终复核：

```text
HEAD:     ea5c3a94618a15e37f914c8b1a13e271875e4337
基线:     f783f19c8a01fbe8d0ed70d851df7ed14598c051
git status: clean
```

因此可以对固定提交 `ea5c3a94618a15e37f914c8b1a13e271875e4337` 签署这两项离线合同审核。