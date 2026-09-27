# RAG 探针并发去重：决策与验证快照

## 背景与范围

用户要求按最优路径继续优化。前轮全懒加载候选虽然加快 `query --help`，但掩盖了坏检索依赖，已否决，见 `2026-09-21-rag-cli-startup-experiment.md`。本轮不改共享 KB、索引、启动器、生产进程，不恢复 K3/judge-off。

实现提交：`3451c1d652252da78760b8136cb6b4d6bb5dc777`。PR #844 维持 WIP，合并与部署仍需授权。

## 发现顺序

1. 复核 CLI 导入链：agentic 是默认查询模式，不能把智能体依赖当成查询无关模块；离线 evaluate 的一次 `-X importtime` 自身读数约 2.154ms。这个单样本只能用于排查优先级，不能当稳定收益。未制作或应用新 KB 导入补丁。
2. 检查金融 `/api/readiness` 与 `/api/health/ready`：每次都会启动独立 help 子进程，探针不经过常驻 worker。生产实际并发频率未测量。
3. 选择金融进程内 per-key single-flight，即同时到来的同配置检查共用在途任务。锁只保护任务映射，不包住子进程或文件读取；不同配置可以并行。完成即移除，没有成功或失败缓存。
4. key 绑定代码根、CLI 命令（含解释器路径）、受跟踪代码内容、完整子进程环境的 SHA256、超时预算。环境快照原样传给子进程，环境值不进入 key 明文或 API 响应。代码身份复用既有 helper，并局部补上 `repo_paths.py`，不改变 worker/负能力缓存身份合同。
5. 每位调用者按自己的单调时钟记录耗时。等待者有自己的等待上限，不重试、不取消执行者；执行者仍负责子进程回收。执行者被中断会通知等待者安全失败并清掉任务。
6. 成功返回前再验代码指纹，变化拒绝报绿（固定分类 `code_changed`）；读取失败也拒绝报绿。仍不是热更新或完整供应链校验。
7. 过程中曾增加 `shared_inflight` 响应字段，复核后删除：优化不需要扩大公开字段白名单。最终公开字段不变，测试显式钉住集合。
8. 补单元、真实子进程、HTTP 双入口、回放脚本测试；运行两轮固定版本对照和两种内存变异。移除 `replace` 的一次误编辑被 Ruff 抓住并恢复，未进入提交。工作树内无变异残留。

## 方案对比

| 方案 | 判断依据 | 结果 |
|---|---|---|
| help 先返回、全部运行时依赖懒加载 | 前轮坏依赖会被掩盖 | 不采纳 |
| 仅移出 evaluate 导入 | 单次 profile 显示成本小，KB 跨仓兼容成本更高 | 不继续 |
| 增加成功缓存、重试或延长 5 秒预算 | 会改变失败时效或掩盖首次失败 | 不采纳 |
| 全局锁包住 help 子进程 | 不同配置也会排队，放大阻塞 | 不采纳 |
| 同 key 在途去重、完成即清除 | 可降低并发重复启动，保留 help 依赖加载与失败 | 采纳 |
| 在途结果不绑定/复核代码身份 | 代码变更时可能复用旧成功结果 | 不采纳 |
| 新增 `shared_inflight` API 字段 | 内部计数即可验证，不需要扩大白名单 | 删除 |

## 验证与收据

证据根：`tmp/rag-probe-singleflight/`。本机私有归档，不是 Git 提交内容；保留首跑、失败和原始 XML/日志。`postcommit-receipt.json` 核对提交、测试计数、源码/KB 身份与变异；`selected-manifest.json` 封存 110 个选定文件的哈希，检查全部通过。不要将目录下旧版试验代码直接用于部署。

- 提交后定向组：`postcommit-focused.log` / `.xml`，`230 passed, 4 skipped`，18.94s；测试 revision 为 `3451c1d65`，当时工作树干净。包含 kb_rag、single-flight、runtime roots、workbench API、receipt integration、worker 及两个回放脚本测试。
- 4 项 skipped 为默认未设置 `KB_RECEIPT_CODE_ROOT` 的跨仓测试，本轮未补显式跨仓质量验收。前轮候选结果不能借用为本轮生产兼容结论。
- Ruff、`git diff --check`、全部适用 pre-commit 门禁通过。未运行全仓 pytest、前端、E2E 或独立外审，不能签合并门禁。
- 并发合同覆盖同配置 8 调用 1 子进程、不同根/版本/解释器/环境/超时互不等待、失败广播、下一次调用重新执行、每请求计时、等待超时、中断清理和代码变更拒绝报绿。
- 真实子进程覆盖 import error 和 timeout 后回收；HTTP 双入口共享 timeout / code_changed 仍返回 503，下一次检查恢复后可重新成功。响应无 stderr/异常原文/环境。
- `mutations/receipt.json`：内存中取消去重触发 6 failures（等待者加入断言失败），取消代码变化保护触发 1 failure（错误报绿被断言抓住），均无 errors。原源码 SHA256 前后相同。
- 并行 pytest 的自动收据使用同秒 + 同 HEAD 文件名，出现命名碰撞。本轮变异与最终结果各有独立 XML/日志，不能引用被覆盖的 `20260921T153421Z-5639b6f5.json` 证明两次运行。提交后复验单独运行，有 `20260921T154016Z-3451c1d6.json`。

### 隔离对照

回放脚本 `scripts/review_probes/check_rag_probe_singleflight.py`：原版模块来自金融 `5639b6f53` 的 Git blob，其他 helper 使用当前工作树；不是两套完整历史环境比较。KB 使用固定 `8a413cde59cd0d6a7757c845243024a3016b50bc` 代码副本，40 个 Python 文件逐一对 Git blob；不复制生产 wiki/索引。解释器显式使用 `/Users/a77/knowledge-base-private/.rag_venv/bin/python`。

同一份 KB 副本、同样环境，正常样本交替执行原/新版；每轮各条件 n=10。输出是整批 wall time，包含线程协调，不是纯 CLI 导入成本。

| 采样窗口 | 单请求原版/新版中位 ms | 8 路并发原版/新版中位 ms | 8 路子进程数原版/新版 |
|---|---|---|---|
| compare-v1 | 148.6665 / 149.2600 | 241.8885 / 177.0015 | 每轮 8 / 1 |
| compare-v2 | 93.1325 / 96.8910 | 168.0145 / 115.6585 | 每轮 8 / 1 |

单请求未加速；并发启动数减少 87.5% 是本组场景的结构性结论。两窗口各自的并发中位耗时下降约 27% / 31%，但同机波动明显，非严格冷启动，不是生产尾延迟保证。

两轮都在真实 KB help 导入链注入 `rag.retrieval` 6 秒延迟和 ImportError：两版均分别返回 timeout / nonzero_exit，候选没有跳过故障。两个 receipt 中的金融源码 SHA256 与实现提交逐项一致。没有执行真实 query、BGE 模型加载或答案质量测试。

复跑须新输出目录：

```sh
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/check_rag_probe_singleflight.py \
  --baseline-revision 5639b6f53 \
  --kb-code-root tmp/rag-cli-startup/current-baseline \
  --python /Users/a77/knowledge-base-private/.rag_venv/bin/python \
  --output-dir tmp/rag-probe-singleflight/replay-new --samples 10 --concurrency 8
```

## 边界与后续

- 只在同一金融进程内去重；多进程不会共享，单请求只新增少量代码哈希工作。
- 5 秒约束仍是 subprocess 超时/等待上限，不是包含路径解析、哈希、清理的严格端到端 deadline。
- 受跟踪代码指纹不涵盖所有第三方依赖/解释器内容，不能检测先改后恢复或所有检查后的竞态。部署仍须不可变检出并重启，不支持原地换依赖。
- 未观察生产实际并发、未复现历史间歇超时，不能断言生产 timeout 已解决。本轮未请求生产 HTTP、改启动器或重发生产题。
- 审 PR 并取得授权后，对目标合并 tip 重新执行全部适用门禁；生产验收另涵盖自然检索、K3/judge-off、fallback、质量与恢复。
- 行情一致性和旧 runtime 文件漂移仍是独立问题，不放宽 readiness 绕过。

## 沉淀盘点

重复对照已归位到 `scripts/review_probes/`，不是只留临时脚本；新增合同已有故障注入和变异验证。single-flight 原则已经在项目指令中，未新增能力门或工具注册，不另建能力清单。本轮不写共享 memory/harness；测试收据命名碰撞以本地独立证据规避，收据基础设施另案修复，避免扩散任务范围。
