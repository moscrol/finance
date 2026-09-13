# feat/research-evolution-05-product-value · 2026-09-13 · 05 用户价值测量：合同 + 纯函数 + CLI + 试点材料

## 这个分支做什么
按 `docs/river-next-specs@194241dd` 的 05 规格交付：ProductValueEvent / MeasurementReceipt / PilotSummary 合同，`validate_event` / `measure_pair` / `summarize` 纯函数，只读证据解析器，离线 CLI，synthetic 夹具，四周试点材料。生产接线归 06（合同见 `docs/research-pilots/research-evolution/06-integration-contract.md`）。

## 决策与被否方案
- 结构化 JSON + 字符串键；否了共享 dataclass 基类（总合同 §5，且过 unread-fields 门禁）
- 收据 / 总结 id 排除 `generated_at` 与 `event_accounting`；否了含审计块（重复上报会改 id，破坏幂等）
- 失败 / 降级 run 直读 `RunStore.load_run`；否了复用 `verify_run_binding` 成功门（幸存者偏差）
- synthetic 输入单独进 `synthetic_check`；否了混算后贴标签（真人分母不能含仿真）
- 无真人输入时回检为 `unknown(no_real_inputs)`；否了显示 0.0
- 主动时间同样扣预登记暂停；孤儿事件只看带本配对号的

## 当前状态
基线 `5fb13a8c`；本轨文件全部在白名单路径内，已按 pathspec 提交（见 `git log -1`）。未推送、未合并。进度 `docs/superpowers/plans/2026-09-13-research-evolution/05/PROGRESS.md`，阻塞 `BLOCKED.md`。

## 已验证
- 本轨 5 个 `test_product_value_*.py`：100 passed
- 全量 pytest：9640 passed / 77 skipped / 2 xfailed，exit 0（收据 `~/.finance-runtime/test-receipts/20260913T065932Z-5fb13a8c.json`）
- `ruff check .`、`layer_audit`、`check_unread_fields`、`check_path_literals` 全 0
- 夹具 `all/`：validate accepted 69；summarize → valid / incomplete / incomplete；engineering_complete / pending / unstarted

## 未验证 / 已知边界
- 未接 Workbench：source_channel 盖章、单 writer、`due_rechecks` 供给都在 06；product_verified 为否
- `RunStoreEvidenceReader` 只在 tmp `RunStore` 上验过；CLI `--users-root` 会让 RunStore 在 runs 目录建 sqlite，对副本用
- `reuse_observed` 新任务起点靠 server `task_started` 或 `payload.new_task_started_at`，都缺则不算主动
- 前端 / e2e / registry 门禁未跑（未改前端与注册表）
- 真人试点未开展：field pending / commercial unstarted 是事实不是缺陷

## 下一步
1. 06 按接线合同接入；ledger-map 登记后启用 writer
2. 用户授权后 `python -m intelligence.eval.product_value freeze` 冻结协议再招募
3. 合并前跑等价 CI（含前端），合并 main 等用户确认

## 踩过的坑
- CLI 把无配对号事件附给每一对 → `orphan_task_events` 误报，改为只对带本配对号的事件判孤儿
- zsh 里 `${PIPESTATUS[0]}` 为空，记退出码用 `$?` 紧跟命令
