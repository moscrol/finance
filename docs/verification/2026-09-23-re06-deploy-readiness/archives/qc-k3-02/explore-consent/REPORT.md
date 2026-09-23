所有交付物已落盘并校验。审查完成，最终总结如下。

---

## 审查总结（K3 / explore / consent 组）

**范围**：C4-C6 + RE06 直接事务调用同族。只静态审查 + 写探针，未跑 pytest，未执行业务函数。`.git` 未触碰。

### 核心发现（静态结构层面）

**C4 共用折叠**：`scopes_at`/`measurement_scopes` 全仓仅 consent.py 一份（rg 确认 measure.py/run_observer.py 中 withdraw 只出现在 docstring 与排除原因串，无第二份排序键）。三处有意差异结构成立：读侧只要 `participant_id` 真值记录（measure.py:156）vs 写侧认 `participant_id in (None, owner)`（run_observer.py:162-163）；读侧无记录→None（measure.py:169-174）vs 写侧→自用默认 True（run_observer.py:170-171）；读侧坏时间戳 `event_time` 抛（events.py:85-89）vs 写侧跳过（run_observer.py:165-166）。

**C5 时间语义**：排序键 `(effective_at, action)` 字典序使同时刻 withdraw 后应用→净撤回（consent.py:70-78）；`effective > at` 截断未来记录；读侧以 `event_time(event)` 复核（measure.py:451、759）。

**C6 TOCTOU 门**：`_record` 锁外快筛（门闭直接 return 不争锁）→ `try_transaction(0.2)` → 锁内 `store=txn` 复核（run_observer.py:227-228）→ append；三类自动事件共用此漏斗；前端撤回经 `ingest_events→_store_event→store.transaction()`（facade.py:1991→2070）与观察器同锁族，窗口期撤回可被拦截——静态闭环成立。

**事务同族**：独立 AST 枚举分母 = **18** 处直接调用（facade 11 / pilot_io 5 / run_observer 1 / store 1 infrastructure；api 文件 0 处）。唯一需锁内复核的测量写入点（run_observer.py:218）复核已存在。逐项分类见 transaction-review.json/.md。

### 疑点（待 execute 核实，非结论）
- **S1**：consent.py 自述写侧坏时间戳「跳过并留 stderr」，但 run_observer.py:165-166 无 stderr——doc-vs-code 不符，且正是 consent.py 自警的「静默跳过 withdraw」场景；合法台账下或不可达。
- **S2**：`effective_at` 损坏时静默回退 `event_at` 而非跳过；**S3**：用户发起事件不走 I11 门（设计边界）；**S4**：`scopes` 为字符串时按字符成集（依赖上游校验）。

### 交付物（均已落盘）
- `probes/test_reviewer.py`：25 测试函数/27 用例，AST 解析通过，真实断言（乱序/同时刻撤回优先、未来不提前、事件自身时刻、锁外读后插入撤回被拦、门闭不抢锁、三类事件共门、读写差异边界）
- `probes/test_positive_control.py`：`assert 1 == 2`（expected_positive_control/probe_bug）
- `transaction-review.json` / `.md`、`ast_enum_transactions.py`、`EXPLORE.md`（含 execute 命令与未覆盖清单）

**未覆盖**：本场未执行任何测试；measure 全链路端到端、StoreLockTimeout 真实占锁、多进程 flock、cost_recorded 同意方向落账未探；C8-C10 不代签。探索交付 ≠ 候选 PASS。

```json
{"stage":"explore","group":"consent","revision":"8eac9b3b55c563b1eb3be58686fcc0918464f69a","baseline":"b59d6eed0356ae093b52bd291ab328628de8790e","complete":true,"artifacts":["/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/consent/probes/test_reviewer.py","/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/consent/probes/test_positive_control.py","/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/consent/transaction-review.json","/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/consent/transaction-review.md","/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/consent/ast_enum_transactions.py","/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/consent/EXPLORE.md"],"suspected_issues":["S1: consent.py docstring 自述写侧坏时间戳跳过并留 stderr，但 run_observer.py:165-166 的 continue 无 stderr（doc-vs-code；静默跳过 withdraw=已撤回当仍授权；合法台账下或不可达，待 execute 确认）","S2: effective_at 不可解析时静默回退 event_at（run_observer.py:164），与跳过语义不同，方向保守但无痕迹","S3: 用户发起 product_value 事件（facade.py:1665 task_selected、ingest_events）不走 I11 同意门——与 C6 表述一致的设计边界，记录待确认","S4: measurement_scopes 对字符串型 payload.scopes 会按字符成集（consent.py:42），依赖上游校验"],"limits":["本场只静态审查：探针仅经 AST 解析校验，未执行 pytest，无行为通过结论","measure_pair/_task_quality 读侧全链路未做端到端探针，仅到 _consent_timeline/_scopes_at 单元层","StoreLockTimeout 真实占锁路径与多进程 flock 竞态未覆盖","cost_recorded 同意后正常落账方向未探（撤回方向三类已覆盖）","C1-C3、C7-C10 属其他组，本组不代签；事务分母 18 为本人 AST 独立得出，数量一致不等于全仓无竞态"]}
```
