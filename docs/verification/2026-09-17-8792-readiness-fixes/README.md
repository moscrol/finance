# 8792 边界返修 · 固定版本验证索引

被验代码：`6f9df75a6d01c35801dcd7d26b95d2338daf756c`，基线：`0a1cb8c44aaf2d19ae5f5809bf27119b709b8442`。
本目录是之后的文档提交，**不把代码提交收据外推成文档新头、整合头或生产验收**。

取舍/限制见 [决策快照](../../handoffs/2026-09-17-8792-readiness-boundary-fixes.md)，在途状态见 [分支交接](../../handoffs/inflight/fix-8792-readiness-boundaries.md)。

## 结果

| 叶子 | 结果 |
|---|---|
| Python全仓 | 11519 passed，0 failed，81 skipped，2 xfailed，17 warnings |
| Ruff | 全仓通过 |
| 前端 | lint、typecheck、107项Vitest、build通过 |
| 浏览器E2E | 34 passed，2 skipped（绑定链只跑desktop） |
| Registry | parseability、check、backfill-tables、generate-views、ledger-spec-crosswalk全部通过 |
| Runtime catalog | `scripts/gen_runtime_catalog.py --check`通过 |
| 原独立QC探针 | 15/15，无失败/错误/跳过 |

新增84个测试实例：旧版68F/16P，修复后全绿。相关模块选集892P/4S是提交前读数，不冒称全量收据。三个进程内变异分别14、5、12项失败，详见下方复现及 `results.json`。

## 原件与身份

原件根 `~/.finance-runtime/reviews/8792-readiness-fixes-20260917/`，本目录 `results.json` 冻结代码验收时的32份顶层证据文件与关键源码的 SHA256、分叶结果、精确revision。它是索引而非新的测试收据；日志哈希只证明原件身份，不证明测试覆盖完备。审计根下 `baseline/` 是旧基线加同一测试文件的反证树，不包含在日志清单中。

全量原收据：`~/.finance-runtime/test-receipts/20260917T134635Z-6f9df75a.json`（审计根保存逐字节副本）。校验时须在干净被验代码树运行：

```sh
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
"$PY" scripts/check_test_receipt.py \
  "$HOME/.finance-runtime/test-receipts/20260917T134635Z-6f9df75a.json" \
  --expect-revision 6f9df75a6d01c35801dcd7d26b95d2338daf756c --base-drift-max 0
```

后续文档头不能直接冒充精确被验revision；需要时另建该revision干净检出再校验。主干前进导致漂移时如实重验，不放宽参数掩盖。

## 正式回归与原QC重放

在修复代码树使用主树venv（无editable安装），不要使用宿主Python：

```sh
"$PY" -m pytest -q intelligence/tests/test_readiness_boundary_regressions.py
"$PY" "$HOME/fwp-wt-qc-8792-readiness-0917/scripts/review_probes/qc_8792_readiness.py" \
  --repo "$PWD"
```

原QC runner在审查分支`docs/qc-8792-readiness-0917`，runner哈希已记在`qc-replay-6f9df75a.json`。它禁止脏`intelligence/`、核对import来源、禁止socket连接，真实checkpoint只写临时目录；exit0=全绿，exit1=行为拒收，exit2=环境/加载错误。不能把它当全仓测试或生产API测试。

## 三类变异复现（子进程内撤保护，磁盘源码不改）

下面命令在固定修复代码树运行。每个子进程预期exit1；exit0说明承重测试没有抓住变异，exit2/5等说明测试本身没成功执行，均不得报“变异验证通过”。

```sh
"$PY" - <<'PY'
import subprocess
import sys

cases = (
    ("intelligence.services.track_contract", "persistence_opt_out", "lambda query: False",
     "test_explicit_opt_out_blocks_real_writers"),
    ("intelligence.services.episode_semantic_verifier", "_mismatched_evidence_date_indexes", "lambda *args: ()",
     "test_source_date_assertions_remain_mechanically_rejected"),
    ("intelligence.services.user_task", "_reads_like_document", "lambda text: True",
     "test_formatting_does_not_demote_question_or_change_route"),
)
for module, name, replacement, selection in cases:
    code = (
        f"import importlib,pytest\nm=importlib.import_module({module!r})\n"
        f"setattr(m,{name!r},{replacement})\n"
        "raise SystemExit(pytest.main(['-q',"
        "'intelligence/tests/test_readiness_boundary_regressions.py','-k',"
        f"{selection!r}]))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], check=False)
    assert result.returncode == 1, (name, result.returncode)
PY
```

## 全叶验证形状与限制

Python采用 `umask 022`、`env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI="$KNOWLEDGE_WIKI"` 后执行 `"$PY" -m pytest -q`。前端在 `intelligence/webapp` 按锁文件安装，执行 `pnpm lint && pnpm typecheck && pnpm test && pnpm build`。

E2E另设 `WORKBENCH_PYTHON="$PY" WORKBENCH_E2E_PORT=8793 RE06_E2E_PORT=8795 RE06_E2E_URL=http://127.0.0.1:8795`，执行前确认两端口空闲。fixture/用户目录/测试DuckDB隔离、模型密钥清空，不接生产8792；browser/API链通过不代表金融真实模型效果。

保留失败史：`frontend-install.log`是离线缺包失败，成功看`frontend-install-online.log`；`registry-6f9df75a.exit=2`是误写末步脚本名，最终看`registry-final-6f9df75a.exit=0`。不得摘前几行掩盖末步错误。

共享记忆回写单独检查：图谱通过；vault整体19 errors / 17 warnings。`memory-lint-comparison.json`用同一当前库、仅将两个改动文件在内存中读为父版，核到前后错误集合相同，无新增；不是干净历史库全量校验。这些后续记忆维护日志不在上述32份代码验收原件索引中，不能据代码四叶通过声称记忆库全绿。

本枝不含另一agent的引用数字门修复：条件句E1编号误读只测日期函数，不外推全链保留。#770、判官off启用、行情新鲜度、真人长期效果均不在本轮验收范围。
