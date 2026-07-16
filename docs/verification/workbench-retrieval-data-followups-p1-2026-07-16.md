# Workbench P1 Retrieval, Data Producer and Followups Verification

- 日期：2026-07-16
- 分支：`fix/workbench-product-maturity-p0`
- 结论：P1 本地验收通过；未合并 main，未安装 LaunchAgent，未部署 canonical 8792

## Followups v2

API 契约升级为 `label + full_prompt`，同时保留一个兼容周期的 `question` alias：

- `label` 最多 20 个中文字符，只用于按钮展示。
- `full_prompt` 是完整用户口吻，点击后提交它而不是截断标签。
- LLM parser 兼容旧 `question` 输出；前端组件验证展示/提交字段没有串用。

## Persistent Hybrid RAG worker

Workbench 父进程管理一个 lazy、长驻的 JSON-lines 子进程。首查加载索引和 BGE-m3，
后续查询复用同一 retriever；超时会 terminate/kill 并在下一次查询重建。readiness 暴露
enabled、active、model_load_count 和 lifecycle。

实施时选择 stdio JSON-lines，而没有使用计划候选里的 Unix socket：本机只有一个父进程
和一个 worker，不需要跨进程共享；stdio 没有端口暴露、socket 权限和 stale socket 清理，
同时仍保留进程级强终止边界。若未来多个 Workbench 实例共享一个模型，再升级 Unix socket。

真实知识库烟测：

```text
BM25 raw worker: cold 10.900s, hot 1.036s, model_load_count=1
Hybrid raw worker: cold 24.868s, hot 0.796s, model_load_count=1
Full kb_rag + lineage: cold 43.463s, hot 2.705s, 3 hits, freshness=fresh
```

worker 对旧版 KB CLI 补齐 content hash、section、evidence text/chunk ids、index revision
和 freshness，避免性能升级后丢证据血缘。`RAG_WORKER_ENABLED` 默认关闭，必须在 canonical
部署时显式开启，便于独立回滚。

## AkShare data producer

- AkShare 使用独立固定版本 venv，不进入 `.venv-workbench`。
- 数据优先级：既有非 AkShare complete > AkShare；partial 不覆盖 complete。
- macOS `requests` 会读取 `scutil` 系统代理，runner 通过 `NO_PROXY=*` 才实现真实直连。
- spot 顺序为 Eastmoney 快路径 → Sina 70 页慢路径 → partial。
- complete/partial/failed 退出码分别为 `0/3/1`；readiness 不把 partial 当 ready。
- LaunchAgent 模板为工作日 16:15，但本分支只提供模板和 runbook，没有安装或启动。

真实网络烟测写入 `/tmp`：Eastmoney spot 直接断连后，Sina 在约 2 分 42 秒完成
5,528 只股票；同步结果 `quality=complete`，生成 26 个主题和 42 只强势股，snapshot
contract 返回 `PASS`。

## 自动化验证

```text
P1 focused Python: 85 passed
Frontend components: 51 passed
AkShare + contract focused: 14 passed
plist lint: OK
git diff --check: PASS
```

全仓 Python、前端全套和三尺寸 E2E 放在 P2 完成后统一再跑，避免为每个独立切片重复
承担全量验证成本。
