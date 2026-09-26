# Spec 独立复核：PASS

复核时间：2026-09-20。无须阻断本有限片的规格缺失、错误实现或范围扩张发现。此结论只签本次源码改动与 tiny fixture 验证，不是生产回填授权、全父链演练或合 main 结论。

候选 `/Users/a77/fwp-wt-backfill-acceptance-closeout-0920`；实际首尾 HEAD 固定为 **`1fd34dc7ab06d54882a5643b4b985fa5ca291b7c`**，status 均为空。代码提交 `be3f29306739ff55ac7f40adbbc9f55503c26abf`，比较底 `3736d5bfa9978dfa0a264bb2e44795c4bc29b27d`。使用 code-review skill 的 Spec 轴；已读本树 AGENTS、偏好卡及本分支交接。期间 main 推进到 e51c5157，不改变本有限复核的底与受测 HEAD；本报告未签新 main 集成。

## 静态证据与要求对应

- `scripts/verify_302132_backfill_acceptance.py:190` 同时保留股票代码格式约束和 `spec.code == CODE`；`:426` 对 apply、verify 分别验证，`:309` 保留嵌入 child 身份，`:444` 保留独立 child 深比较。实际 SQL 的 CODE=302132.SZ 没有变化。
- `:129` 对 bool、NaN/Inf、巨大正负整数返回 False，捕获范围只在 `math.isfinite` 的 OverflowError；`:244`、`:258`、`:266` 分别覆盖 stock、technical、window pin。`:508` 仍由 schema 通过与否控制数据计算；没有新增外围宽泛异常捕获、没有假成功路径。
- `:448` 备份身份、`:468` 完整跨轮 spec、`:477` 逐轮 parquet 三向绑定、`:586` 源表零差约束保留。正常 fixture 37 checks 全绿，选取的原反例保持会红。
- 测试差分无删除原测试/参数项，新增 3 个 huge-int CLI 参数、3 个逐轮伪 code CLI 参数、9 个数值判定参数；收集总数 104，与原 89 + 新 15 一致。测试辅助子进程白名单化属于这次验证边界，未扩生产行为。

## 独立动态结果（分母不混合）

1. 原 probe 原样重跑，3 个场景，runner rc0。control 为 rc0/PASS、37/37 checks；同步伪 code 和 technical `10**400` 各为 rc2/FAIL、22 checks，具体失败均为两轮 schema 与 `data_checks_executed`。`boundary_review.py` 又读取具体 payload 断言字段名、跳过数据计算、外部 child 一致，补足原 probe 只打印、不 assert 的不足。原 probe 内过时的 code/main/diff 注释不作为本次 revision 证据。
2. 独立目标身份 CLI：3/3 场景满足预期。合法另一代码 000001.SZ 同步写父 spec、嵌入 child、外部 child；apply-only/verify-only 只拒绝对应轮且跨轮不一致，两轮一起伪造仍各自被拒绝，所有外部 child 一致检查为 True。
3. 独立数值 CLI：stock.close、technical.ma26、window[0][1] 各 9 个输入。21 个非法值场景（True、False、NaN、+Inf、-Inf、10**400、-(10**400)）全部 rc2/结构化 FAIL，正确 pin 字段报 schema 错且未执行数据计算。6 个有限对照（7、-2.5）全部 schema 通过并进入真实数据检查；其数值不等于 fixture 钉值，因此数据钉值失败是预期，不能称全 PASS。
4. 外部隔离脚本 mutation：仅撤 CODE guard 后，同一伪 code 收据出现 rc0/PASS/37 checks；仅撤 overflow guard 后，同一巨大数收据出现 rc1/无 JSON/OverflowError。两者均令要求的结构化拒绝断言失败。换回候选脚本、复用完全相同收据各得 rc2/FAIL，恢复 2/2。候选树从未被改写。
5. 精选原/新增 pytest：首批 10 passed、94 deselected；约束补核 5 passed、99 deselected，两次 rc0。两组选择互不重叠。没有重跑或移签作者 104、历史 49、9706 或前端；未读生产库、旧大演练库/parquet，未联网或调用模型。

所有 DB/parquet 都是本目录新造的 30 日 tiny fixture；child 确实运行，父收据由 fixture 合成，明确不代表生产父链演练。

## 精确复现命令与证据

以下均在候选树为 cwd；`E` 是这次实际执行的完整白名单前缀（未继承完整宿主环境）：

```sh
E='env -i HOME=/Users/a77 PATH=/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=/tmp FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/a77/fwp-wt-backfill-acceptance-closeout-0920'
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
R=/Users/a77/.finance-runtime/reviews/research-closeout-20260920/backfill-acceptance-review/spec
$E $PY /Users/a77/.finance-runtime/reviews/research-closeout-20260920/backfill302132-design/probe.py --tree /Users/a77/fwp-wt-backfill-acceptance-closeout-0920 --output $R/original-probe
$E $PY $R/boundary_review.py > $R/boundary-run.log 2>&1
$E $PY -m pytest -q -p no:cacheprovider --basetemp=$R/pytest-tmp tests/test_repair_backfill_stock_history.py -k 'acceptance_e2e_baseline_pass or acceptance_rejects_spec_code or huge_int or acceptance_verify_other_parquet or acceptance_apply_other_parquet or acceptance_verify_spec_divergence' > $R/pytest-selected.log 2>&1
$E $PY -m pytest -q -p no:cacheprovider --basetemp=$R/pytest-invariants-tmp tests/test_repair_backfill_stock_history.py -k 'output_and_source_corrupted_together or source_only_corrupted or adjustment_source_tampered or backup_sha_short or child_code_mismatch' > $R/pytest-invariants.log 2>&1
```

四条验证 runner 都 rc0；原输出不可覆盖，复跑须换全新空目录。`commands.json` 记录每个独立 CLI 的完整 argv、cwd、白名单 env、exit code；`boundary-results.json` 记录逐场景结果。输入保留在每个场景目录内，输出为 `acceptance.json`，异常 mutation 保留 stderr。`identity-before.json`、`identity-after.json` 是独立 identity；`review-hashes.json` 记录代码/runner/results/commands SHA256。

SHA256：
- 原 probe：`546a0b7c1683544d099f04cdf7ff90d2b79344a3f9853da94feea6de59e8920e`
- 独立 runner：`bc8f102cdb4408e9becd121f6df7287ab024ad4f74aa8766596f70a34113c8ae`
- 验收脚本：`e786c626d5a56d333d33c38249d4f4a8f8055010ee8286764a2396f4a4db8048`
- 测试模块：`a0c0ecd6a825e6a172bbda49e822c553cf0bdbee694d6688440b94b67795e645`

下一步：交 root 进入 Quality 轴。审查工作只写外部 spec/ 证据，无实现修改、提交或合并。
