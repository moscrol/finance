# PR #738 · fd8b1baa 独立复验：修复可部分认可，仍不放行

## 范围与基准

用户请审第五轮及跨会话修复汇报。本轮只审，不改实现、部署、生产数据，不执行迁移，不抢跑全量，不停止其他会话。

- `git ls-remote gitea refs/pull/738/head` 核实头为 `fd8b1baa50d16eb765e98ed8537fd6e3422230ce`（开审及落文档前一致）。PR open/未合为用户提供，本轮未另查 PR API 状态。
- 冻结树 `/tmp/method-qc-fd8b1baa-review`；独立文档枝 `docs/qc-method-fd8b1baa`。
- `git diff 607f53a6 fd8b1baa --name-only` **只有原分支 inflight 文档**。实现和测试与上一轮 `607f53a6` 完全相同，所以前次未闭合项不能因新文档提交消失。
- 作者树有他人进行中的 method_validation / 夜跑续修。本轮仅查看其差异识别归属，没有修改、提交或将中间状态算进 PR 验收。
- 前次报告位于文档枝 `docs/qc-method-607f53a6@08ca6edf`：`docs/handoffs/2026-09-12-method-closed-loop-607f53a6-review.md`。

## 发现

### 1. P1，前次未闭合：坏 active 指针仍静默回退默认协议

位置：`intelligence/services/method_validation/store.py:264–270`、`skills/daily-full-review/scripts/nightly_full_review.sh:71–76`。

当前 PR 真实 CLI：`active.json=[]` → `doc.get` 抛 AttributeError → rc=1。夜跑仍把 1 当成 unset。执行冻结源码的绑定段及 `run_method_flywheel()`（只用 spy 替换 daily 写入和通知）再次确认：**默认协议 daily 被调用，无告警**。

前次目录指针、悬空软链误判 unset 也因代码无变化仍未闭合。仅真正未配置才允许兼容回退；不能把 Python 崩溃和业务 unset 共用一个未经核验的信号。

### 2. P2，本轮新证实：目录打开失败被 `_fsync_dir` 吞掉，三条成功路径都虚报持久化成功

位置：`intelligence/services/methodology_backtest/receipts.py:475–489`，尤其 `except OSError: return`。

目录同步是把“文件名指向内容”这一目录项刷入存储；成功调用一次辅助函数不等于目录项已同步。`dd7b6f74` 将首次发布原有的直接 `os.open` 改为此 helper，额外引入了吞掉打开失败的路径。

隔离注入：仅在 `os.open(target.parent, O_RDONLY)` 抛 `OSError(EIO)`；文件写入、文件 fsync 和正式名发布照常，检查调用轨迹。

| 路径 | 实测调用 | 返回 | 结果 |
|---|---|---|---|
| 首次发布 | file_fsync → directory_open_EIO | True | 无异常，没有目录 fsync |
| 同内容重试 | directory_open_EIO | False（幂等成功） | 无异常，没有目录 fsync |
| 竞态输家（注入同内容赢家） | file_fsync → directory_open_EIO | False | 无异常，没有目录 fsync |

**原 fsync 失败后重试场景已修**：独立注入的轨迹确为 `["first-failed", "retry-succeeded"]`。不能因此说所有失败点都闭合。

建议默认向上传递目录 open / fsync 错误，重试成功须实际同步。若确需兼容不支持目录同步的平台，要限定已知错误、明确降级，不能吞掉 EIO/EACCES/EMFILE 等任意故障。回归应分别覆盖 open 与 fsync、三条发布路径。此处证据是故障注入，不是实测断电丢失，不声称生产已丢数据。

### 3. P2，前次未闭合：help 执行失败仍被当作无 active 能力

位置：`skills/daily-full-review/scripts/nightly_full_review.sh:64–86`。

注入 help 输出 `RuntimeError: transient startup failure` / rc=1，有效指针在场。冻结 Shell 实际日志仍写“CLI 没有 active 子命令（链切未做）”，随后调用默认协议，无告警。

应先保存 help 的退出码和原始输出；只有 help 成功、列表确无 active 才兼容回退。失败应停止方法步并告警，不能让 grep 未命中覆盖进程故障。

### 4. P2，同族读取边界仍漏：证伪文件为合法 JSON 数组时仍被伪装成空库

位置：`intelligence/services/methodology_backtest/receipts.py:681–692`。

真实 CLI `report --refuted --refuted-dir <隔离目录>`：

| `r@v1/record.json` 内容 | rc | stderr | 报告 |
|---|---:|---|---|
| 0 字节 | 2 | 带路径 JSONDecodeError | 有不完整警告 |
| 非 UTF-8 | 2 | 带路径 UnicodeDecodeError | 有不完整警告 |
| `[]` | **0** | **空** | **证伪库为空，目前没有任何规则被证伪** |

本轮不是否认“读不出”原场景已修；但专用证伪目录下“能解析、结构错误”的文件仍被无声跳过。建议把非对象及不符合本库记录合同的文件加入异常清单；如果支持异种 schema，明确区分允许忽略的外来记录与损坏记录。

附带展示问题：即使 0 字节已返回 2，报告前半仍先打印“证伪库为空”，再追加“不完整”。建议无法读取任何有效条目时只说“本次无法得出结论”，不要先下绝对否定。已有非零退出与警告有效，此展示问题不与无声 rc=0 混算。

### 5. P2，前次未闭合：迁移核对命令及说明仍不成立

`docs/superpowers/specs/2026-09-12-label-version-migration-plan.md:155–158,177–189` 未变化：

- `status --user "$U"`：status 不支持 `--user`，且缺必填 `--study-dir`。
- `capture --study-dir <v3>`：缺 `--labels-db`，参数错误非零不能证明经过封存闸。
- `"$CODE_ROOT/scripts/method_validation.py" activate --help`：脚本 mode=100644，应显式用解释器，否则 Permission denied。
- §4.1 重号，链切标题仍称④，而当前④是 history、activate 为⑤；旧封存后回退默认的表述也需对齐三态合同。

前次 active 的两种输出模式在坏协议 JSON 上 rc=0 / rc=2 不一致，因 `store.py` / CLI 无提交变化仍未闭合；本轮没有重复创建该坏协议用例。

## 可认可的修复和收据

本轮冻结源码，独立定向：

- `pytest -q intelligence/tests/test_methodology_backtest.py -k 'idempotent_retry_still_syncs or refuted_library_reports_unreadable or non_utf8_receipt_is_wrapped'`：**3 passed / 84 deselected / 10.65s**。
- 收据：`~/.finance-runtime/test-receipts/20260912T101041Z-fd8b1baa.json`。
- 相关 receipts / CLI / 测试 Ruff，夜跑 `zsh -n` 通过。
- 真实 Shell 结果：unset、有效指针、旧 CLI 的正常路径可调用 daily；普通非法 JSON 停止 daily 且通知；数组指针、help 失败错误调用默认 daily 且不通知。探针没有触发真实 daily、联网通知或写共享库。
- 原目录 fsync 失败后的幂等重试独立故障注入通过。非 UTF-8 已存在收据的带路径异常包装回归通过。

核对作者的全量与重跑收据（非本轮重跑）：

| 收据文件（均在 `~/.finance-runtime/test-receipts/`） | 冻结提交 | 结果 |
|---|---|---|
| `20260912T094717Z-22c60030.json` | 22c60030 | dirty=false；9435P / 0F / 77 skipped，exit 0 |
| `20260912T100011Z-607f53a6.json` | 607f53a6 | dirty=false；9436P / 1F / 77 skipped，exit 1 |
| `20260912T100043Z-607f53a6.json` | 607f53a6 | 同一个失败用例，1P |
| `20260912T100047Z-607f53a6.json` | 607f53a6 | 同一个失败用例，1P |
| `20260912T100052Z-607f53a6.json` | 607f53a6 | 同一个失败用例，1P |

失败项确是 `test_real_conversation_round_trip_persists_skills_sse_and_three_turns`。三份重跑收据是**同一用例连过三次**，不是三个不同失败项都转绿。支持间歇性失败假设，不单独证明负载是唯一原因，也不能以此把全量 exit 1 改记为 0。耗时 12:34 / 负载归因及作者的变异试验本轮未取得原始全量 traceback/轨迹，未独立认证。

22c60030 的全绿先于能力探测修复；fd8b1baa 代码虽与 607f53a6 相同，后者全量本身是红的。因此当前既有代码缺陷，也缺最终组合的全量放行证据。

## 汇报措辞需改

- “active --help 两边返回0”不是该旧快照的事实。本轮再次实际调用 `~/.finance-runtime/finance-workspace-2efdff46e251/scripts/method_validation.py active --help`：**rc=2，invalid choice**。顶层帮助可以用，但不能用错误的 argparse 原理解释它。
- 原 inflight 已 **23023 字节**，远超 ≤3KB；追加一段新历史没有解决接手入口过长和头部过期，应压缩现状、移历史到日期快照。
- “指针链一次都没跑过”是对旧 Shell 故障场景的解释，不能仅凭一例复现推广为所有生产历史。本轮只认修复后无继承 LOG_DIR 的隔离路径正常。

## 交接与取舍

| 选择 | 否掉的选择 | 理由 |
|---|---|---|
| 只验固定 PR 头 | 把作者树未提交续修并入验收 | 对方正在变异测试/修改，中间 diff 不是可交付 revision |
| 缺陷先修，再冻结最终组合全量 | 先抢一次全量赌负载低 | 现有确定性缺陷不因全量绿消失，且多会话共享 CPU |
| 持续保留旧 CLI 兼容 | 一刀切禁止所有默认回退 | 真旧 CLI 是已证实的部署状态；应收紧失败信号，不取消需求 |

建议由唯一收口人提交续修，并把目录 open 故障及合法 JSON 坏结构加入行为回归；测试要断言 daily 未调用且告警，不止匹配源码字符串。之后核对代码与文档合同，再申请安静窗口跑整树门禁。无用户授权不要迁移、切生产根或改共享库。

临时证据：`/tmp/method-qc-fd8b1baa-evidence/` 中 `probe.py`、`results.json`、`consumer_probe.py`、`consumer-results.json`、`targeted-pytest.log`、`old-cli-help.log`。consumer 复用了前轮隔离只读 fixtures；实际被测 Shell 取自 fd8b1baa。Bash spy 避免宿主 `.zshenv` 改写隔离用户根；被测绑定和消费者函数本身仍由 zsh 执行。

工具沉淀：本轮是只审授权，未把失败探针或门禁修复写入实现枝，也未修改共享知识仓；上述输入、故障点和断言已明确，可由收口人转成仓内测试。这里保留方法与证据，不宣称已落地新的回归门。
