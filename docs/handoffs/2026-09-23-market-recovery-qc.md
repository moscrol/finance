# 2026-09-23 行情恢复独立质检：HOLD

## 结论与边界

本轮不放行 PR #861 / #871，也不执行新的恢复写入。发现三项可复现的实现问题；最新主线组合预览的定向检查还有两项纯主线同样可复现的沙箱失败。未取得最新组合树的全量绿色收据。

只新增本报告、交接、离线重现脚本和证据文件。没有修改业务实现，没有合并或推送 PR，没有创建数据库 staging、换库或写入生产事实表。负例中的 DELETE / INSERT 只作用于测试夹具创建的内存 DuckDB。

注意区分历史授权动作：#871 的交接记录了 2026-09-22 21:47、`run_id=92f6604e22f4` 的生产原子换库。本轮没有新增生产写入，不能把这句话扩大成“生产库从未写过”。

## 复核身份

| 对象 | 本轮检查身份 |
|---|---|
| PR #861 | `fix/market-recovery-contracts-0922@2df76ae9f7147619c0f6b9ec1faddf57d7a5b53a` |
| PR #871 | `fix/mootdx-history-0922@1d3324211118c15478e0995b484c463885dcf28c` |
| 最新主线 | `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb` |
| 最新组合预览 | `c57a4d019bd0bfa0a8f552590ec13f8ef4349de0`，tree `aa522049c76c8ed151b11a5c5fc79b7aebe520a8` |
| 预览工作树 | `/tmp/qc-market-recovery-ffd1b7f1`，检查时干净 |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` |
| 报告分支 | `docs/market-recovery-qc-0923`，工作树 `/tmp/qc-market-base-9a022798` |

Gitea `show` 回读两 PR 均为 `open / merged=false`。不要采信中途“#871 已合入”的错误表述。平台声称 `mergeable=true` 只供参考；本地 `merge-tree --write-tree` 返回 0、无冲突。预览提交通过 `commit-tree` 构造，没有移动 main 或任一被审分支。

## 发现

### F1 / P1：桥接步骤没有进入实际 local 夜跑计划

定位：`market_feature_store/sync/sync_daily_full.py:314`；`skills/daily-full-review/scripts/run_review_sync.py:386`。

#871 把 `bridge-stock-daily` 加在 `run_daily_update()`。本机夜跑包装器 `/Users/a77/.local/bin/nightly-review-sync-staged.py` 启动的却是 `run_review_sync.py`，其 `build_local_plan()` 没有调用桥。该计划的 `stock-daily` 只尝试东财快照和已有 sector-stock fallback；同花顺四步随后只写并跑表。

实测只构造计划、不执行动作，返回 20 个标签，无 `bridge-stock-daily`。因此主源及旧 fallback 失败、同花顺日线成功时，canonical `fact_stock_daily` 仍缺当天数据，下游拼接和派生无法被新桥救回。注册表校验为绿不构成反证，它核对的是已声明步骤，不证明预期的新兜底已接线。

修复验收：在真实 local 计划中覆盖“主源失败、同花顺成功”和“双源失败”两种路径；桥接应先于依赖 canonical 行情的拼接/派生。还须核对成功兜底如何处理前一来源的失败状态，不能只插入一个标签。

### F2 / P1：缺 canonical 行情仍报告完整覆盖，并重写错误统计

定位：`market_feature_store/sync/compute_local_stats.py:226`。

恢复路径传给 `sector_coverage()` 的 `observed_members` 来自 `fact_sector_stock_daily`，没有与当日 `fact_stock_daily` 的真实行情身份对账；涨停分子却来自后者。成分身份存在，并不能证明分子所需的行情还在。

内存复现：先得到某板块 `limit_up_count=2 / total_count=3`；保留成分身份，删除 `600001.SH` 的当日 canonical 行情，再传同一冻结名单执行。函数返回 `action=written`，把统计改成 `1 / 3`，却仍返回 `observed_bar_fraction=1.0` 和 `disposition_coverage_fraction=1.0`。

修复验收：在删除旧派生数据前，对冻结身份、成分投影、当日 canonical 行情、具名停牌逐一核对。缺行情不应被成分行证明为“已观察”。负例必须验证拒跑且保留原派生数据，而非仅检查分母数字。

### F3 / P2：过期计划绕过默认不覆盖策略

定位：`market_feature_store/sync/bridge_hithink_stock_daily.py:252`。

`build_bridge_day()` 在构造时检查已有行，但 `apply_bridge_day()` 不复核 `allow_replace_existing` 或目标日状态，进入事务后直接删除目标日全部行。事务保证同次写入原子性，不保证之前构造的计划仍符合当前状态。

内存复现：构造 `allow_replace_existing=false` 的三行计划；随后目标日加入三行 `close=99` 的 canonical 数据；应用旧计划仍成功，回执 `deleted_replaced=3`，价格全部改成计划中的 `10`。这证明默认策略在构造与执行分离时可被绕过；本轮没有声称该场景已在生产发生。

修复验收：执行事务内复核覆盖授权与目标日状态，对过期计划明确拒绝；新增“构造后插入已有行”和“重复应用默认计划”的测试。若允许计划长期保存，还应明确输入指纹的有效期和复核责任。

## 不能当作已完成的合同

- `compute-limit-stats-local` 的 CLI 只传 `trade_date / force / min_boards`，未传 `recovery_members / recovery_nontrading`。本轮用 mock 拦截调用验证，未访问数据库。这是恢复合同尚未接入运行入口的边界，不另报为违反当前默认行为的代码缺陷。
- `sector_coverage()` 接受的是调用方已验证的停牌身份集合，对各板块取交集。只凭“不属于任何板块的停牌身份被忽略”，不足以单独认定缺陷；全市场范围校验责任仍须在入口合同里说清。
- mootdx 开工前健康探针失败不写行情；运行中连续失败达到熔断阈值时，源码明确先 flush 有效行再抛错。这是可续跑设计，不能宣传为全程零部分写入。
- `daily-full` 的互斥锁与原子换库保护，不能自动推广到本机另一个 nightly 包装器。此轮没有部署或实跑夜间写入流程，也未验收其完整并发行为。
- 5553/5565 范围、两只分红金额差异、53 只除权/送转拒写、名称未验证与换手率 NULL 等仍按既有决策页等待确认。F1 修复不构成扩大恢复范围或写派生表的授权。

## 验证与收据

所有归档产物见 [质检证据目录](../verification/2026-09-23-market-recovery-qc/)。

最新 `ffd1b7f1` 组合预览上的检查：

| 检查 | 结果 |
|---|---|
| `python -m ruff check .` | 通过，见 `ruff.txt` |
| `python -m market_feature_store.cli registry-check` | 通过，见 `consumption-registry.txt` |
| `python scripts/build_registry.py check` | 本仓通过；日志明确跨仓缺席项跳过，见 `registry-source.txt` |
| `python scripts/build_registry.py check-parseability` | 39 个 SKILL.md 可解析，见 `registry-parseability.txt` |
| 恢复相关 9 个测试文件 + 两个沙箱参数化用例 | `231 passed / 2 failed`，退出码 1，见 `targeted-receipt.json` |
| `check_test_receipt.py --expect-revision c57a4d019bd0 --base-drift-max 5` | 身份可采信、漂移 0；这不表示失败测试变绿，见 `targeted-receipt-check.txt` |
| `main_gate_receipt.py` 校验同一收据 | 退出码 1，列出两条 RED |
| 负例重现脚本 | 三项问题均复现；另确认 CLI 参数边界，见 `probes.json` |

两项失败都是 `intelligence/tests/test_codex_headless_runtime.py::test_installed_codex_sandbox_denies_network_and_unix_socket[False/True]`，断言期望 `proven`、实得 `unproven`。在纯主线 `9a022798` 的干净树单独复跑也同红，见 `baseline-sandbox-receipt.json`。该基线到最新主线只改了三个文档文件。因此可确认它们并非只在本 PR 组合中出现；此轮没有进一步定位沙箱失败根因，也不以“主线同红”为放行理由。

全量结果边界：旧基线 `9a022798` 的组合预览 `17605385d4b2` 曾执行 `pytest -q --tb=short`。主线随后前移；最新预览已经获得明确红灯及复现问题，故结束旧任务，最后进度约 69%。SIGINT 未结束后台任务，随后仅对本轮已确认的 pytest PID 60925 发 SIGTERM；已确认该进程及包装进程均退出、停止前无子进程。`full-interrupted.txt` 仅是中断进度，不是完整失败列表或全量收据。最新预览没有全量通过结论。

前端/E2E 不适用：两 PR 的变更文件均未触及 `intelligence/webapp`。这不是“执行并通过”。

重现命令，必须在包含两 PR 的预览树执行：

```bash
cd /tmp/qc-market-recovery-ffd1b7f1
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  /tmp/qc-market-base-9a022798/scripts/qc_market_recovery_contracts.py
```

脚本断言的是当前缺陷仍存在，退出 0 代表重现成功，绝不代表业务验收通过。修复后应把相应负例转成期望拒绝的正式回归测试；本脚本依赖这次测试夹具，不注册为长期门禁。

## 生产只读回读

本轮使用既有 `readback_before.py`，显式指向 `/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`，通过 `duckdb.connect(..., read_only=True)` 扫描 36 张带 `trade_date` 的事实表/视图。时间、文件信息与每表结果见 `production-readback.json`。

- `fact_stock_daily`：09-21 / 09-22 各 5551 行，来源 `hithink:daily-k-10d`。
- `fact_market_daily`：09-21 仍缺行；09-22 有一行，不据此声称字段齐全。
- 13 张逻辑本地派生表停在 09-18，generation 物理表不重复计入此数。
- theme flow 停在 09-15；七张复盘会相关表停在 09-02。

这是行数与日期回读，不替代重要字段非空审计，也不重新证明冻结范围的官方历史真实性。

## 决策与后续

| 方案 | 结论与理由 |
|---|---|
| 凭 PR 旧收据及平台 mergeable 放行 | 否：缺少当前组合树完整门禁，而且三项行为缺陷已复现 |
| 本轮直接修复并恢复生产 | 否：授权是独立 QC；合同与恢复范围未确认 |
| 继续跑完已漂移基线的全量任务 | 否：最新预览已有红灯，旧任务不能替代最新准入收据 |
| 报告缺陷、保留离线负例、维持 HOLD | 采用：给实现者明确复现与验收条件，不越过用户决策 |

下一轮先确认合同及恢复范围，再修复 F1/F2/F3 并补正式回归测试。修复后从届时最新 `gitea/main` 构造干净组合预览，重跑完整 Python、Ruff、registry 及适用门禁，取得有效绿色收据；沙箱红灯也必须处理或按项目规则正式裁决。任何合并、推送、staging、换库或派生表写入仍需相应明确授权。

沉淀范围：诊断脚本已进入 `scripts/`，不只留在 /tmp；没有修改运行时门禁，因为这是审查而非修复授权。原子性不等于计划新鲜度、成分身份不等于行情存在这两个原则可迁移，但本轮不新建重复的方法论清单，也不改跨仓 harness。
