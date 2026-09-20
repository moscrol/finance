# 第二份组合：作者工程门禁通过

固定提交 `e1b63b1a5b7c066b7377bbd2d005051863331001`，基准 `728f327160bbd2485cb635e7ef09d040d718d7b5`，独占树 `/Users/a77/fwp-wt-ownership-gates-v2-0921`。解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，最小环境、umask022。

包含看板 `49169f7e`、回填 `49f32259`、收据 `d5d807f80`；三个单项PR分别 #812/#813/#814。组合分支仅用于验收，不重复开功能PR，也没有合入main。

| 检查 | 实际结果 |
|---|---|
| Ruff | 全仓通过 |
| Python | 12061 passed / 85 skipped / 2 xfailed，739.87秒 |
| Python门禁及收据读回 | 退出0；revision/树/解释器/退出码/计数一致，非零执行 |
| 前端 | frozen install / lint / typecheck / build 各0；110 passed |
| E2E | 34 passed / 2 skipped；desktop/tablet/mobile；绑定链只在desktop跑一份 |
| registry | finance-only CI边界五项全部0，不是跨仓验收 |
| 身份 | 三叶前后均同SHA、Git干净、main基准未动 |
| 原故障来源复验 | 实际整仓收集测试走同一门禁1P/1S，子pytest未抢父收据 |
| 独立Spec/Quality | 未取得，未启动新的付费审查 |

唯一全量收据：`python/receipts/gate-6jPrqYoy/pytest.json`。原目录为 `~/.finance-runtime/reviews/ownership-followup-recheck-20260921/`。收据不记录xfailed计数，2X来自同轮pytest控制台；latest仅作导航，不作门禁依据。

## 完整性

`manifest.json` 保存29个原件的源路径、字节数和SHA256，封存前核各叶complete/退出0/前后身份及日志哈希，复制后逐字节比较。新嵌套反例的旧版2F与修后49P在 `author/`。第一轮29个失败原件及manifest在相邻 `2026-09-21-ownership-followup/`，仍为 `gate_passed:false`，没有覆盖或追认。

`worktree-board.json` 是本轮带固定base的333条快照：18条error、52条dirty、137条cherry_plus>0。这些集合有重叠，不能加总为待办数；Git无增量/干净也不是删除许可。`open-prs.json` 是本地Gitea接口快照，受接口limit50约束，不冒充全历史清单。

`review-request.md` 是独立复核的固定输入包，未发送自动队列。`run_leaf.py.txt` / `seal_evidence.py.txt` 仅为本轮有限对象编排留证，不是新增长期调度入口。门禁控制台只保留pytest末15行，不称完整stdout；日志原始空白/ANSI不清洗。

## 不成立的结论

- 不给三个来源分支后续文档尖移签；这套全叶只签e1b63b1a。
- 不证明独立审查、生产数据正确或真实完整副本父子发布演练。
- 不授权main合入、8792切换、真实回填、解除复盘会停抓或删树。
- main或代码变化后不能沿用这一组合的通过结论。

源代码差异检查通过。旧日志原件有尾空白，完整历史diff check会提示；不为清洁格式修改证据。
