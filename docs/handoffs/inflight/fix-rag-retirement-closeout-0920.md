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

代码冻结在 `d6812e6220b46ff939dfbcf51ac6c6b93246d361`；门页已同步。待独立 Spec→Quality 双审；未建 PR、未合 main、未部署。

## 已验证

- 定向收据：94 passed / 2 skipped / 126 deselected；相关 Ruff 全绿。`FWP_TEST_RECEIPT=0`，解释器为主树 `.venv-workbench/bin/python`。
- 真 scratch：KB `3a210103`，hash/BM25，standard/full，alpha→beta→rollback；首次新查询前旧 worker 已 failed/retired，旧注册不能被新 ready 掩盖，close_all 后新代绿，真实消费者不回退 CLI，8/8 子进程关闭。
- 变异：删 current 检查、启动改读 ambient 两项均抓红；另抓红并修复 venv 入口 resolve 缺陷与“不同 venv 同目标”误等价。
- 证据根：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/rag-retirement-fix/`；最终真探针 `worker-fixed-d6812e62/results.json`。

## 未验证 / 已知边界

- 未跑整仓、前端、生产索引、BGE、8792、launchd；协调侧将在独占冻结检出跑四叶门禁。
- 不自动迁移父服务；切代后仍由既有 `close_all`/服务重启建立新池。

## 下一步

独立 reviewer 先审规格，再审质量；有问题回本分支修。通过后由协调侧决定集成，不直接合 main。

## 踩过的坑

`Path.resolve()` 对文件同一性有用，但不能代表 Python 虚拟环境身份；启动入口本身会影响 `sys.prefix` 与依赖解析。
