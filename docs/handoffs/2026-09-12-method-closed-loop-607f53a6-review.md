# method-closed-loop · 607f53a6 独立质检

日期：2026-09-12。结论：**不放行；有可复现代码缺陷，不只是缺全量绿单。**

## 对象与隔离

- 被测提交：`607f53a65abae17026ea8cf72b2a8c8bddc5a707`，包含 `a7aa227d`、`dd7b6f74`、`22c60030`、`607f53a6`。不能拿冻结在 dd7b6f74 的全量验后两笔夜跑修复。
- 独立树：`/tmp/method-qc-607f53a6-review`，由该提交 detached 检出；两次定向 pytest 时干净；之后才创建 `docs/qc-method-607f53a6` 留本报告。
- 原分支 `/Users/a77/fwp-wt-closed-loop` 未改。主检出脏树未改。未推送、合并、生产部署、迁移、重建共享库，也未启动整树全量或停止其他进程。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- 临时证据：`/tmp/method-qc-607f53a6-evidence/` 的 `probe.py`、`results.json`、`consumer_probe.py`、`consumer-results.json`、两份 pytest 日志。保留原路径便于本机复核；临时文件不是永久归档，关键反例另记在下文。
- consumer 探针逐字截取仓内绑定段和 `run_method_flywheel`，仅把 daily 的真正执行改成写本地调用记录、notify 改成本地告警记录；active 是真实 CLI。没有执行市场复盘或真实数据写入。首次 spy 用 zsh，受到宿主 `.zshenv` 覆盖隔离 users 根的污染，结果废弃；改 bash spy 后重新跑出的结果才采信。绑定段自身仍由 zsh 执行。

## 发现（按严重度）

### 1. P1：坏指针仍可变成 exit 1，被当成「从未配置」，无告警跑回默认协议

位置：`intelligence/services/method_validation/store.py:264-270`；`scripts/method_validation.py:677-681`；`skills/daily-full-review/scripts/nightly_full_review.sh:75`。

复现：在临时用户根登记并 activate 有效协议，再把 `active.json` 写成 `[]` 或 `null`。

```text
active --root <临时根> --print-dir → rc=1（AttributeError traceback）
nightly 真实绑定段 → METHOD_BINDING_ERROR 为空、METHOD_STUDY_DIR=475597e2…
run_method_flywheel（daily spy）→ DAILY_CALLED 默认协议，NOTIFY=0
```

原因：`json.loads` 成功不等于对象结构正确。随后 `doc.get` 抛 AttributeError，main 未捕获，Python 进程退出 1，刚好撞上为「unset」保留的业务码。stderr 有 traceback 不等于守卫停下——它只看 rc。

另两个同结果反例：`active.json` 是目录、或是悬空软链。`not pointer.is_file()` 把「路径在但形态坏了」直接判 unset。

要求：只对确实不存在的指针给 unset；有路径但读不出/非对象/结构不合法均为失效。并让业务上的「未配置」不能与进程崩溃混用一个无额外验证的信号（结构化结果或更合适的专用退出码均可）。真实 shell 回归须断言**没调用 daily 且产生告警**，不只断言源码里有 case 分支。

### 2. P2：能力探针失败仍冒充「旧 CLI 无 active」

位置：`skills/daily-full-review/scripts/nightly_full_review.sh:64-86`。

`CLI --help | grep` 的 false 有两种来源：help 正常输出且无命令；help 进程自己失败。当前都进同一个 else，输出「CLI 没有 active 子命令（链切未做）」并回退默认，原始 stderr 被管道吃掉。

故障注入：已有有效 active 的临时用户根；解释器 spy 仅令 `--help` 打印 `RuntimeError: transient startup failure` 并 exit 1，其他命令照常。

```text
METHOD_BINDING_ERROR 为空
日志：CLI 没有 active 子命令（链切未做）
run_method_flywheel → DAILY_CALLED 475597e2…，NOTIFY=0
```

这是「查询失败」被当成「能力不存在」，和上轮批评的假诊断是同一形状。只在 help **成功**且确无 active 时允许兼容默认；help 非零/异常输出应保留原因、停掉方法日步。不要把这两种状态继续压成 grep 的一个布尔值。

对真正旧快照 `~/.finance-runtime/finance-workspace-2efdff46e251` 的 help-only 检查和绑定检查，兼容回退符合当前设计；本项不要求删除旧版兼容。

### 3. P2：同一 active 指针的两种输出模式给出不同有效性结论

位置：`intelligence/services/method_validation/store.py:274-281`；`scripts/method_validation.py:575-582`。

先登记 activate，然后把目标 `protocol.json` 写坏：

```text
active --print-dir → rc=0，输出目录（夜跑实际用此入口）
active             → rc=2，invalid JSON record
```

`active_binding` 只检查 protocol.json 文件存在，没有校验协议封套；JSON 输出模式才额外 load_protocol，而 print-dir 提前返回。日步稍后仍会被 load_protocol 拒绝，所以本项没有实测出错误观察写入，但「有效绑定」和诊断入口已经分裂。

要求：两种展示模式共用同一份绑定验证；损坏目标明确报失效。无需在这里新增「当前库版本」或未来样本可用性门，验证磁盘协议完整性与业务可运行性是不同范围。

### 4. P2：迁移核对表仍不可逐行执行；链切说明有漂移

位置：`docs/superpowers/specs/2026-09-12-label-version-migration-plan.md:155-158,177-189`。

| 文档原命令/陈述 | 本轮实测/核对 |
|---|---|
| `status --user "$U"` 列出协议 | rc=2；status 必须 `--study-dir`，且根本没有 `--user` 参数 |
| `capture --study-dir <v3目录>` 应报封存 | rc=2 但原因是缺 `--labels-db`；没有到封存闸，不能拿「非零」作验收 |
| `"$CODE_ROOT/scripts/method_validation.py" activate --help` | 冻结检出该文件 mode=100644，无执行位；直接调用 Permission denied。要用已核对的 OPS_PYTHON |
| 第二个「§4.1 执行④之前」 | §4.1 重号；主表④已经是 history，activate 是⑤。新代码准备若也是 history 前提，应明确写全，不保留旧步骤号 |
| §3.3 仍写封存后非零会回退默认 | 与新三态合同相反，应写停止并告警（无指针是另一分支） |

建议核对命令（变量以执行时显式确认的临时/生产路径为准）：

```bash
"$OPS_PYTHON" "$CODE_ROOT/scripts/method_validation.py" status --study-dir "$NEW_STUDY_DIR" --json
"$OPS_PYTHON" "$CODE_ROOT/scripts/method_validation.py" capture --study-dir "$OLD_STUDY_DIR" --labels-db "$LABELS_DB" --user "$U"
```

此外，`607f53a6` 提交说明、nightly:62-63 与 test_method_flywheel.py:728-729 声称「旧 CLI 的 active --help 也返回 0，argparse 不校验子命令」不成立。本轮正确解释器对真实旧快照实跑：

```text
--help          → 0
active --help   → 2，invalid choice: active
activate --help → 2，invalid choice: activate
```

顶层帮助探针可以保留，但不能用错误的 argparse 原理为它背书。

## 本轮认可的修复与边界

- 已封存协议在真实 `capture` / `daily` CLI 上均 rc=2，原因是「协议已封存」；临时协议树新增文件 0。传不存在的主库/旁路库仍先报封存，证明确在访问数据/写入前拒绝。
- 未配置→默认；有效指针→新协议；普通非法 JSON 和已封存目标→rc=3，真实方法步不调用 daily 且记录告警。这些原反例已经收住，不能因为新边界失败就把它们说成没修。
- 跨 root 拒绝、resolve 归一化、同意图封存不刷新时刻：现有回归通过。
- recheck 入口没有加入封存闸；本轮没有新增「封存且有存量待验」的端到端试验，不给额外结算保证。
- `report --labels-db` 确实读库的 meta；history 重跑已在主执行表独立列出。
- 收据发布/证伪库模块现有 87 项回归通过；本轮未新加进程崩溃或断电模型探针。

## 验证证据

在干净冻结代码上：

1. `pytest -q intelligence/tests/test_method_validation.py intelligence/tests/test_method_validation_cli.py intelligence/tests/test_method_flywheel.py` → **78 passed / 18.67s**。
2. `pytest -q intelligence/tests/test_methodology_backtest.py` → **87 passed / 27.16s**。
3. 改动相关 Python 的 ruff 与 nightly 的 `zsh -n` 通过。

这是两次**定向**测试共 165 项通过，不是全量通过。对应收据：

- `~/.finance-runtime/test-receipts/20260912T094532Z-607f53a6.json`
- `~/.finance-runtime/test-receipts/20260912T094701Z-607f53a6.json`

## 对原汇报的证据质检

已读取两次全量收据，数字属实：

- `20260912T091157Z-dd7b6f74.json`：源树 9429P/1F，failed id 是 method_backtest CLI/refuted 用例。结束时 dirty=false **不能证明运行期间没变过**；与中途 dd7b6f74 落下的描述相容，不采信为固定 revision 全量。
- `20260912T093817Z-dd7b6f74.json`：冻结树 9430P/3F，exit=1。
- `20260912T093845Z-dd7b6f74.json`：上面三项定向重跑 3P/0F。

「三条都是真实墙钟等待 wait(timeout=2)/wait(timeout=1)」不准确：

| 冻结全量失败项 | 源码实际时序 |
|---|---|
| conversation_orchestrator::test_ask_watchdog_returns_partial_and_suppresses_late_progress | 有 wait(2)/wait(1) |
| episode_semantic_verifier::test_late_malformed_final_rejudge_remains_fail_closed | 20ms 总 deadline + sleep(30ms)，不是上述 wait |
| workbench_conversation_integration::test_real_conversation_round_trip_persists_skills_sse_and_three_turns | 10s 轮询终态并 sleep(20ms)，不是上述 wait |

三项确实涉及真实时钟，但**高负载只支持环境干扰假设，不证明三个失败均仅由负载导致**。需失败 traceback 与断言逐项对账。保留红单，不以定向绿改判全量绿。本轮没有拿到原 14:22/24:48 的完整日志，不独立认证耗时数字。

本轮 17:42 观察 load average=10.03/22.32/36.30，两个 pytest 仍高 CPU；后续 lsof 识别其 cwd 分别为 `fwp-wt-verify-dd7b6f74` 与 `agroup-build/finance-workspace-private`。这证明机器仍存在争用，但**不能仅凭进程信息把两者都归为同一任务的两个会话**。

## 交接与调度建议（未替用户实施）

原 inflight 文件 **20279 字节**，远超 ≤3KB，并且头部仍是第五轮待复验，未包含 22c60030/607f53a6 后的完整状态。不是本轮无权代写的聊天归属问题，而是下一位会被注入过时信息的实际风险。原分支单一写入者应把历史压入日期快照、在途只留当前阻塞。

建议选一个明确收口人（可选原汇报的 a），但须另一会话明确确认停止该分支写入；审查方独立树只读，不代改。顺序：先修本报告缺陷与真实 shell 行为回归→固定最终提交→确认整机静默窗口→一位执行者跑整树等价检查。若仍红，保留原始日志按断言定位，不以重跑绿覆盖。没有调度授权，本轮不 kill 其他任务。

本轮只做语义质检和局部故障注入，不把临时按提交定制的 spy 宣传为通用门禁；正式可复用回归应由收口人加在现有测试中，且覆盖「正常/确无能力/探针失败/坏结构」分母，而非继续加源码字符串断言。
