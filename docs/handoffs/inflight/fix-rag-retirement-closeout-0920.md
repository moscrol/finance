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

生产代码冻结在 `cb4bbf1ce6cd9b1af4b71dcbb13668877dbc54be`，独立 Spec 已 PASS。测试同步提交 `292d78f3afe1513725eb91baa5e65d6ab554ec9d` 修正 keepalive 完成等待；待 Quality。未建 PR、未合 main、未部署。

## 已验证

- Spec 最终独立复核：消费者探针 2 passed、generation 29 passed。其指出旧 1F/119P 是测试先等 sent、未等请求完成的竞态；现于原 3 秒 `_wait_until` 内同时等 `sent>=2` 和 `served>=3`，未改生产计数器或 deadline。
- 测试同步白名单回归首尾均为 `292d78f3`：keepalive/worker/generation 85 passed，相关 Ruff 通过。相对 `cb4bbf1c` 的 `intelligence/services` 差分为空。
- 首次受管捕获的 full/code/wiki/解释器缺失、残余 `PermissionError` 与解释器软链环都转为专用 generation 不可用；真实 `kb_rag.retrieve` 均不运行 CLI。legacy `PermissionError` 与普通协议故障仍保留原行为。
- 脱敏外部消费者探针：修前 2 failed；撤回捕获保护变异 2 failed；最终 2 passed。证据在 `capture-repair/`。
- 真 scratch：KB `3a210103`，hash/BM25，standard/full，alpha→beta→rollback；首次新查询前旧 worker 已 failed/retired，旧注册不能被新 ready 掩盖，close_all 后新代绿，真实消费者不回退 CLI，8/8 子进程关闭。
- 变异：删 current 检查、启动改读 ambient 两项均抓红；另抓红并修复 venv 入口 resolve 缺陷与“不同 venv 同目标”误等价。
- 证据根：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/rag-retirement-fix/`；返修清单 `capture-repair/FINAL-MANIFEST.md`，测试同步 `keepalive-test-sync/`。

## 未验证 / 已知边界

- 未跑整仓、前端、生产索引、BGE、8792、launchd；协调侧将在独占冻结检出跑四叶门禁。
- 不自动迁移父服务；切代后仍由既有 `close_all`/服务重启建立新池。

## 下一步

独立 Quality reviewer 审最终候选；通过后由协调侧决定集成，不直接合 main。
