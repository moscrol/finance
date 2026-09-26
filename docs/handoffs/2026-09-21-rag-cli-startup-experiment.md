# 2026-09-21 RAG CLI 启动对照：候选不采纳

## 结论和背景

PR #844 仍只交付安全探针诊断，不授权部署。继续调查 `query --help` 的提前导入成本后，隔离实现的懒加载确实缩短了帮助命令启动时间，但也使“检索模块无法导入”从探针失败变成协议兼容。**这不是保持故障覆盖范围不变的性能修复，候选不进入生产或知识库主树。** 历史 readiness 超时根因仍未知。

这里的“假绿”仅指 `RagCliProbe.query_protocol_compatible`，没有运行整套生产 readiness，不能推断 HTTP 会变为 200；已有 worker 等检查仍可能失败。帮助协议、依赖可加载、真实检索、答案质量是不同保证。

## 发现顺序

1. 确认金融 readiness 独立启动 CLI 的 `query --help`，不经过常驻 worker；延长 worker 保活不直接改变这条探针。
2. 知识库 CLI 顶层导入检索实现，`rag/__init__.py` 又提前导入多个子模块。导入 NumPy/YAML 不等于加载 BGE 模型，不能把两者的成本混为一谈。
3. 首次在固定 `d0caf31146a30e2cea05e6549652afb16fe70cb8` 副本实验，发现它不是共享 KB 当前的 `8a413cde59cd0d6a7757c845243024a3016b50bc`。分别保留两组基线和候选；封存时逐个 Python 文件对 Git blob 验证，分别 45/45、40/40 一致。没有复制 wiki 正文、线上索引或未解决冲突。
4. 两处候选修改：包级 `__getattr__` 按需加载子模块；直接 CLI 先解析参数再导入检索实现。模块被 worker 导入时仍保留 `get_embedder`、`rag_store`、`_load_retriever` 等导出，避免破坏模型和索引复用。
5. 新增 13 项候选合同测试，主动禁止导入检索模块验证帮助和用法错误先退出；真正 query 仍须失败。候选全绿，未修改基线上 12 failed/1 passed，证明测试能检测导入顺序变化。这 12 项是预期反例，不是生产门禁失败。
6. 用真实 `probe_rag_cli()` 注入 `rag.retrieval` 的 6 秒导入延迟：原实现返回 `timeout`，候选帮助成功。改为 `ImportError` 后，原实现返回 `nonzero_exit`，候选帮助仍成功，而真正 query 仍非零。这是暂停采纳候选的直接证据。
7. 临时 hash 索引上的关键词和混合检索，CLI 与两次连续 worker 请求的 page_id 均一致，worker 的 `model_load_count` 均为 1。它是 retriever 加载计数，不能等同于真实 BGE 模型只构造一次的完整证明。
8. 将重复排查固化为 `scripts/review_probes/check_rag_cli_startup.py`，增加 6 项证据收集测试。该脚本复制有限代码集合，只建合成索引；清空继承环境、关闭模型联网并阻断 Python socket connect，所有查询和访问日志只写副本。不是通用恶意代码沙箱。

## 方案取舍

| 方案 | 判断 | 结果 |
| --- | --- | --- |
| 延长超时、重试、缓存成功 | 改变故障信号，无法回答首次为何失败 | 不做 |
| 只改 worker 保活 | 不经过帮助探针的执行链 | 不做 |
| 所有导入直接搬进 query 函数 | 可能绕过 worker 的模块级函数替换 | 不做 |
| 帮助解析提前 + 保留 worker 导出 | 启动下降、查询回归通过，但依赖损坏不再被帮助探针发现 | 实验归档，不采纳 |
| 协议探测和依赖/worker 健康显式分层 | 需明确故障集合、worker 关闭或失败时如何判定及全链超时 | 单独设计，不在本轮偷换合同 |
| 保持 PR #844 原探针行为，只追加回放工具和收据 | 维持单次、5 秒、失败分类及 API 503 语义 | 采用 |

## 验证范围

最终交替采样，每臂 20 次，使用生产配置中同一路径 `.rag_venv/bin/python`，但环境已净化且代码、数据均是实验副本，并非线上部署验收。存在同机其他任务，不是空闲主机、严格磁盘冷启动或压力尾延迟测量。

| 固定 KB 基线 | 原帮助中位耗时 | 候选帮助中位耗时 |
| --- | ---: | ---: |
| `8a413cde` | 92.516 ms | 37.763 ms |
| `d0caf311` | 175.171 ms | 72.119 ms |

窗口之间波动明显，不能把两行相减解释为版本成本；也不能用毫秒级当前采样归因历史 5 秒超时。首轮宿主 Python 数据和参数错误的 runpy 尝试不作为最终证据。

所有 pytest 用主树 `.venv-workbench/bin/python`：

| 组 | 结果 | 边界 |
| --- | --- | --- |
| 旧 KB 基线 RAG 测试 | 253 passed | 固定副本 |
| 旧 KB 候选 + 启动合同 | 266 passed | 不是生产兼容签字 |
| 新 KB 基线 RAG 测试 | 308 passed | 固定副本 |
| 新 KB 候选 + 启动合同 | 321 passed | 不是全 KB 仓门禁 |
| 金融跨仓 + worker | 51 passed | 显式 `KB_RECEIPT_CODE_ROOT` 指向新候选，包含此前跳过的 4 项 |
| 金融最终定向组 + 回放工具 | 178 passed, 4 skipped | 默认未设置跨仓根，因此 4 项依然跳过 |
| 回放工具自身 | 6 passed | 已包含在上行，不加总 |

Ruff 与 diff check 通过。早期三份 pytest 输出末尾有共享临时目录清理警告，保留原文；后续使用独立 `--basetemp`，没有修改或清理其他任务目录。未跑全仓、前端、独立外审、真实 BGE 质量、长期稳定性、自然 KB 候选 judge-off、fallback 或生产恢复演练。

## 收据和复跑

本分支工作树下 `tmp/rag-cli-startup/evidence/`（gitignored，勿清理）：

- `selected-manifest.json`：基线 Git 核验、解析 XML 得到的各组计数、选定原件 SHA256。
- `final-current-pair/receipt.json`、`final-new-pair/receipt.json`：解释器、命令、耗时、真实探针返回、金融及 KB 代码哈希；源和副本运行前后均核对。采样时金融 HEAD 为 `bac1b42a8`，新回放工具尚未提交，因此工具另以 SHA256 绑定，不能冒充当时 HEAD 内已有它。
- `candidate-rejected.patch`、`current-candidate-rejected.patch`：仅两处 KB 代码改动。**不得直接应用到共享 KB。**
- `test_rag_cli_startup_candidate.py`：候选合同原件；配合显式 `KB_CLI_STARTUP_CODE_ROOT` 运行。
- 各组 `.log` / `.xml` 和每条命令 stdout/stderr，原件权限 `0600`，帮助输出前后逐字一致。

复跑入口（输出目录必须不存在）：

```sh
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/check_rag_cli_startup.py \
  --baseline tmp/rag-cli-startup/current-baseline \
  --candidate tmp/rag-cli-startup/current-candidate \
  --python /Users/a77/knowledge-base-private/.rag_venv/bin/python \
  --output-dir tmp/rag-cli-startup/replay-new --samples 20
```

脚本 exit 0 表示预期的对照现象已被复现，**包括候选帮助掩盖坏依赖的反例**，绝不表示候选可部署。原始补丁及代码快照留在本机，不作为金融仓运行时代码提交。

## 下一步与禁做

- 优先审阅现有诊断 PR；合并、部署、恢复 K3、关闭判官、重发原两题仍须明确授权。
- 若继续启动优化，先约定协议检查与运行时健康分层后的故障集合，覆盖 worker 启停、缓存/索引损坏、真实加载失败，再决定是否另开 KB 隔离分支。不能只拿帮助更快当验收。
- `market_data_consistency`、旧 runtime 文件漂移来源各自独立处理，本轮没有触碰行情库、共享 KB、启动器和生产进程，也未重新 HTTP 采样。此前生产 health/readiness 记录不冒充本轮新验证。
- 工具沉淀已进入 `scripts/review_probes/`，但属于这组 CLI 候选的定向对照，不新建通用部署器或第二份能力清单。可迁移原则：优化健康检查时，要对“故障覆盖集合是否缩小”做故障注入。共享 memory/harness 因本轮限定工作树未修改；本快照先保留方法与理由。
