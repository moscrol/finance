# 受管 RAG worker 退役状态闭环

## 背景

KB 候选 `3a21010323eababb54ce8519093fd60dbacb9451` 已在每次查询前用固定 generation 与 `current.json` 拒绝旧代。金融侧 `PersistentRagWorker` 原来只看子进程是否存活和内部 `_state`，所以 alpha 热进程在 beta 激活后，查询会被 KB 拒绝，但查询前 readiness 仍报告 `ready/active`。更危险的是，消费者把一般 `RuntimeError` 当“worker 不可用”并重跑旧 CLI。

基线是真实新 scratch 根，不读生产大索引：两页资料、hash embedder、BM25、standard/full 两份索引，内容从 alpha 改成 beta 后显式回滚。原探针 SHA256 为 `a4de73d4...4714`；复制前逐字节相同，修前扩展探针 `fdf194f4...9efb` 在新根复现两个旧 worker 于首次新查询前仍 `ready/active`。证据见外部目录 `rag-retirement-fix/worker-baseline/results.json`。

## 发现与实现顺序

1. 新增 `rag_generation_identity.py`。它只识别三个核心键：`KB_RAG_GENERATION`（manifest SHA）、`RAG_GENERATION_MANIFEST`、`RAG_GENERATIONS_ROOT`；普通超时/开关/legacy 路径变量不会被误判成部分受管身份。受管绑定还固定代码、解释器入口、资料、普通/全文索引。
2. 实例创建时读一次 manifest 与 marker，核对实际参数和 manifest 声明，保存 root/candidate/manifest/code/source/wiki/index/python 的身份。之后 status 只读这些身份和小 `current.json`，不扫描索引、不载模型、不 spawn/kill/recover。
3. pool key 加固定绑定。旧实例已退役时，即使新实例 ready，聚合仍 failed；`close_all` 后新代才能整体 ready。不同 root 的两个合法代际允许并存。
4. 查询、预热、keepalive、恢复都先过同一固定身份边界。退役抛 `RagGenerationUnavailable`，`kb_rag.retrieve` 明确停止，不落入通用 CLI fallback；JSON/进程协议故障仍按旧行为 fallback，单次参数非零不改变 generation 分类。
5. 首次真实探针暴露解释器问题：把 venv `python` resolve 成 Homebrew 二进制后，启动失去 venv 依赖而退出。最终设计固定“venv 入口绝对路径 + 入口 inode + 目标 inode”，启动仍用原入口；不同 venv 即使指向同一宿主二进制也不等价。

## 方案对比

| 方案 | 评价 | 结果 |
|---|---|---|
| status 动态 import KB `generation.py` | 易漂且把维护者完整校验带进高频探针 | 否 |
| 每次 status 走 `resolve_startup` | 会验证全代码/资料/索引和运行时，违背纯读小元数据边界 | 否 |
| ambient 环境作为旧实例当前身份 | 新 root 出现会误杀独立旧 root，也可能给旧实例改名 | 否 |
| 固定金融消费快照 + 小 current 指针 | 与 KB 查询护栏同向，成本有界且可独立测试 | 采用 |
| 所有 worker 异常都禁 CLI fallback | 会破坏普通协议故障的恢复语义 | 否 |

## 验证与收据

- 代码身份：`d6812e6220b46ff939dfbcf51ac6c6b93246d361`，基线 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。
- 定向 pytest：94 passed、2 skipped、126 deselected；相关 Ruff 全绿。日志 `final-code-receipt-d6812e62.log.txt`。
- 最终真探针：13 行阶段记录；alpha 初始两 worker ready；beta 激活后首次查询前二者 failed/retired；真实消费者 `persistent_worker_generation_unavailable` 且无 CLI fallback；旧注册存在时聚合红；close_all 后 beta 两 worker ready；回滚后 alpha 两 worker ready；8 个真实子进程全部关闭。结果 SHA256 `9641aab5...dfb9`，探针 SHA256 `83d9fc88...47a6`。
- 承重变异：删除 current 比较 → 退役前状态断言红；启动改读 ambient → 固定旧绑定断言红。两份日志分别为 `mutation-remove-current-check.log.txt`、`mutation-ambient-relabel.log.txt`。
- 真实探针首轮失败脚本已按字节恢复为 `probe_finance_worker.fixed-attempt1.py`，SHA256 `fbce13bd...d32c`，对应金融 SHA `3f5d0690...8a26` 与 `real-fixed.log.txt`；它证明 resolve venv 入口会让真实子进程无响应。

## 后续与禁区

独立 Spec reviewer 通过后再做 Quality reviewer。此切片不做生产切换、父服务自动迁移、KB 仓修改、BGE/网络模型、生产索引读写、8792/launchd 操作。完整四叶门禁由协调侧在独占冻结检出执行。
