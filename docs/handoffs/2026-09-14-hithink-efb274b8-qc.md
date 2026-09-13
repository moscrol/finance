# hithink 十三轮修复独立 QC：efb274b8

## 裁定

**两处 P1 关闭，修复审查通过；尚不能直接签最新 main 的合并门禁。**
原因不是新增业务缺陷，而是最新主干已前移，组合代码态尚无本轮门禁收据。
本轮未合 main、未改候选/施工树、未切运行时、未打开生产数据库。

- 候选：`efb274b84e619234d93371cc09fb8166c66fc24e`。
- 修复：`b98441c5fcd55c808e4b21305ce0bcec0bbd2666`。
- fetch 后主干：`d7e5380551ba92758935d268fdd0e6fbfdd51ce8`。
- 候选共同基座：`e40f22b837178322169f47e565282450b4381a3a`。
- 独立审查树：`~/.finance-runtime/reviews/hithink-efb274b8-qc/tree`，分支 `docs/qc-hithink-efb274b8`；检查期间干净，之后才增加本审查文档和证据。

## 发现顺序与第一手验证

1. 默认主检出是其他任务的混合树，未动；候选 efb274b8 与施工 f40ee96d 实查均干净。
2. 核 b98441c5 仅改门禁及新增四条故障回归；b98441c5 到 efb274b8 仅交接与两份证据 JSON。
3. fetch gitea main 后发现主干独有 6 个提交（含 1 次合并），增量涉及 `scripts/moneyflow/write_to_duckdb.py`、`tests/test_moneyflow_server_aggregation.py` 和三份文档。不能把“两个分支分别绿”读作组合绿。
4. `git merge-tree --write-tree gitea/main efb274b8` exit 0；预测树对象 `0c89012edeb91f7ccb2f01cd7ce9129953a40658`。仅证明文本合并无冲突，没有更新 main 或创建合并提交。
5. 在独立干净 efb274b8 检出，全仓 Ruff exit 0；五组相关测试 **81 passed / 10.21s / exit 0**。解释器统一 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，测试环境 `env -i HOME="$HOME" PATH="$PATH"`、umask 022。
6. 从 `63f377da` 原样取出 `scripts/review_hithink_gate_faults.py`，在独立树真实运行：
   - output-base 指向普通文件：exit 1，stdout 有结构化 FAIL 与 REPORT_WRITTEN_TO，stderr 空，报告落 `/tmp/hithink-gate-report-*/gate-report.json`。
   - 真实未跟踪 marker + 临时损坏 GIT_INDEX_FILE：Git status exit 128、stdout 空；门禁 exit 1、failed=[git_invocation]，含 argv/rc/有界 stderr；无 tree_clean=true，未开始克隆/修复。没有损坏真实索引，marker 由 finally 删除。
7. 正常路径使用上轮审查的存档 before.duckdb + frozen parquet，不接触生产：绑定 efb274b8，**22/22 PASS、exit 0**；报告落本轮 `replay/run-mewhne9o/`。
8. 提交内 gate/child 报告逐字节等于原 `~/.finance-runtime/reconcile-gate/run-87sfiewb/`；脚本自哈希、冻结 parquet 哈希、before 哈希全部吻合。
9. 原全量收据 `20260913T160704Z-b98441c5.json` 核到 dirty=false、9612 passed、0 failed/error、77 skipped、exit 0。它证明 b98441c5；文档提交不改变被测代码，但不能外推覆盖最新 main 的 L2 组合。

相关测试命令：

```bash
<主树>/.venv-workbench/bin/python -m pytest -q \
  tests/test_reconcile_hithink_gate.py \
  tests/test_market_feature_store_staging_swap.py \
  tests/test_repair_hithink_stock_day.py \
  tests/test_sync_local_sector_members.py \
  tests/test_write_path_guard.py
```

## 证据与诚实边界

小证据随审查提交：`docs/handoffs/evidence/20260914-hithink-efb274b8-qc/`：
- `verification.json`：代码、主干、哈希链及裁定摘要。
- `fault-results.json`：两条真实故障的原始输出。
- `normal-replay.json`：独立正常重放。
- `full-python-receipt.json`：执行方 b98441c5 全量原收据。
- `targeted-python-receipt.json`：本轮 efb274b8 定向收据。

仓外原件根：`~/.finance-runtime/reviews/hithink-efb274b8-qc/`。
独立测试收据：`~/.finance-runtime/test-receipts/20260913T165041Z-efb274b8.json`。

本轮没有重跑全量 Python、frontend、E2E、registry。前端等原叶子记录绑 044d1661，本轮只是确认这些直接目录/脚本自该版本无差异，未对旧日志重新签发四叶通过结论。
正常重放里的 production_untouched 指显式 source-db（历史 before），不代表当前生产新鲜度。
未遍历所有存储/序列化/超时故障；不把此次两项闭环写成所有异常路径均经实测。

审查自身一次命令用了不存在的测试路径，pytest exit 4、no tests ran，失败收据 `20260913T164911Z-efb274b8.json` 保留；查上一轮原收据的真实 target 后才跑出 81p。该失败属于调用错误，不能算业务回归。
`check_test_receipt.py` 在 efb274b8 上校验 b98441c5 收据也会因当前 HEAD 不全等而拒绝；即使 --expect-revision=b98441c5 通过显式期望项，也不覆盖其内部当前 HEAD 检查。未把这次调用报作 exit 0。

## 决策与被否方案

| 方案 | 裁定与理由 |
|---|---|
| 两处 P1 修好就直接合最新 main | 否：文本无冲突不等于组合行为已经测试 |
| 主干前移，所以推翻 b98441c5 全量及数据收据 | 否：原件/哈希/独立重放仍支持它们在原代码态的结论 |
| 将代码审查通过与最新主干合并门禁分开 | 选：不重复退修已关闭问题，只补组合版本的四叶验证 |
| QC 顺手修改业务或执行生产换库 | 否：用户问可合并性，本轮保持只审边界 |

## 下一步

先在隔离候选纳入执行时最新 gitea/main（当前 d7e53805），在组合后的干净 revision 上跑齐 Python/frontend/E2E/registry 四叶；任一红或无结论不合。全部通过后再申请/执行用户明确授权的 main 合并。合入后批次与部署检查依验收规程，不拿分支收据冒充 main-tip 收据。

生产换库仍是单独授权事项，需按当时生产状态重新做隔离对账；302132 历史回填、并跑表补齐不在本次放行范围。
本轮复用既有 QC 探针与 receipt validator，没有新增通用工具，不另造同功能门禁。
