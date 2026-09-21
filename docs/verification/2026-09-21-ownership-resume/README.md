# 归属接手续轮：只读收据身份修复与 v3 工程验收

## 固定对象与结论

- 基准：`728f327160bbd2485cb635e7ef09d040d718d7b5`，本轮首尾与远端 main 一致。
- v3：`47530e20fe5c3195e50ce429b31898d57918e413`，独占树 `~/fwp-wt-ownership-gates-v3-0921`，已推 `baseline/ownership-gates-v3-0921`。
- 来源：#812 `6c74fa012b1cc79168b72368e262775b66df70f7`、#813 `5994230dadcf23ec0a17c0b27e3a649d782ecf94`、#814 `cdf6647cfe852bd19c23df0408b4bc2af306da6f`。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，最小环境、umask022。
- **作者工程门禁通过；独立 Spec/Quality 未取得，不授权合 main、部署、生产回填或删树。**

| 检查 | 本轮结果 | 原件 |
|---|---|---|
| Python 全仓 + Ruff | 12068 passed / 85 skipped / 2 xfailed；721.76秒；门禁退出0 | `v3/python/0.log`，`v3/python/run.json` |
| 唯一全量收据 | revision/树/解释器/计数/退出码/干净状态一致；回读和条件校验均0 | `v3/python/receipts/gate-Idx5hl80/pytest.json`，`v3/receipt-*.log` |
| 前端 | frozen install / lint / typecheck / test / build / test:e2e 全0；110单测、34 E2E通过/2跳过 | `v3/frontend/gate/frontend.json` 及同目录日志 |
| 注册表 | finance-only CI边界五项退出0，非跨仓验收 | `v3/registry/run.json` |
| 身份 | 三叶首尾同SHA、Git干净；main基准未动 | 各叶 `run.json`、`v3-source-identity.json` |
| 文本合并 | 三个来源与组合对固定main的merge-tree均0，只证文本可合 | `merge-tree-checks.json` |

归档时 `.log` 和 `.py` 文件仅追加 `.txt` 后缀，字节不变。表内用的是原目录路径；仓内对应名可由 manifest 精确查询。Python JSON不记录xfailed数，2X来自同轮控制台；门禁只保存pytest末15行，不称完整stdout。

## 缺口、先红后绿与边界

原 `scripts/main_gate_receipt.py` 把树路径比较放在 `--pytest-exit` 条件内；`run_main_gate.sh --receipt` 不启动pytest，不传该选项，于是错误/缺失/错类型的树身份也返回0。版本相同不能代替工作树绑定。

1. 在不改 `e1b63b1a` 的新隔离树复跑相关188 passed/1 skipped；新探针的合法对照退出0，错树、缺tree、数字tree三例错误放行。`fixture-*.json` 是**测试样本副本，不是实际执行收据**。
2. 正式回归加入7例：错路径/None/数字/空串/缺字段，以及baseline和allow-dirty组合。旧源7 failed/28 passed，修复后相关56 passed。
3. `cdf6647cf` 将树检查提为所有模式共有条件；真实进程退出码仅在有本轮进程时额外比较。源码尖干净门禁56 passed，唯一收据 `source-cdf-receipts/gate-O93oRQ71/pytest.json`。
4. v3相对v2的行为变化只有 `scripts/main_gate_receipt.py` 和 `tests/test_main_gate_receipt.py`。新增7例解释全量12061→12068的变化，不把测试数增长称为覆盖率。
5. 用新helper回读历史原件：匹配原树的v2真收据仍0；首轮零计数收据仍4。通用 `check_test_receipt.py` 允许同rev跨树验证环境相容性，与本轮gate强制当前树绑定是不同用途。

原件：`readback-before.log` / `readback-after.log`、各轮独立收据、`source-cdf-gate.log`、`new-helper-old-*.log`。首次红窗不改写。正式反例已进仓内测试；`probe_receipt_readback.py`、`run_leaf.py`、`verify_existing_archives.py`、`seal_evidence.py` 是本固定对象留证工具，不是新长期调度入口。

## 原档、PR与并行工作

- 两份旧archive各30文件（29原件+README），共60项哈希/大小/源文件逐字节比对通过；manifest自身哈希另记 `existing-archive-integrity.json`。本轮未重跑旧seal、未改变旧日志/收据/manifest。第一份 `321712b6` 的 `gate_passed:false` 和第二份 `e1b63b1a` 的历史作者通过均保留，只签各自对象。
- `pr-*.json` 为修复前GET快照，按指定编号查询（comments/reviews为单页limit100）；不是实时全仓PR清单。修复与封存后的状态以追加评论为准。
- Arena #816 已有另一轮离线NO-GO，见该PR评论5165：完成状态与Match非原子、stale-running恢复及发布审计待修；本轮未复验该报告，也未接管Arena。它不在v3组合中。
- 生产软链仍为 `~/.finance-runtime/finance-workspace-bf662e9310ff`；本轮未操作8792、生产数据库、定时任务或外部参赛端点。没有开启外部独立模型审查。

## 完整性与下一步

`manifest.json` 列出本次封存时点的全部文件（含本说明、不含manifest自身）、源路径、字节数和SHA256；数量以 `len(files)` 为准，测试样本和实际收据按上文分账。封存脚本先检查三叶、首尾身份、日志哈希、真实全量收据与读回退出码，拒绝覆盖已有archive，再复制并逐字节比较。

交接和封存文档放协调分支，不追加到固定验收树；这些后续文档提交不继承v3收据。下一步只在明确授权及预算下做独立Spec/Quality；合入前重核上游、实际合流目标与最终门禁。真实完整副本回填排练仍需单独冻结输入、磁盘/备份和父子发布链。不得分别重复合三单与组合，也不得以Git干净推导删除许可。
