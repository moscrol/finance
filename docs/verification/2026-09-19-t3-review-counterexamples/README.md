# T3 独立审查反例与返修收据 · 2026-09-19

**结论：仍需返修，不合入、不部署。** 三轮有效独立裁决均为 `CHANGES_REQUIRED`。
最新业务 `79dba348bb2f4e76aa6be0d692a34baae1b6ddbe` 的既有完整工程套件通过，
但之后新增的“待核对后继续给错值”真实公开出口探针 **0P/4F，exit 1**。
不是服务超时、不是只等裁决，也不是自然金融答案已通过。

## 身份与收据导航

| 对象 | 精确版本 / 路径 | 结论 |
|---|---|---|
| 第一次有效外审 | `qc-retry-01/verdicts/ARL-0001.json`，a2a3301963d11a073f511e1552b53daee7ecd704 | CHANGES_REQUIRED |
| 第一轮返修 | `candidate-64984b33/result.json`，64984b33e6f38eccc50c004b7b79120f1f45a775 | 既有工程门通过，Python 11877P/87S/2xfailed |
| 第二次有效外审 | `qc-repair-64984b33/verdicts/ARL-0002.json`，64984b33e6f38eccc50c004b7b79120f1f45a775 | CHANGES_REQUIRED |
| 第二轮返修 | `candidate-79dba348/result.json`，79dba348bb2f4e76aa6be0d692a34baae1b6ddbe | 既有工程门通过，Python 11912P/87S/2xfailed |
| 第三次有效外审 | `qc-repair-79dba348/verdicts/ARL-0003.json`，79dba348bb2f4e76aa6be0d692a34baae1b6ddbe | CHANGES_REQUIRED |
| 阻塞原样复现 | `qc-repair-79dba348/ratio-hedge-probe.json` / `.exit` | 两句×判官off/成功替身，0P/4F；公开稿仍completed，无缺口或续修 |
| 最终分账 | `review-closeout-outcome.json` | hold；未合main/部署，自然金融会话0 |

两轮业务冻结均通过 Ruff、前端 lint/typecheck/build、前端110P、E2E34P/2S、
固定三仓 registry 五项、原样六例。变异检查分别为25组、28组，均真断言检出、逐项还原绿；
套件基线/最后还原分别305P、340P。各自收据只签各自SHA，不能移签给归档后的分支tip。
`candidate-*/result.json` 的 `passed=true` / `live_model_calls=0` **只描述工程检查**，
不覆盖随后三次模型审查，也不推翻新红探针。

完整 Python 收据原路径：
- `~/.finance-runtime/test-receipts/20260919T065553Z-64984b33.json`
- `~/.finance-runtime/test-receipts/20260919T072906Z-79dba348.json`

复制件在对应 `candidate-*/full-python-receipt.json`；校验日志保留精确revision、完整target、
解释器、依赖、干净树与base drift 0。不能使用会被并发定向测试覆盖的 `latest.json` 代替。

## 原始证据与模型账本

`manifest.json` 登记 **796件、8,049,260字节**原件，绑定来源、档案路径、大小和SHA-256；
归档时逐字节核对。根源为 `~/.finance-runtime/convergence-20260919/retention-repair/`。
排除冻结worktree、锁和缓存；日志、diff及一次性编排脚本仅加`.txt`后缀，内容不变。
配置内只有本机凭证helper路径，不含密钥；不把该配置安装到产品。
原始pytest/JUnit/diff中的尾空格与末尾空行**原样保留**。全档案`diff --check`因此可能非零；
应核它们属于manifest并单独检查新写文档/代码，不能清洗原件或全局关闭门禁。

本轮三次Claude CLI调用各有独占state root，一次有界调用、不自动重试/换模型。
请求别名`sonnet`，本地映射与三个响应信封的`modelUsage`均为`claude-opus-5`；
每次600秒/$6上限，无工具、插件、hooks或MCP。CLI报告费用分别为
$1.19882875、$0.9547405、$1.0830505；是CLI报价，不是结算凭证，provider实际请求数未知。
机械预检由隔离worker执行，模型是无工具静态审查；二者不能互相冒充。

更早的600秒超时仍保留在[上一轮档案](../2026-09-19-t3-retention-repair/README.md)；
其`qc/ARL-0001`与本轮`qc-retry-01/ARL-0001`属于不同state root，不可只凭编号认身份。
旧225件档案与已封存review原件均验证未变。旧日期快照是历史状态，不覆写为新结论；
当前入口见[在途交接](../../handoffs/inflight/q-research-data-readiness.md)，
发现顺序/取舍见[本轮快照](../../handoffs/2026-09-19-t3-review-counterexamples.md)。

## 复现最新阻塞

在仓根使用约定解释器运行：

```bash
.venv-workbench/bin/python scripts/review_probes/check_ratio_hedge_delivery.py \
  --code-root "$HOME/.finance-runtime/convergence-20260919/retention-repair/candidate-79dba348/registry-pinned/finance-workspace-private" \
  --expect-revision 79dba348bb2f4e76aa6be0d692a34baae1b6ddbe
```

附属worktree没有该venv时，解释器改用主树`.venv-workbench/bin/python`。
目标须干净且精确匹配。exit 1 是当前已确认的业务反例；exit 2 是身份/执行错误，不能冒充反例。
`judge_mode=llm`仍为确定性成功替身，`model_calls=0`只限该探针。

本次没有把新红针改成xfail、改题刷绿、删除旧变异，或继续试到取得PASS。
它是后续必须修过的反例，而不是已经接入并通过的CI保护。
