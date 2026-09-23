# 2026-09-22 RAG readiness 探针诊断（#844）收口与权重脆弱点工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#61（行情恢复）——readiness 唯一红项 `market_data_consistency` 取决于生产库日期，#61 换库后再采样才有意义。姊妹：#75（独立 QC 批）负责本单候选的第二方审查。部署走 8792 链切，需用户单独授权。

## 背景与动机

- PR **#844**（`fix/rag-probe-diagnostics-0921`，远端 head `18c621579`，本地 `1137987db` 领先远端 3 个文档提交未推）：readiness 探针加安全失败分类与同 key single-flight（同配置重叠的 help 请求去重，完成即删，不缓存、不重试、不延长 5 秒单次），失败仍 503。实现停在 `3451c1d65`，其后只有文档。
- 09-22 17:58 按用户要求做过**一次** `GET /api/readiness` 实跑：HTTP 503、780.664ms、`missing_critical=["market_data_consistency"]`；RAG 必要四参数齐、worker ready；索引元数据门通过（年龄 3.86d < 14、chunk_profile 一致、向量/BM25 对齐）。当时五张关键 fact 表 max 均 09-18。**注意 readiness GET 不是纯读**：会 `ensure_recovery` 并建目录，采样要声明副作用。
- 21:47 换库后 `fact_stock_daily` / `fact_market_daily` 已到 09-22，但 13 张本地派生表仍 09-18（见 #61）。readiness 是否翻绿未验，属推断。
- **生产权重脆弱点（本单新增目标，来源 `feat/research-answer-preservation` 交接）**：`BAAI/bge-m3` 权重曾整机不存在且 `HF_HUB_OFFLINE=1` 禁下载，任何新进程预热必败。09-22 用户授权后按固定 sha `5617a9f6` 拉回 12 文件 / 2189 MB（跳过 onnx 2.16 GB）。两个坑：按 sha 下载不写 `refs/main`，离线解析 main 失败；补齐 ref 后 huggingface_hub 1.x 判「快照不完整」。最终用 `RAG_BGE_MODEL` 直指快照目录绕过。**8792 的 worker 在权重消失前已加载所以仍 ready，但一旦重启会撞 incomplete snapshot**；启动器未加 `RAG_BGE_MODEL`，属未做的生产配置变更。
- **已定的形态决策**：single-flight 而不是全局慢 IO 锁或结果缓存；503 与原始日期不改、不放松一致性门去求绿；探针去重不生产行情事实。

## 目标

1. 推送本地 3 个文档提交；#844 前向到最新 `gitea/main`；四叶收据 revision == head；去 `WIP:`。
2. 权重脆弱点闭合：二选一并留记录——(a) 启动器 `~/.local/bin/start-finance-workbench` 加 `RAG_BGE_MODEL=<快照目录>`（生产配置变更，需用户授权，改前后 `diff` 落盘）；(b) 补齐 onnx 让快照完整（磁盘 ≥ 3 GB 余量才可）。默认推荐 (a)，并加一条启动前自检：快照目录不存在或缺 `config.json` 即拒启并打印原因，不静默回落到联网下载。
3. #61 换库后做**一次**声明副作用的 readiness 采样（用户点头后），记录 HTTP 码、耗时、`missing_critical`；对照 17:58 那次。
4. #75 出 Spec + Quality 独立结论后，用户确认合入；合入后按 `docs/workflows/acceptance-workflow.md` §4 链切五步部署（单独授权），并用 `/api/health` 回读 `source_revision`。

## 非目标（写死认领）

- ❌ 不补行情、不写库、不改快照日期（#61）。
- ❌ 不声称「RAG 间歇超时已修复」：n=1 的 780ms 是旧版端到端 HTTP，不是新探针性能。
- ❌ 不轮询 readiness 求绿；一次采样，写明副作用。
- ❌ 不动共享知识库仓（KB）索引；「KB 索引 stale」是机器既有状态，另立单。
- ❌ 不在本单做 K3 / judge-off 切换（#65、#76）。

## 证据路径

| 文件 | 看什么 |
|---|---|
| 分支 `fix/rag-probe-diagnostics-0921`：`docs/handoffs/inflight/fix-rag-probe-diagnostics-0921.md`、`docs/handoffs/2026-09-22-rag-readiness-live-resume.md` | 决策、17:58 采样读数、边界 |
| `docs/verification/2026-09-22-rag-readiness/summary.json`（分支）与 `~/.finance-runtime/reviews/rag-readiness-resume-20260922T175900/`（33 份原件，勿删） | 采样原件、保护文件/主库 SHA 前后不变 |
| 分支 `feat/research-answer-preservation`：`docs/handoffs/inflight/feat-research-answer-preservation.md`「前置阻塞与修复」段 | 权重两坑、`RAG_BGE_MODEL` 绕法、`protocol-amendment.json` |
| `~/.finance-runtime/reviews/research-preservation-natural-live-20260922/launch-config-amendment.json` | 旁路实例当时怎么加的环境变量，照抄形状 |
| `~/.local/bin/start-finance-workbench` | 生产启动器；改动需授权，改前 `cp` 一份带日期后缀 |
| `intelligence/api/app.py` readiness 路由 | 副作用点（`ensure_recovery`、建目录） |
| `docs/workflows/acceptance-workflow.md` §4 | 链切五步与 `--port 8792` 不能省 |

## 步骤

1. 开工三连；`git push gitea fix/rag-probe-diagnostics-0921`（本地领先远端仅文档，PR head 会动，PR 里把旧收据声明改成新 head 或注明）。
2. `merge-tree` 探冲突、前向、推送；低负载四叶。
3. 权重自检：在旁路实例（端口避开 8780–8830，用户根放 `~/.finance-runtime/rag-readiness-<日期>/`）验证 `RAG_BGE_MODEL` 指向快照目录时 worker 冷启 ready；删掉该变量再起，必须失败并打印原因（阳性对照）。
4. 起草启动器改动 diff 贴给用户，授权后改，`launchctl` 不重启 8792（重启另议）。
5. #61 换库后、无其他写者时采样一次 readiness；落 `docs/verification/<日期>-rag-readiness-after-recovery/`。
6. 交 #75 独立 QC；用户确认后 `gitea_pr.py merge … --record`；部署按 §4，回读 health。
7. INDEX #62 行改状态；inflight ≤3K。

## 验收

- [ ] 四叶收据 revision == #844 head。
- [ ] 旁路实例：有 `RAG_BGE_MODEL` 冷启 ready；无该变量拒启且日志有原因（阳性对照）。
- [ ] readiness 采样记录含「副作用已声明、采样前后主库 SHA256 与保护文件不变」。
- [ ] 合并记录含授权原话与出处；部署账本有 `port=8792` 一行。
- [ ] 合入后 `/api/health` 的 `runtime.source_revision` == 合入提交 SHA。

## 红线

- readiness 采样一次，且必须先声明副作用；不轮询、不改日期标签、不直写库。
- 生产启动器与 8792 的任何改动都要用户单独授权；改前备份。
- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 不写明文密钥；网关钥匙只从 launcher 读的同一 `client-keys.env` 取。
