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

## Governed market snapshot provider chain

- provider 顺序：目标日 DuckDB → 目标日 AkShare → 最近完整 DuckDB。
- DuckDB 使用 Workbench Python 只读查询；AkShare 使用独立固定版本 venv，两者通过
  临时 JSON snapshot 交接。
- 数据优先级：既有非本链 complete > 目标日完整事实 > 最近完整事实；partial 永不发布。
- macOS `requests` 会读取 `scutil` 系统代理，runner 通过 `NO_PROXY=*` 才实现真实直连。
- spot 顺序为 Eastmoney 快路径 → Sina 70 页慢路径 → partial。
- complete/partial/failed 退出码分别为 `0/3/1`；readiness 不把 partial 当 ready。
- LaunchAgent 模板为工作日 16:15，但本分支只提供模板和 runbook，没有安装或启动。

真实验收保留了正负两类证据：

- 第一次 AkShare-only smoke 中 Eastmoney/Sina 都被远端断开，26 秒返回
  `quality=partial`；这促使架构从单外部源升级为 provider chain。
- chain smoke 写入 `/tmp`：目标日 DuckDB 缺失；Eastmoney 断连后，Sina 在 133.8 秒
  完成目标日全市场行情，最终 `provider=akshare_exact`、26 个主题、42 只强势股，
  contract 为 `PASS + ready=true`。
- 故意传入不存在的 AkShare Python 后，真实 canonical DuckDB 在 24ms 内生成
  2026-07-15 complete snapshot：5524 条个股事实通过门禁，输出 4 个主线题材、80 只
  强势股，`provider=duckdb_latest`、`freshness=historical`，contract 同样
  `PASS + ready=true`；requested/served date 分别为 2026-07-16/2026-07-15。

因此公开端点恢复时能补最新日；端点失败时不会让 Workbench 整体失去可用行情，也不会
把历史日伪装成当天。

## 自动化验证

```text
P1 provider-focused Python: 91 passed
Full Python (clean user env): 1831 passed, 1 skipped, 8 existing warnings
Frontend components: 51 passed
AkShare + contract focused: 14 passed
plist lint: OK
git diff --check: PASS
Frontend lint/typecheck/build: PASS
Frontend unit: 56 passed
Playwright E2E: 15 passed (desktop/tablet/mobile)
```

桌面会话设置了真实 `FORESIGHT_USER` 时，首次全量 Python/Playwright 会错误读取真实用户
状态；Python 通过显式 clean env 验证，Playwright server 则固定
`FORESIGHT_USER=default` 后在宿主变量仍存在时 15/15 通过。该修复避免本地与 CI 使用不同
用户身份。

Registry 在 worktree 单仓布局四项通过，但只能扫描到 0 个 Skill；在 canonical 多仓布局
能扫描 49 个 Skill，其中 parseability/backfill/views 通过，`check` 因 knowledge-base
当前新增 20 个 Skill 尚未回灌 finance registry 而失败。这是本分支之外的跨仓登记漂移，
没有用单仓空扫描掩盖，也未混入本次行情 provider 改动。
