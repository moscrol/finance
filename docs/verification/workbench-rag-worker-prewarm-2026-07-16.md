# Workbench RAG Worker 启动预热验证

**日期：** 2026-07-16  
**分支：** `fix/rag-worker-import-context`  
**设计：** `docs/superpowers/specs/2026-07-16-rag-worker-startup-prewarm-design.md`

## 结论

启动预热实现通过代码、真实知识库、真实 BGE-m3、API readiness、全量测试和多端
E2E 验证。Workbench 只有在常驻 worker 完成模型加载后才开放端口；首个用户研究
请求不再承担 BGE-m3 冷启动，也不再因 `company_master` 的 20 秒门限丢弃整套结果。

## 根因复现

第一层根因是 worker 动态加载 knowledge-base 的 `scripts/rag_index.py` 时没有建立
CLI 等价的 import context：

```text
ModuleNotFoundError: No module named 'scripts'
ModuleNotFoundError: No module named 'rag_freshness'
```

第二层根因是 lazy worker 的模型首次加载约 43.9 秒，而 owner stage 预算是 20 秒；
首次查询超时会终止 worker，使其永远无法进入 warm 状态。

## 实现验证

- worker cwd 固定为 knowledge-base 根，`sys.path` 包含根目录和 `scripts/`；
- 状态机覆盖 `cold -> warming -> ready | failed`；
- 预热失败只暴露异常类型，不暴露 query、路径或 stderr；
- FastAPI lifespan 在 `yield` 前同步预热，shutdown 显式清理子进程；
- readiness 把 `rag_worker` 纳入 critical，要求 `state=ready` 且 `active>=1`；
- disabled 环境不预热，保持开发/CI 轻量；
- 预热不调用 `retrieve()`，不写会话缓存或 RAG 业务结果缓存。

## 真实 BGE-m3 证据

进程内连续查询：

```text
first_sec=43.852
second_sec=3.960
model_load_count=1,1
returncode=0,0
```

独立 8793 启动门禁：

- startup 期间请求 8793：连接失败，未暴露半热 API；
- 预热完成后：HTTP 200；
- `state=ready`；
- `active=1`；
- `configured_workers=1`；
- `model_load_count=1`；
- `prewarm_latency_ms=48901`；
- market snapshot：2026-07-16 / `duckdb_exact` / ready。

## 个股热态回放

问题：`中际旭创怎么看`

- controller：`stock_deep_dive`；
- owner：`stock-deep-dive`；
- `company_master`：completed，18.56 秒；
- `company_evidence`：completed；
- `financial_transmission`：completed；
- `market_choice`：completed；
- `counterevidence`：completed；
- citations：33；
- RAG：hybrid，热态约 4.30 秒；
- EvidenceAtom：53；
- 不再出现 `company_master 超过阶段时限 20 秒`。

回放仍显示 degraded，原因不是预热失败：

1. 当前证据缺少 L3 公告/订单/量产等公司级硬事实，owner 按既有证据门槛不把候选
   研报升级为已验证事实；
2. 隔离 8793 没有注入生产 LLM provider 配置，合成层按预期走 deterministic
   fallback；没有复制或暴露生产密钥。

“无 L3 时诚实降级”是产品契约，不应为了 smoke 变绿而关闭。正式 8792 部署后需在
生产 provider 环境复核自然语言合成、同会话指代继承和题材 owner。

## 质量门误报修复

回放发现固定句“确定性结构化结果”被简单子串匹配误判为“确定受益”。修复后：

- `确定性 / 不确定 / 无法确定 / 尚未确定 / 待确定` 不触发弱证据硬写；
- `确定受益 / 必然上涨 / 已证实 / 板上钉钉` 继续告警；
- 固定句改为“由结构化规则生成”，减少内部工程术语泄漏。

## 自动化验证

### Python

```text
1839 passed, 1 skipped, 8 existing utcnow deprecation warnings
```

定向：

```text
RAG worker + Workbench API: 79 passed
Output review + ask compose + owner: 73 passed
```

### Frontend

```text
eslint: PASS
typecheck: PASS
Vitest: 56 passed
production build: PASS
Playwright: 15 passed (desktop/tablet/mobile)
```

Playwright 首次启动命令误选系统 Python 3.14，因该解释器没有 uvicorn 而在用例前退出；
显式设置生产解释器
`WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
后 15/15 通过。该事件不是测试失败，也未改代码规避。

### 静态检查

```text
ruff: PASS
git diff --check: PASS
secret/large-file pre-commit gates: PASS
```

## 部署门禁

合并后部署必须满足：

1. `main` 的 `registry-check` 与 `workbench-check` 全绿；
2. 新 runtime 使用版本化 detached worktree；
3. 旧 `05e4fd1d` runtime 保留作回滚；
4. 启动等待至少 120 秒，允许同步预热完成；
5. readiness 必须报告 `rag_worker=true`、`state=ready`、`active=1`、
   `model_load_count=1`；
6. 完成个股、同会话追问、题材三类生产回放。
