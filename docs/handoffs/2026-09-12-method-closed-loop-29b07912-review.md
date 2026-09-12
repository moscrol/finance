# 29b07912 独立质检：测试数字成立，尚不建议合入

## 范围与裁决

被审对象：`feat/method-closed-loop@29b0791269a22f85c13ebbe3e243f807be2ae178`（第四轮实现 `5d000c3e`）。独立检出：`/Users/a77/fwp-wt-qc-method-29b07912`，报告分支 `docs/qc-method-29b07912`。

**暂不放行：1 条 P1 写入发布缺陷，2 条 P2 迁移/交接执行缺口。** 第四轮原反例的针对性修复成立，但不能扩大为“写入层全部收敛、迁移可执行”。另有 1 条条件性读取遗留，明确不计为第四轮新引入。

本会话接续被中断的质检：开工时两份聊天中的报告草稿均未落盘，复现脚本、日志、全量收据已保留。本文件是唯一正式报告。未修改被审实现、源分支交接或迁移方案；未读写生产数据库、未执行生产迁移、未切夜跑/Workbench 运行时、未合并或推送。

## 已验证：绿是真的，覆盖范围也要说清

- 前会话全量 pytest 收据：**9422 passed / 0 failed / 77 skipped，exit 0**，解释器为主树 `.venv-workbench/bin/python`（Python 3.12.13），被测 revision 精确为上述完整 SHA，`dirty=false`、依赖门未绕过。归档副本与原收据逐字节相同。本会话核对并采信，**没有冒称重新跑过全量**。
- 本会话在同一干净 revision 重跑第四轮新增的 5 项回归：**5 passed / 0 failed**。包含强制同名不同内容并发、scan 防覆盖、JSON 成功/Markdown 创建失败后的修复重试、混合时间戳、Workbench 不串规则版本。
- 重放原质检脚本的 4 组探针，全部复现；普通 `cmd_report` 的正对照确实取到 `.500000+00:00` 那份。现有 `test_mixed_timestamp_forms_order_consistently` 实际断言 `latest_receipt` / `load_steps`，普通 report 的直接断言来自这个额外探针，不能只凭测试名说入口已覆盖。
- `forward_start` 已改为登记时计算 `max(重建日, 登记日)` 的下一交易日；工单已清除旧版“用 v3 备份结算剩余对象”的指令。两条按文档与实现核对，未执行共享库操作。
- 本报告不签发 Ruff、前端、浏览器端到端或注册表门禁的合入证明；Python 全量绿不是“所有合入叶子全绿”。

## 发现（沿前会话的发现顺序）

### 1. P1：原子占名不等于完整内容原子发布

定位：`intelligence/services/methodology_backtest/receipts.py:466-505`（`_write_exclusive`），调用点为 `write_receipt`、`write_refuted`、`write_scan_summary`；读取端 `lifecycle.py:177-195`、`receipts.py::latest_receipt` 跳过坏 JSON。

`os.open(..., O_CREAT | O_EXCL)` 保证“不存在才创建”，但**正式文件名立即可见，内容在随后 `fdopen` / `write` 才写入**。`except BaseException` 能处理普通异常，不能保证进程直接退出后仍执行清理。

实测两个互补场景：

1. 让第一写手在 `os.open` 成功、`fdopen` 前暂停：正式 JSON 已可见，大小 **0 字节**；第二写手提交**完全相同内容**，得到 `ReceiptCollision`，不是幂等成功。原并发回归只要求“不同内容强制同名时一成功一拒绝”，没有压到这一窗口。
2. 子进程在同一位置 `os._exit(73)`（真实进程终止，不是可捕获 Python 异常）：正式目录留下 **0 字节 JSON**；原内容重试仍被 `ReceiptCollision` 拒绝。先建立 supported 三阶段链，再这样中断一份 refuted 写入，`load_steps` 静默跳过坏文件，派生状态仍为 **`personal_method`**。

**影响边界**：探针不是“已经成功提交的反证被删除”，而是“失败写入在正式命名空间留下不可读对象，重试被卡住，读取端没有损坏告警而继续给出旧状态”。文件写入函数不满足其完整发布/可恢复重试的承诺；同一 helper 的三个写入口都需修复并各自覆盖。

建议验收：

- 在正式目录之外的临时文件写完并同步后，才无覆盖地发布正式名称；相同内容并发重试成功，不同内容碰撞仍拒绝。
- 已有可复用实现参考：`intelligence/services/method_validation/store.py:35-58::_publish`，采用同目录临时文件、`flush/fsync`、`os.link` 无覆盖发布和目录同步。这里只建议评估复用，不假设 JSON 专用实现可直接原样处理 Markdown。
- 不要直接换成 `os.replace`：它会覆盖已有目标，重新破坏“失败证据不可覆盖”的合同。
- 补进程终止、读写交错、同内容并发、JSON/Markdown 分步失败的恢复测试。明确旧坏文件的告警/恢复策略，不凭文件名推断其结论，不自动覆盖或删掉真实证据。

### 2. P2：迁移只有登记新协议，没有切换消费者；封存标记也没有运行语义

定位：迁移方案 `docs/superpowers/specs/2026-09-12-label-version-migration-plan.md:63-99`；夜跑 `skills/daily-full-review/scripts/nightly_full_review.sh:43,209-215`；注册入口 `scripts/method_validation.py:115-136`。

- 夜跑的 `METHOD_STUDY_DIR` 默认固定为旧协议 `475597e2…`，实际调用显式传 `--study-dir "$METHOD_STUDY_DIR"`。
- `register` 只落新协议并打印 id/目录；它不改夜跑绑定。迁移正文没有更新 `METHOD_STUDY_DIR`、验证有效运行快照与新协议版本匹配、或验证下一次日步实际选中新协议的步骤。**在没有额外环境覆盖/人工切换的情况下，照方案登记完成后夜跑仍选旧协议。** 本轮没有读取生产启动环境，不声称线上已执行迁移或必然不存在覆盖。
- “旧协议写一条 superseded”目前不足以实现运行态封存：`store.py:13,114-116` 只接受 `history/capture/recheck`，`write_record(..., "superseded", ...)` 实测报 `invalid record kind`。
- 若改为手写 `superseded.json`，隔离实测：`list_studies` 仍枚举旧目录；`flywheel.fingerprint` 不变；此前的 standing 摘要仍返回 `fresh=True`。它最多是人工备忘，不是停用开关，也不能防止消费者继续按旧摘要工作。

建议验收：把迁移补到消费者切换——明确旧协议如何留档但退出活跃消费、新协议实际绑定由谁修改、暂停/恢复边界在哪里；逐项验证夜跑选中的 study id、代码版本、库版本和下一次 capture。若暂时只用人工封存记录，必须明确它不具备机器停用能力，并提供真正的停用/切换动作，不能继续把写标记当作完成封存。

### 3. P2：交接放行了依赖合入的共享库重建

定位：`docs/handoffs/inflight/feat-method-closed-loop.md:138` 对比迁移方案 `§4`（第 99 行）。

- 迁移正文：**①② 不依赖 #49 合入；③④⑤ 依赖**。
- 源分支交接“下一步”：**①②③ 不依赖本单合入**。
- 第③步恰好是**共享库重建到 v5**。这不是排版问题：接手者按交接会在实现尚未合入/部署时先改共享数据口径。交接正文前一节还正确写着“①②”，同一文件内部也矛盾。

建议验收：源分支交接删掉“已全部收敛、等合入”的无条件裁决；执行顺序以迁移方案为唯一来源，避免再次复述出另一套编号。修正文档不等于获准执行共享库写操作，仍需用户逐步确认。

### 4. 条件性遗留：`report --refuted` 仍按时间戳字符串取最新

定位：`receipts.py:599-626::load_refuted/summarize_refuted_by_stage`；入口 `scripts/methodology_backtest.py:451-454`。

同规则两份证伪条目分别为 `2026-09-12T12:00:00Z` 与 `2026-09-12T12:00:00.500000+00:00`，后者实际更晚；`load_refuted` 却将前者排第一，阶段汇总 `setdefault(rule_ref, entry)` 因而采用旧条目。普通 report 已按解析后的时刻比较，正对照通过。

**归属严格限定**：字符串排序这一行的 `git blame` 指向 `e520e31e0`（2026-09-04），第四轮之前已存在；需要混合精度/表示的输入才能触发，本轮未统计生产证伪库是否存在该组合。不冒充第四轮新引入，也不撤销普通 report 修复通过的结论。另列后续回归即可。

## 决策与被否方案

| 方案 | 评价 / 决定 |
|---|---|
| 9422 全绿就按“全部收敛”放行 | 否：现有回归证明特定反例已修，探针证明正式文件发布边界仍有洞。 |
| 再跑一遍全量来否定探针 | 否：相同干净 revision、相同依赖已有收据；新反例不在既有测试里，重复全量不会增加这条边界的覆盖。 |
| 质检分支顺手修实现、迁移用户库 | 否：越过本次只审范围，也会混淆被审 revision 和修复 revision。交给源分支补修再独立验。 |
| 把条件性 `--refuted` 遗留也算第四轮缺陷 | 否：来源提交可追溯，普通 report 的修复仍应给通过。 |
| 留两份中断草稿 | 否：实际都没落盘；本文件统一裁决，短交接只放下一步和证据指针。 |

## 证据、复跑与解释边界

持久证据目录：`/Users/a77/.finance-runtime/reviews/method-closed-loop-29b07912/`。

| 文件 | 内容 |
|---|---|
| `reproduce.py` | 前会话原探针，未经改写；SHA256 `6a3a7b42e37eb8906512b301a063e965df5c2e8d0a398e89552a0ab011739dbb` |
| `results.log` | 前会话结果 |
| `full-pytest-receipt.json` | 原 `20260912T064212Z-29b07912.json` 的逐字节副本；SHA256 `7555be49fa095240e2b39d615d6db1839f47d8c421e35ad80a3c35c9d5dfdff1` |
| `resume-results.log` / `resume-run-path.txt` | 本会话探针重放输出及临时产物目录 |
| `resume-targeted-pytest.log` / `resume-targeted-pytest-receipt.json` | 本会话 5 项回归及对应收据 |

本会话合成数据落 `/tmp/qc-method-resume-29b07912.2F0kTK/`，不进 git。原探针用 `__file__` 的父目录放产物，因此**先复制到临时目录再执行**，不要因开头旧注释写了“only under /tmp”就直接在归档目录运行：

```bash
cd /Users/a77/fwp-wt-qc-method-29b07912
R=$(mktemp -d /tmp/qc-method-29b07912.XXXXXX)
cp /Users/a77/.finance-runtime/reviews/method-closed-loop-29b07912/reproduce.py "$R/reproduce.py"
/Users/a77/finance-workspace-private/.venv-workbench/bin/python "$R/reproduce.py"
```

探针硬绑定被审 worktree，且断言的是**缺陷仍可复现**；exit 0 不是产品通过。验证修复时应改成正向回归，不能直接把这个脚本的 exit 0 当修复收据。本会话未重放前三轮全部原始脚本，不扩张为对全部历史修复逐项独立认证。

## 下一步与沉淀盘点

1. 源分支修第 1 条，并补齐第 2、3 条迁移与交接口径；第 4 条另记条件性遗留。
2. 对新提交重验新增边界和原回归，再取得对应 revision 的必要门禁；合入与共享库迁移仍分别等用户确认。
3. 本轮没有新增通用工具：复用并冻结已有 revision 专用探针作证据，不把硬编码被审树/期待缺陷存在的脚本注册成常规门禁。缺失的正向回归应随修复进入源分支，本只审分支不改门禁。
4. 可迁移原则：**原子占名、完整发布、不可覆盖、崩溃恢复是不同承诺；测试必须在承诺之间的交接点暂停或终止进程。** 这在缓存、账本、任务结果与模型产物落盘中同样适用。
