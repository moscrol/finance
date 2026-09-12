# fix/sync-code-root@fcf9cca9 快速独立质检

日期：2026-09-12。结论：**局部配置修复通过，不予整体放行；补跑安全边界仍有 P1。**

## 范围与证据

- 被审对象 `fcf9cca9`，分支八笔提交（其中三笔实现）。独立冻结树 `/tmp/sync-qc-fcf9cca9-review`，先检查/测试，后开 `docs/qc-sync-fcf9cca9` 留报告。
- 原分支、主检出脏树、生产配置与数据库均未修改。未外呼、未同步、未启动完整 finalize、未重载 launchd、未推送合并。
- 正确解释器 `.venv-workbench/bin/python`，`tests/test_eval_launchd_wiring.py` **19P/1.05s**；该文件 Ruff 通过，nightly zsh -n 通过；两源 plist 的 plutil 与 plistlib 解析通过。
- 收据：`~/.finance-runtime/test-receipts/20260912T100011Z-fcf9cca9.json`。不是全量收据。
- 无副作用探针：`/tmp/sync-qc-fcf9cca9-evidence/probe.py`、`results.json`。执行实际 run_step 但在 subprocess 边界拦截，不启动同步；shell 只执行源解析和 run_sync 函数，解释器为打印参数的 spy。

## 1. P1：新增一键补跑显式直写生产，绕开 staging 保护

位置：`skills/daily-full-review/SKILL.md:87-91`、`skills/daily-full-review/scripts/nightly_full_review.sh:137-138`。

新推荐命令设置 `MARKET_FEATURE_STORE_DB=<生产库>`，直接调 `run_review_sync.py`。该编排器不会 clone/swap，run_step 启动 sync-* 子进程继承同一变量：

```text
实际 index-daily lambda → python -m market_feature_store.cli sync-index-daily
subprocess env 未覆盖 → 继承 MARKET_FEATURE_STORE_DB=…/market_feature_store.duckdb
```

`market_feature_store/sync/sync_akshare_index_daily.py:122` 直接 `connect()`（默认写连接）。故门禁失败发生在部分生产写入之后，谈不上「失败不换库」。本轮拦截了子进程，没有实际写入。

与同一 SKILL.md:42 的「夜跑失败禁止直写生产；补 staging，门绿才换名」直接冲突。新的 run_sync 只是把脚本路径改对，仍绕过 18:30 `nightly-full-review-s7.sh → nightly-review-sync-staged.py` 包装。**绕过 staging 的 shell 路径早已存在，不全算新引入；但此次明确把它与新增直写命令当作安全补跑推荐，必须一起收口。**

要求：补跑与定时入口共享 staging/质量门/原子发布边界，不另建直写正门。已有夜跑锁的入口不要简单再套一层同锁 shell（会自撞锁），应复用正确层级的编排/包装实现。加失败注入回归：中间步骤/门失败时生产库字节不变，无 swap。

## 2. P2：手动 sync|all 没有继承 plist 的档位与专用代码根

位置：`nightly_full_review.sh:52-53,137-138`，以及该文件不设置 REVIEW_SYNC_PLAN。

源解析+真实 run_sync 函数实测（spy，不同步）：

```text
未设置 FINANCE_SYNC_CODE_ROOT / REVIEW_SYNC_PLAN：
script=…/finance-workspace-runtime/…/run_review_sync.py
plan=UNSET（CLI 默认 full）
db=生产库

显式提供二者：
script=…/finance-workspace-sync/…/run_review_sync.py
plan=local
db=生产库
```

plist EnvironmentVariables 只属于对应 launchd 子进程，不会自动导入人的 shell。两份 plist 同为 local 是正确修复，但不能证明手动 `nightly_full_review.sh sync|all` 也已固定 local/专用根。当前测试反而钉住了 `FINANCE_SYNC_CODE_ROOT:-$CODE_ROOT` 这条回退。

新 SKILL 的直接命令显式给了 local，故该命令没有这一档位问题，但仍有上一条直写问题。要求补跑入口和说明明确合同：必要配置缺失就拒绝，或采用同一受控默认；验证干净 shell 路径，而非仅看 plist/源码字符串。

## 3. P2（遗留未闭合）：生成段仍从同一脏数据树导入代码

位置：`nightly_full_review.sh:121,178`，装机副本也相同。

先 `cd "$WORKSPACE"`，再 `"$OPS_PYTHON" -m intelligence.cli daily …`。FINANCE_CODE_ROOT 环境变量本身不会改变 Python 模块查找路径。

用相同 cwd 仅 import（不运行 daily）确认：

```text
intelligence.__file__=/Users/a77/finance-workspace-private/intelligence/__init__.py
```

这是既有问题，不是本轮新增；但本轮不能把「检查器已指 CODE_ROOT」延伸成整个 finalize 代码根已经钉死。需明确另单/接替指针，或在收口范围内修并检查生成产物的数据根仍正确。

## 本轮可以认可

- 三处 data/l2/all 检查调用确实统一 REVIEW_CHECKER=CODE_ROOT 下脚本，不再裸相对路径。
- sync/finalize 两份源 plist 均有 local 与专用 sync 根。
- 两份装机副本的上述关键字段与源一致；18:30、20:40 计划一致。
- launchctl print 显示加载的两个任务确实有 local/专用根。
- 原作者已经明确「真实同步、最终检查、方法日步尚未贯通」，这个边界应保留。

## 汇报中需要订正的证据措辞

1. 当前两个 launchd job 都是 `runs=0`、`last exit code=(never exited)`。重载命令成功只能证明注册配置，不能写成「两个 job 执行 exit 0」。若说的是 bootstrap 的退出码，请点名命令；本轮未否认先前历史执行，只是不以本次重载作运行成功证据。
2. `607f53a6 已独立复验通过`只能收窄成「正常旧/新 CLI 能力探针分流通过」。上一份独立质检报告 `2026-09-12-method-closed-loop-607f53a6-review.md`（docs/qc-method-607f53a6，提交08ca6edf）仍有坏指针 rc1 回退、help 进程失败冒充能力不存在等缺陷。
3. 本分支 inflight 与日期快照再次重复「active --help 新旧都0」；真实旧快照2efdff46上 active/activate --help均2。前次质检已有输出，不能继续沿用。
4. 日期快照仍写「固定local没做，留给用户」，与198b95f0/已加载配置不符。历史否决若保留须标明后来决策已翻转、依据见哪笔。
5. inflight 已3822字节，仍超过≤3KB；应收窄当前状态，历史放快照。

## 本轮未核实

- 没有重跑真库 09-10 local/full 对照；原报告 COMPLETE/INCOMPLETE 属待引用原始日志，不冒充本轮读数。
- 没有复算15日对账的命中率、周期阶段/新高差量；那是另一组数据证据，与本分支19项接线测试不同分母。
- 未核实名单9-02、同花顺表9-08水位及其变更设计；不能因本分支提及就认定已审完数据面。
- 没有全量pytest/集成与实际补跑收据，不宣称可合并。

## 建议收口

先修补跑 staging 边界、明确干净 shell 配置合同，再补真实入口的失败行为回归；生成段脏根至少明确接替单。冻结最终组合（含另一方法分支的修复）后再约安静全量与真实闭环验收，不能用配置重载或19P替代。此为独立审查，不代修改原作者分支或生产。
