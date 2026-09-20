# 2026-09-20 · 接手夜跑刷新与回填验收

## 身份与结论边界

- 原协调会话：`01a0bca6-ab06-7d11-aa00-75cb22254403`；原工作树 `~/fwp-wt-research-closeout-0920` / PR #799。未触碰其未提交归档。
- 本枝：`fix/nightly-refresh-resume-0920`，PR [#803](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/803)，**WIP，独立审查受阻，不合 main / 不部署**。
- main 基座 `e51c5157c9ea9aa86491c486663700e7d7696a6f`，原夜跑 `6356ffd5e703b30948f687baaaf60102bf97f0a5`；合流 `34f49ce1`；受测代码 `d95b706edc6e44f3dfa54d7b8837dfdd36b16cf2`。
- 本目录由后续文档提交封存，**以下全叶数字属于 d95b706e，不是文档 tip 的全量收据**。合并/部署之前仍核最终版本和最新基座，不能直接移签。
- 外部原件：`/Users/a77/.finance-runtime/reviews/research-closeout-resume-20260920`。`manifest.json` 逐文件记录来源路径、字节数及 SHA256；`.py.txt` / `.log.txt` 是逐字节封存，不是另一个执行入口。无生产 DB 或大演练产物。

## 作者实跑

| 检查 | 结果 | 证据 |
|---|---|---|
| 固定源码 Python 全量 | 11913 passed / 85 skipped / 2 xfailed，rc0 | `nightly-gate/pytest.log.txt`、`python-registry.json` |
| Ruff | rc0 | `nightly-gate/ruff.log.txt` |
| registry parse/check/tables/views、ledger-crosswalk | 五项 rc0 | `nightly-gate/*log.txt` |
| Python 严格收据 | 完整 revision 一致、干净树、解释器/依赖一致、基座漂移0，rc0 | `nightly-gate/receipt-check.log.txt`、`receipts/20260920T074400Z-d95b706e.json` |
| 前端安装/lint/typecheck/test/build/E2E | 六项 rc0；单测110P；E2E34P/2S | `nightly-frontend/frontend.json` 与各步日志 |
| 固定源码定向11模块 | 160P，rc0 | `nightly-refresh/frozen-related-restored.log.txt` |
| 撤刷新判据 | 同两条实际断言2F；恢复同输入2P | `nightly-refresh/mutation-refresh.log.txt`、`mutation-restored.log.txt` |
| 扩大skip豁免至所有步骤 | 2F/7P；恢复同一选择9P/3 deselected | `nightly-refresh/mutation-skips.log.txt`、`mutation-skips-restored.log.txt` |
| 原独立探针适配副本 | 作者复跑rc0；R1拒绝、正常fixture真更新；R2继续安全拒绝 | `nightly-probe/probe_spec.py.txt`、`probe-results.json`、`probe.log.txt` |

全量与前端使用两棵独占检出，首尾 `d95b706e` / dirty=false / identity_stable=true。Python门禁依赖固定为 KB `1254224be89e2c4974350b7f3e985dbedb5dc043`、研究站 `f606583867fe1cad8de96b06be1dd6cfe2b57e51`，身份见 `nightly-gate/target.json`。白名单环境、umask022，主树 `.venv-workbench/bin/python`；receipt_redirect 只改收据落点、不改测试断言。前端端口19081/19084，不借生产8792。

变异只发生在单独的 `nightly-mutation/finance-workspace-private`；全量检出从未被变异。两处均已恢复，随后160P与同skip选择9P，最终 git status 为空。阶段一刷新反例、阶段二Hithink集成反例的红日志也保留，未用后来的绿覆盖它们。

### 定向复跑入口

在新的同SHA独占检出中，使用主树venv、`env -i HOME=/Users/a77 PATH=/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=/tmp FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1`：

```sh
$PY -m pytest -q -p no:cacheprovider \
  tests/test_stitch_refresh_completion.py \
  tests/test_recovery_refresh_integration.py \
  tests/test_recover_local_review.py tests/test_tiered_sync_local.py \
  tests/test_index_local_fallback_boundary.py tests/test_backfill_sina_resume.py \
  tests/test_review_sync_hithink_wiring.py tests/test_consumption_registry.py \
  tests/test_processing_quality_order.py tests/test_review_sync_export_release.py \
  tests/test_market_feature_store_staging_swap.py
```

两条刷新变异选择：`test_refresh_cannot_borrow_old_success_when_baseline_expired` 与 `test_real_refresh_cli_failure_prevents_child_success`；skip变异选择是 integration模块 `-k 'nonoptional and skip'`。源码保护落在正式测试，不依赖一次性探针才能重现。原probe副本含绝对ROOT和输出路径，复跑须适配至新目录，不覆盖证据。

## 独立审核：BLOCKED，不是PASS

Spec只启动一次，thread `01a0bdd4-902d-7ad3-9fc9-f60742e71071`。`nightly-independent/spec/events.jsonl` 记载 Codex 使用额度耗尽；另有配置/host警告。0审核工具、无REPORT、无结论；进程rc1，首尾候选干净。未自动重试或换provider，Quality未启动。`run_spec.py.txt` / prompt / execution.json 保留调度与身份事实；**此README是作者说明，不冒充审核者报告**。

## 回填小片：原双审核实与 PR #802

- [#802](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/802) base=`fix/backfill-302132-scoped`，冻结候选 `1fd34dc7ab06d54882a5643b4b985fa5ca291b7c`，代码 `be3f2930`。
- 原 Spec / Quality PASS 报告逐字节封存在 `backfill-review/{spec,quality}/`；本次对两份清单的15个文件及2份报告核 SHA，候选仍干净同SHA。`backfill-review-confirmation.json` 是证据核实，**不是新的独立复核**。
- 仅签目标302132.SZ绑定、有限数schema与tiny fixture；不签main集成或生产全父链。父收据是fixture合成，child真运行。104项为原作者相关测试；两轴独立分母看各自报告，不相加。

## 仍然不能推出什么

R2跨午夜历史快照回放未修，日期门没有删。要另行明确源业务日证明、真实updated_at与历史日不取即时市值。未执行真实行情采集、生产回填、下一夜时钟触发或自然模型问答；8792/L2/索引/launchd均未改。#801及#789状态已核实，不重复合并。财务#797、runtime#798、历史#800和协调#799仍分别在途，不被本片签字覆盖。
