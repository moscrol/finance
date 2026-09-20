## 这个分支做什么

关闭受管 RAG generation 切代后金融侧 `PersistentRagWorker` 仍误报 ready/active、并可能回退旧 CLI 的缺口。

## 决策与被否方案

| 选择 | 否掉 | 理由 |
|---|---|---|
| 金融侧固定有限身份键、小元数据和 inode；完整校验仍归 KB | 动态 import KB runtime / 扫全索引 | status 必须纯读、轻量，维护者与消费者职责不混 |
| 同 root 的 `current.json` 决定退役；独立 root 可并存 | ambient 环境一变化就判旧实例退役 | ambient 不能给实例改名，实例只认创建时固定 root |
| 固定 venv 入口路径、入口 inode 与目标 inode | 只比较 resolve 后宿主 Python | 两个 venv 可链接同一二进制但依赖环境不同；直接跑目标会丢 venv |
| 退役用专用异常停在消费者边界 | 通用 RuntimeError 后回退 CLI / 禁全部 fallback | 只阻断旧身份重载，普通协议故障仍可恢复 |

展开见 `docs/handoffs/2026-09-20-rag-retirement-readiness.md`。

## 当前状态

代码冻结在 `cb4bbf1ce6cd9b1af4b71dcbb13668877dbc54be`；门页已同步。首轮 Spec 在 `bc43ece9` 发现首次捕获缺失工件会泄漏普通文件系统异常并触发 CLI，已返修；待同一 Spec reviewer 复核后再做 Quality。未建 PR、未合 main、未部署。

## 已验证

- 最终定向收据：121 passed；相关 Ruff 全绿。首次同命令因 keepalive 异步计数时序为 1 failed / 119 passed，原样保留，原命令复跑通过。`FWP_TEST_RECEIPT=0`，解释器为主树 `.venv-workbench/bin/python`。
- 首次受管捕获的 full/code/wiki/解释器缺失、残余 `PermissionError` 与解释器软链环都转为专用 generation 不可用；真实 `kb_rag.retrieve` 均不运行 CLI。legacy `PermissionError` 与普通协议故障仍保留原行为。
- 脱敏外部消费者探针：修前 2 failed；撤回捕获保护变异 2 failed；最终 2 passed。证据在 `capture-repair/`。
- 真 scratch：KB `3a210103`，hash/BM25，standard/full，alpha→beta→rollback；首次新查询前旧 worker 已 failed/retired，旧注册不能被新 ready 掩盖，close_all 后新代绿，真实消费者不回退 CLI，8/8 子进程关闭。
- 变异：删 current 检查、启动改读 ambient 两项均抓红；另抓红并修复 venv 入口 resolve 缺陷与“不同 venv 同目标”误等价。
- 证据根：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/rag-retirement-fix/`；最终真探针 `worker-fixed-d6812e62/results.json`，返修清单 `capture-repair/MANIFEST.md`。

## 未验证 / 已知边界

- 未跑整仓、前端、生产索引、BGE、8792、launchd；协调侧将在独占冻结检出跑四叶门禁。
- 不自动迁移父服务；切代后仍由既有 `close_all`/服务重启建立新池。

## 下一步

独立 reviewer 先审规格，再审质量；有问题回本分支修。通过后由协调侧决定集成，不直接合 main。
