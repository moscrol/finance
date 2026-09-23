# EXPLORE — K3 consent 组（C4-C6 + RE06 事务同族）

- stage: explore（只静态审查 + 写探针，**未跑 pytest**，未执行业务函数冒烟）
- revision: `8eac9b3b55c563b1eb3be58686fcc0918464f69a`
- baseline: `b59d6eed0356ae093b52bd291ab328628de8790e`
- 候选树（只读）: `…/qc-k3-02/candidate/finance-workspace-private`
- `.git` 明确不可读，未使用任何 git 命令；revision 按任务给定采信。
- 本组只审 C4-C6 与事务同族；C1-C3、C7-C10 由其他组审，本文件不代签。

## 交付物

| 文件 | 内容 |
|---|---|
| `work/consent/probes/test_reviewer.py` | 自造探针 25 个测试函数/27 用例（C5 折叠/时间 9、共用折叠助手 5+covers 1、C4 差异边界 5、C6 门控/TOCTOU 5 函数含参数化） |
| `work/consent/probes/test_positive_control.py` | 正控 `assert 1 == 2`，下一会话单独运行记 `expected_positive_control/probe_bug` |
| `work/consent/ast_enum_transactions.py` | 自写 AST 枚举器（独立分母来源） |
| `work/consent/transaction-review.json` / `.md` | 18 处直接 transaction/try_transaction 调用逐项分类 |

## 关键源码行（已核）

### C5 — 折叠与时间语义（consent.py）
- `scopes_at` 排序键 `(effective_at, action)`：consent.py:70-78。同时刻 `"grant" < "withdraw"`（字典序），
  撤回后应用 → 净效果撤回（保守方向）✓ 结构成立。
- `if effective > at: break`（consent.py:72-73）：未来生效记录不提前作用；`effective == at` 含边界 ✓。
- 空输入返回空集且 docstring 明确「空集 ≠ 没有记录」（consent.py:66-67）✓。
- 读侧以事件自身时刻复核：measure.py:451 ` _scopes_at(consent, participant, event_time(event))`、
  measure.py:759 同模式 ✓。

### C4 — 共用折叠 + 三处有意差异
- 共用：measure.py:27 与 run_observer.py:151-153 都 import 同一份 `scopes_at`/`measurement_scopes`，
  两侧无第二份排序键 ✓。
- 差异 1 参与者过滤：读侧 measure.py:156 只要 `participant_id` 真值的试点记录；写侧
  run_observer.py:162-163 只认 `participant_id in (None, owner)` ✓ 方向相反、各自留在调用点。
- 差异 2 无记录：读侧 `_scopes_at` 返回 None（measure.py:169-174，记 limitation/排除）；
  写侧 `if not entries: return True`（run_observer.py:170-171，自用默认）✓。
- 差异 3 坏时间戳：读侧 `event_time` 抛 ValueError（events.py:85-89，measure.py:159 调用）；
  写侧 `if effective is None: continue`（run_observer.py:165-166）跳过 ✓ 行为差异成立，但见疑点 S1。

### C6 — 同意门 TOCTOU（run_observer.py `_record`，176-233）
- 锁外快筛：run_observer.py:185-188，门关闭直接 return，**不进 try_transaction**（不争锁）✓。
- 有界事务：`try_transaction(timeout=0.2)`（run_observer.py:218）；`StoreLockTimeout` 只 stderr 跳过
  （run_observer.py:231-232），不阻断被测 run ✓。
- 锁内复核：run_observer.py:227-228 `self._measurement_consented(now, store=txn)`，读 `txn`（同一
  EvolutionStore，锁内读=提交时台账，store.py:137-151 合同）✓；时间语义不变，仍用事件自身 `now`。
- 三类自动测量事件共用此门：`create_run`→run_started、`claim_terminal_run`/`claim_failed_run`→
  run_finished + cost_recorded，全部汇到 `_record`（run_observer.py:74-137）✓。
- 撤回写入对端：前端撤回经 API `post_events`（api/research_evolution.py:162-174）→
  `ingest_events`（facade.py:1945）→ `_store_event`（facade.py:1991→2070）→ `store.transaction()`，
  与观察器同一把 owner 锁 → 窗口期撤回可被锁内复核读到 ✓ 静态闭环。

### 事务同族（独立 AST 分母 = 18，未抄作者数量）
- business 17 / infrastructure 1（store.py:203 `_locked` 自保包装）。
- 唯一「涉及测量/授权且需要锁内复核」的点：run_observer.py:218，复核已存在。
- 授权数据写入通道两处：facade.py:2070（前端撤回）、pilot_io.py:167（M 渠道导入，S2 锁内整批对账）。
- api/research_evolution.py 0 处直接调用（全委托 facade）。
- 详见 `transaction-review.md` / `.json`。**数量一致不等于全仓无竞态**；本结论仅限此 scope 的静态结构。

## 疑点（suspected issues，待 execute 核实，均非 PASS/否决结论）

- **S1（doc-vs-code，安全相关）**：consent.py 模块 docstring 自述写侧坏时间戳「跳过该条**并留 stderr**」，
  但 run_observer.py:165-166 的 `continue` 无任何 stderr。静默跳过一条 `withdraw` 正是 consent.py
  自己警告的「把已撤回当成仍授权」。可达性存疑：台账事件经 05 校验后 `event_at` 应恒可解析，
  `effective_at` 又有 `or parse_ts(event_at)` 兜底（run_observer.py:164），该分支对合法台账可能不可达；
  但手工改账/坏行场景下无痕迹。建议 execute 阶段确认可达性并决定是补 stderr 还是改文档。
- **S2（语义边界）**：`effective_at` 存在但不可解析时静默回退 `event_at`（run_observer.py:164），
  一条生效时间损坏的 withdraw 会按 `event_at` 折叠而非被跳过——与「跳过」语义不同，方向仍保守
  （撤回更早生效），但值得记录。
- **S3（设计边界，非缺陷）**：用户发起的 product_value 事件（facade.py:1665 `task_selected`、
  ingest_events 前端事件）不走 I11 同意门；门只管三类自动测量事件。与 C6 表述一致，列为边界观察。
- **S4（输入契约）**：`measurement_scopes` 对 `payload.scopes` 为字符串时会按字符成集
  （consent.py:42），依赖上游校验保证 list；台账内记录已过校验，风险低，仅记录。

## 下一场（execute）命令

```bash
# 自造探针（本组）
cd /Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02
CANDIDATE_ROOT=$PWD/candidate/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  work/consent/probes/test_reviewer.py -q

# 正控（必须失败，记 expected_positive_control/probe_bug）
CANDIDATE_ROOT=$PWD/candidate/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  work/consent/probes/test_positive_control.py -q

# 作者测试（学 API 用，不作本组证据；路径相对候选 intelligence/）
cd candidate/finance-workspace-private && \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_re06_consent_fold_shared.py \
  intelligence/tests/test_re06_consent_gate_toctou.py \
  intelligence/tests/test_research_evolution_i11_consent.py -q
```

## 未覆盖边界（诚实清单）

1. 本场未执行任何测试：探针只经 AST 解析校验语法，行为断言全部待 execute。
2. 读侧 measure 全链路（`measure_pair`/`_task_quality` 在 event_time 的排除，measure.py:451/759）
   未做端到端探针，只到 `_consent_timeline`/`_scopes_at` 单元层。
3. `StoreLockTimeout` 真实占锁路径未造探针（需另一进程/线程持锁的 fixture）。
4. cost_recorded 的「同意后正常落账」方向未探（05 校验严格度未全核）；三类事件的撤回方向已覆盖。
5. 多进程 flock 竞态未覆盖（探针均单进程；文件锁语义只静态核对了 store.py:153-198）。
6. C8-C10（activity-timer 门、legacy alias 细节、撤回不被重计时覆盖）属其他组主张；
   本组探针里 `measurement_scopes` 用例仅作共用折叠助手契约，不签 C8-C10。
7. S1/S2 的可达性（坏时间戳行能否进入已校验台账）未证实。
