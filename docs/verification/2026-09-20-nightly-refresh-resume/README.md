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

## 独立审核：首次 Codex 尝试 BLOCKED；同日 K3 复跑 Spec PASS · Quality PASS

首次 Spec 只启动一次，thread `01a0bdd4-902d-7ad3-9fc9-f60742e71071`。`nightly-independent/spec/events.jsonl` 记载 Codex 使用额度耗尽（恢复时间 2026-09-27 01:06）；0审核工具、无REPORT、无结论；进程rc1，首尾候选干净。原件 `spec/` 逐字节保留，未被后续复跑覆盖。**此README是作者/接手会话说明，不冒充审核者报告**；审核者结论只看两份 `REPORT.md`。

### K3 复跑（用户确认 K3 可用后，由接手 QC 会话调度）

- 传输：`pi 0.85.1 --provider mirasim-kimi --model kimi-k3 --thinking xhigh`，本机网关 127.0.0.1:18788；禁 extensions / skills / prompt-templates，禁 `edit` 工具，json 事件流。pi 没有 Codex 式 OS 沙箱，隔离靠指令 + 前后四组指纹（候选 HEAD 与 porcelain、共享仓全部 refs 哈希、作者分支树、记忆 vault），两轮全部未变，见各 `execution.json`。
- Spec：独占树 `spec-tree`@d95b706e；prompt 与 Codex 版逐字节只差输出目录（sha `45a06e49…` → `29c31ebd…`）。09:23:57Z–09:39:41Z，45 次工具调用，rc0。自建 fixture 探针 A 27/27、探针 B 18/18，作者 29 项新测试 29P，ruff 0。结论 PASS，报告 `spec-k3/REPORT.md`（sha `644ba90d…`）。
- Quality：独占树 `quality-tree`@d95b706e；prompt 自带 fail-closed（Spec 报告缺失或非 PASS 即 BLOCKED），首尾均记 Spec 报告 sha。09:40:58Z–09:53:11Z，37 次工具调用，rc0。29P；外部副本变异「吞 rc2」12F/17P、「所有 skip 放行」2F/27P，副本已由审核者删除，实跑输出保留在 `quality-k3/events.compact.jsonl` 的工具结果里。结论 PASS，issues=[]，报告 `quality-k3/REPORT.md`（sha `86589b99…`）。
- 接手会话交叉核验（不是第三次独立审核，只证审核者证据真实、可复现、对缺陷敏感）：两份报告内全部哈希与实际文件一致；Spec 5 处源码位置引用逐条属实；Spec 两个探针从中立目录对冻结树复跑 27/27、18/18，逐项判定与审核者日志相同；对变异树注入「借旧审计」缺陷探针 A 5 项变红、注入「所有 skip 放行」探针 B 2 项变红，树已恢复干净；Quality 的 5 文件哈希、差分与 `git show d95b706e` 逐字节相同（409 行）、numstat 唯一删行在 recover、差分无新增家目录字面量均属实，其动态数字逐条对到事件流里的工具输出。记录 `qc-of-spec-k3.json` / `qc-of-quality-k3.json`；复跑与变异日志在 `qc-rerun/`、`qc-mutation/`。首轮复跑曾因 zsh 不分词得到 rc=127，已丢弃、未据此下结论。
- 事件流原件 7.6 MB / 3.4 MB，仓内封存精简版（去掉逐 token `message_update` 与 `tool_execution_update`），原件字节数与 sha256 记在 `manifest.json` 的 `external_only`。
- 边界不变：两轴只签 d95b706e 的 R1 + I1；审核者是 LLM，不给 main / 生产签字；冻结树无 `.agent-memory` 软链，审核者读的是 AGENTS.md 内嵌偏好。合并仍需最终 SHA 全叶与用户确认。

## 回填小片：原双审核实与 PR #802

- [#802](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/802) base=`fix/backfill-302132-scoped`，冻结候选 `1fd34dc7ab06d54882a5643b4b985fa5ca291b7c`，代码 `be3f2930`。
- 原 Spec / Quality PASS 报告逐字节封存在 `backfill-review/{spec,quality}/`；本次对两份清单的15个文件及2份报告核 SHA，候选仍干净同SHA。`backfill-review-confirmation.json` 是证据核实，**不是新的独立复核**。
- 仅签目标302132.SZ绑定、有限数schema与tiny fixture；不签main集成或生产全父链。父收据是fixture合成，child真运行。104项为原作者相关测试；两轴独立分母看各自报告，不相加。

## 仍然不能推出什么

R2跨午夜历史快照回放未修，日期门没有删。要另行明确源业务日证明、真实updated_at与历史日不取即时市值。未执行真实行情采集、生产回填、下一夜时钟触发或自然模型问答；8792/L2/索引/launchd均未改。#801及#789状态已核实，不重复合并。财务#797、runtime#798、历史#800和协调#799仍分别在途，不被本片签字覆盖。
