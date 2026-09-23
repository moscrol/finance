# RE06 直接事务调用同族审查（consent 组，stage=explore）

- revision: `8eac9b3b55c563b1eb3be58686fcc0918464f69a`
- baseline: `b59d6eed0356ae093b52bd291ab328628de8790e`
- 方法：自写 AST 枚举器 `work/consent/ast_enum_transactions.py`（候选树静态解析），
  分母为本人独立得出，**未参考作者数量**；数量一致也不等于全仓无竞态。
- 机读版：`work/consent/transaction-review.json`（同 scope、同 18 条 entries）。

## 范围与分母

scope = `intelligence/services/research_evolution/*.py`（9 文件）+ `intelligence/api/research_evolution.py`。
直接 `transaction(...)` / `try_transaction(...)` 调用共 **18** 处：

| 分布 | 数量 |
|---|---|
| facade.py | 11 |
| pilot_io.py | 5 |
| run_observer.py | 1 |
| store.py | 1（infrastructure） |
| api/research_evolution.py | 0（全部委托 facade） |

按 kind：business 17、infrastructure 1（`store.py:203 _locked` 自保包装）。

## 涉及测量/授权的调用点（重点）

1. **`run_observer.py:218 _record` — try_transaction(0.2)**（C6 核心，唯一需要锁内复核的测量写入点）
   - 三类自动测量事件 `run_started` / `run_finished` / `cost_recorded` 全部经 `_record` 一个漏斗（run_observer.py:74-137）。
   - 顺序：锁外快筛 `_measurement_consented(now)`（run_observer.py:185）→ 门关闭直接 return，**不抢锁** →
     `try_transaction(timeout=0.2)` → 锁内 `_measurement_consented(now, store=txn)` 复核（run_observer.py:228）→
     `txn.append_product_value_event`。
   - `StoreLockTimeout` 仅 stderr 跳过，不阻断被测 run（run_observer.py:231-233）。
   - 锁内复核读的是 `txn`（同一 EvolutionStore，锁内读=提交时台账，store.py:137-151），窗口期撤回可被拦截。

2. **`facade.py:2070 _store_event` — transaction**（授权数据写入通道）
   - 前端撤回路径：API `post_events`（api/research_evolution.py:162）→ `ingest_events`（facade.py:1945）→
     `_store_event`（facade.py:1991）→ `store.transaction()` → `append_product_value_event`。
   - 与观察器同一把 owner 锁（同 lock 文件），是 TOCTOU 注释里「API 侧用户点撤回」的实际写入点。
   - 它写的就是同意记录本身，不需要同意门；无锁外快筛，无需锁内复核。

3. **`pilot_io.py:167 cmd_import_events` — transaction**（授权数据导入通道）
   - M 渠道批量导入可含 `consent_changed`；S2 模式：锁内整批对账、冲突零写入后再追加——自带锁内复核。

4. **`facade.py:1634 _select_task` — transaction**（边界观察）
   - 锁内直接 append 用户发起的 `task_selected` product_value 事件（facade.py:1665），
     注释明确「_store_event 会再开一把锁——非重入，自死锁」。
   - 用户发起事件**不走 I11 同意门**（门只管三类自动测量事件）。与主张一致，列为设计边界，不判缺陷。

## 其余 14 处（business，不涉及测量/授权，无需锁内复核）

- facade.py:727 `create_binding`、792 `_maintenance_action`、1799 `_reveal_exercise`、
  2084 `register_artifact`、2105 `record_process_receipt`、2117 `store_protocol`：
  锁内幂等/不可变登记，无锁外读决策。
- facade.py:1220 `fold_run_terminal`、1335 `bind_pending_rejudge_run`、1534 `pending_task_continuation`
  （均 try_transaction(0.5)）：维护折回/归属/continuation，锁内自带状态核验；有界等待不堵 run。
- pilot_io.py:94/114/124 `cmd_register`（protocol/assignment/policy-pack）、231 `cmd_rebuild`：
  CLI 登记与读侧产物重建；`cmd_rebuild` 中 `consent_changed` 仅作 summarize 输入。

## 结论（静态，未执行）

- 需要锁内复核的唯一点位（run_observer.py:218）复核**已存在**且读 `txn`；两条 consent_changed
  写入通道与其同锁族。静态层面未见「锁外读后锁内直接追加」的未防护同族调用。
- 本审查不签 C4-C6 PASS；行为正确性留 execute 阶段跑 `work/consent/probes/test_reviewer.py` 验证。
