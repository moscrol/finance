# 8792 边界组合候选：证据与复现

> 后续状态（2026-09-18）：同一 `3faf64fb` 已完成四次隔离真实会话，3 次交付、1 次运行失败；边界局部有效，整体验收未通过。见[独立 live 索引](../2026-09-18-8792-boundary-live/README.md)。下文保留 09-17 工程验收原口径，不把后续失败抹掉或改发旧收据。

- 被验代码：`3faf64fbadcfe45fdd0b306acd223d9e78c56525`，分支 `fix/8792-boundary-integration`。
- 基线：`0a1cb8c4`。组合来源：`c57633bb`（readiness）+ `3c5f485a`（citation），本地合流`51894716`，补限定语`ef9e1c19`、补前缀重复扫描`3faf64fb`。
- 树：`/Users/a77/fwp-wt-8792-boundary-integration`。
- 原件：`~/.finance-runtime/reviews/8792-boundary-integration-20260917/`（本机私有证据，不把原始金融会话提交到Git）。
- [决策/失败史/边界](../../handoffs/2026-09-17-8792-boundary-integration.md)；[接手入口](../../handoffs/inflight/fix-8792-boundary-integration.md)；[机器索引](results.json)。哈希只证明原件身份，不证明覆盖完备。

## 最终检查

| 叶子 | 固定代码3faf64fb结果 |
|---|---|
| Python | 11612P/0F/81S/2xfailed/17warnings，489.73s |
| Ruff | exit0 |
| 前端 lint/typecheck/test/build | exit0，107P |
| 浏览器 E2E | 34P/2S，57.8s；fixture/隔离用户与DB，不是真实模型 |
| 注册表五项 + runtime catalog | exit0，98条crosswalk反向warning |
| 原QC | 原脚本未改判据，15/15 |
| 冻结三句 | 旧[20,24,25]→候选[24,25]，没有替金融答案补做合格判定 |
| 精确收据 | 8项通过，base drift=0 |

权威全量收据：`~/.finance-runtime/test-receipts/20260917T152129Z-3faf64fb.json`；同名原样副本在原件根。
**不要用最近收据**：之后七次变异预期exit1，会覆盖共享最近指针。收据系统并不为进程内替换生成独立revision，因此变异读数必须同时带变异脚本身份，不能说「磁盘干净所以这份红是原版全量」。

`ef9e1c19` 的全量11611P和四叶是历史中间结果；发现性能形状后重新验证了3faf。最终docs-only头只多文档，不冒称其精确revision已全量跑过。

## 普通复现（不改变生产）

在**固定代码的干净检出**运行，且先核版本：

```sh
cd /Users/a77/fwp-wt-8792-boundary-integration
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
umask 022
git rev-parse HEAD
git status --short
# 如当前头已是后续文档提交，不放宽expect-revision；另建detached 3faf64fb检出。
env -i PATH="$PATH" HOME="$HOME" "$PY" scripts/check_test_receipt.py \
  ~/.finance-runtime/test-receipts/20260917T152129Z-3faf64fb.json \
  --expect-revision 3faf64fbadcfe45fdd0b306acd223d9e78c56525 --base-drift-max 0

env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI="$KNOWLEDGE_WIKI" "$PY" -m pytest -q
env -i PATH="$PATH" HOME="$HOME" "$PY" -m ruff check .
```

定向回归是`test_readiness_boundary_regressions.py`（114例）、`test_boundary_gate_integration.py`（26例）、`test_episode_numeric_citations.py`与`test_episode_protocol.py`。新增114/26分母是pytest实例，不是缺陷个数；114中本轮新增30（29个功能对照+1个扫描计数）。

前端在`intelligence/webapp/`：`pnpm install --frozen-lockfile --offline`后执行`pnpm lint && pnpm typecheck && pnpm test && pnpm build`；本轮离线安装成功、锁文件不变。保留esbuild未获安装脚本授权提示，实际构建通过，不自动执行approve-builds。

E2E前确认8793/8795空闲，使用干净环境与：
`WORKBENCH_PYTHON=$PY WORKBENCH_E2E_PORT=8793 RE06_E2E_PORT=8795 RE06_E2E_URL=http://127.0.0.1:8795 pnpm test:e2e`。
配置自建`test-results/workbench-users`、`re06-users`、`re06-market.duckdb`；不使用真人目录。两个skip是研究绑定用例只在desktop执行，tablet/mobile不重复。不可复用现有服务绕过版本隔离。

注册表完整命令（均经`$PY`）：

```sh
"$PY" scripts/build_registry.py check-parseability
"$PY" scripts/build_registry.py check
"$PY" scripts/build_registry.py backfill-tables --check
"$PY" scripts/build_registry.py generate-views --check
"$PY" scripts/audit_ledger_spec_crosswalk.py
"$PY" scripts/gen_runtime_catalog.py --check
```

## 七类反证（进程内替换，不改磁盘源码）

| 变异 | 最终结果 | 防的空测 |
|---|---|---|
| 恢复51894716扫描器，仅功能 | 25F/88P/1 deselected | 限定语修补确实必要 |
| 恢复ef9e1c19重复扫描 | 1F/113 deselected；100次对1次 | 性能门不是机器速度门 |
| 引用屏蔽恒等 | 8F/4P/14 deselected | E1与日期串接后仍保留计划 |
| 日期门关闭 | 4F/4P/18 deselected | 错误发布日期仍拦 |
| 数字门关闭 | 4F/8P/14 deselected | 真实阈值不因去引用编号而失守 |
| 写口退出关闭 | 6F/20 deselected | 格式化问题的拒绝真到写口，不是没触发跟踪/排序 |
| 所有请求变材料 | 6F/20 deselected | 主体与拒绝指令不被排版吞掉 |

以下可复制运行；每组独立子进程，预期都是exit1。代码只能在固定候选检出运行；读Git父版只为反证。日志只落临时目录，不覆盖已归档原件。

```sh
"$PY" - <<'PY'
import os
from pathlib import Path
import subprocess
import sys
import tempfile

assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == '3faf64fbadcfe45fdd0b306acd223d9e78c56525'
assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
boundary = 'intelligence/tests/test_readiness_boundary_regressions.py'
combined = 'intelligence/tests/test_boundary_gate_integration.py'

def prior(version, replace_module=False):
    code = f'''import subprocess, types, sys
import intelligence.services.track_contract as m
old = types.ModuleType('previous_track_contract')
sys.modules[old.__name__] = old
source = subprocess.check_output(['git', 'show', '{version}:intelligence/services/track_contract.py'], text=True)
exec(compile(source, 'previous_track_contract.py', 'exec'), old.__dict__)
m._opt_out_spans = old._opt_out_spans
'''
    if replace_module:
        # Count the regex object in the actual globals of the old function.
        code += '''import intelligence.services as services
services.track_contract = old
sys.modules[m.__name__] = old
'''
    return code

variants = {
    'parent_scanner': (prior('51894716'), [boundary, '-k', 'not qualifier_link_is_scanned']),
    'prefix_rescan': (prior('ef9e1c19', True), [boundary, '-k', 'qualifier_link_is_scanned']),
    'citation_strip_off': ('import intelligence.services.episode_semantic_verifier as m\nm.strip_evidence_ordinals = lambda text: text', [combined, '-k', 'future_review or support_is']),
    'date_gate_off': ('import intelligence.services.episode_semantic_verifier as m\nm._mismatched_evidence_date_indexes = lambda *args: ()', [combined, '-k', 'invalid_claim']),
    'numeric_gate_off': ('import intelligence.services.episode_semantic_verifier as m\nm._novel_numeric_condition_indexes = lambda *args: ()', [combined, '-k', 'invalid_claim or support_is']),
    'writer_opt_out_off': ('import intelligence.services.track_contract as m\nm.persistence_opt_out = lambda query: False', [combined, '-k', 'formatted_financial']),
    'all_requests_material': ('import intelligence.services.user_task as m\nm._reads_like_document = lambda text: True', [combined, '-k', 'formatted_financial']),
}
root = Path(tempfile.mkdtemp(prefix='boundary-gate-mutations-'))
env = {k: os.environ[k] for k in ('PATH', 'HOME', 'KNOWLEDGE_WIKI') if k in os.environ}
for name, (setup, selection) in variants.items():
    code = setup + '\nimport pytest\nraise SystemExit(pytest.main(' + repr(['-q', *selection]) + '))\n'
    with (root / (name + '.log')).open('w') as out:
        result = subprocess.run([sys.executable, '-c', code], env=env, stdout=out, stderr=subprocess.STDOUT)
    print(name, result.returncode, root / (name + '.log'))
    assert result.returncode == 1, 'must be a behavioral failure, not success/load error/no tests'
PY
```

## 两份原诊断重放

```sh
"$PY" /Users/a77/fwp-wt-qc-8792-readiness-0917/scripts/review_probes/qc_8792_readiness.py \
  --repo /Users/a77/fwp-wt-8792-boundary-integration
"$PY" /Users/a77/fwp-wt-8792-sector-history-diag-0917/scripts/replay_sector_history_diagnostic.py \
  --artifacts-root /Users/a77/.local/share/finance-workbench/diagnostics/20260917-sector-history-2030 \
  --runtime-root /Users/a77/fwp-wt-8792-boundary-integration
```

原QC runner SHA256 `d0d9c11913275633072bd4fd425a2a18b0852d2aa2d82dd28919ba975c715c7b`；核导入路径、禁socket、隔离写口。冻结诊断runner的`runtime_revision=bf662e93`来自历史health，不是候选身份。候选身份由`results.json`与`three-sentences-3faf64fb.json`单列。重放输出与原引用修复枝完全一致；原样本的81%/46.875%差异、区间查询invalid_query、manual mappingproxy错误未解决，exit0不等于原答案合格。

## 保留的失败史与授权边界

- `composition-tests-first.log`：测试误用不存在的QueryEnvelope.question，6F/20P；不是业务缺陷。
- `scanner-expansion-red.log`：25项业务断言红 + 3项排序阳性夹具红，28F/111P；不把28当缺陷数。
- 初次撤写口只有3F/3P，发现next-watch未触发跟踪，补真实研究跟踪请求后最终6F；不把初次6个测例均称承重。
- `qualifier-rescan-red.log`：新增计数测试在ef9e1c19扫描100次，1F。
- `mutation-parent_scanner-3faf64fb.log`含26F，其中性能计数点未挂入旧函数globals；最终功能反证改看`mutation-parent_scanner-behavior-3faf64fb.log`的25F，计数另以ef9e1c19反证。
- 未push/PR/合main/部署，8792仍bf662e93；判官semantic默认llm/evidence=auto不变。#770、RE06/#53真人效果、真实模型三类任务未在此签收。
