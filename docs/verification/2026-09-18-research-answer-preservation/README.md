# 研究答案保留：固定提交检查与一次真实会话

## 结论先行

**工程回归通过；已准入终稿的保留行为实测有效；端到端“全部分析保留”验收未过。**

固定代码 `5f3b5b593183aae86a93372149efe6611a92ebc8`。普通质量疑点不再有静默删稿权，但 `finish` 协议准入前仍会拒收正文。真实会话恰好覆盖这两面，不能只报后半段的绿。未 push、未开 PR、未合 main、未部署；8792 未重启或切换。本文是作者验证，不是独立质量认证。

## 身份与证据入口

| 对象 | 本次值 |
|---|---|
| 工作树 / 分支 | `~/fwp-wt-research-answer-preservation` / `feat/research-answer-preservation` |
| 代码提交 / 前置引用修复 | `5f3b5b593183aae86a93372149efe6611a92ebc8` / `478ca199192614a4995141357f5fd255d7474042` |
| 验收时基线 | `gitea/main@0a1cb8c44aaf2d19ae5f5809bf27119b709b8442`，收据校验基座漂移 0 |
| 私有证据根 R | `~/.finance-runtime/reviews/research-answer-preservation-20260918/` |
| 原题 | 这里的行情哪个板块更有机会，历史上有相似的阶段吗 |
| 入口 | 既有 `scripts/workbench_probe.py` → Workbench 会话及消息 API；hybrid；一次首题，零重采样、零澄清续问 |
| user / conversation | `probe-preservation-20260918` / `conv_4c4fbfa7ddb24083853b1f9fbaf525c1` |
| run / 精确助手消息 | `run_20260918_113122_450933` / `msg_05262dd95ebe460ab1e1eccfd9f4155c` |
| 时间（北京时间） | 2026-09-18 11:31:22—11:34:21 |
| 运行后端 / 模型记录 | `continuous_glm` / `zhipu`、`glm-5.3-flash`；语义记录 `correlated_judge=true`，不是独立判官 |

原始 run 工件在 `R/users/<user>/runs/<run>/`，durable Episode 在 `R/episodes/`；不能照 probe 末尾的默认目录提示去另一套用户根找。两份先前被拒稿仍可从 `continuous-episode.json` 的 `events[kind=model_turn].payload.content` 取回，**私有审计留存不等于用户收到**。

- `protocol.json`：事前题目/hash、一次提交与范围。
- `live-inspection.json`：14 项局部检查、状态、正文长度、E号映射、扫描收据。
- `pre-admission-observation.json`：两次准入拒收和恢复替换反例。
- `public-projections.json` / `public-message.json` / `public-answer.md`：从本次精确 ID 重新读取的公开投影。
- `closure.json`：最终 health、停服、写根与快照核对。
- `acceptance-summary.json`：整体 `not_passed`、`promotion_eligible=false`。
- `evidence-index.json`：214 份文件、5,475,994 字节，逐个 SHA-256（内容指纹）与长度复核一致。

[artifact-manifest.json](artifact-manifest.json) 是封存索引原样副本；[receipt.json](receipt.json) 记录本页核心结论与关键原件 hash。数据库/exports/行情快照另由 preparation 与 closure 的 manifests 覆盖，不混入上述 214 份分母。原件仅本地持久归档，清机须保留，不上传整个私有包。

## 固定提交工程验收

权威 pytest 收据：`~/.finance-runtime/test-receipts/20260918T031822Z-5f3b5b59.json`，副本见 `R/checks/`。

| 检查 | 实测 |
|---|---|
| Python 全仓 | **11,594 passed / 81 skipped / 2 xfailed / 17 warnings**；0 failed/error，exit 0 |
| Ruff / diff / layer | 全仓 Ruff、`git diff --check`、分层审计通过 |
| 前端 | lint、typecheck、build 通过；Vitest **8 files / 107 passed** |
| 浏览器 E2E | **34 passed / 2 skipped**；8846/8847 隔离测试服务，非真实模型研究 |
| registry | parseability、check、backfill-tables、generate-views 四项 exit 0 |
| 台账 crosswalk | exit 0，反向 **98 warnings** 保留 |
| 收据身份 | `dirty=false`、dirty_paths 空、依赖门未绕过；期望 SHA、解释器、依赖指纹与基座漂移检查均通过 |

解释器是 `~/finance-workspace-private/.venv-workbench/bin/python`（Python 3.12.13），依赖指纹 `3328bed61f3e21ea`。本机 macOS 26.4 / Node **26.0.0** / pnpm 10.12.1 / DuckDB **1.5.4**；workflow 是 Linux / Node **22** / DuckDB **1.4.3**。这是本地对应命令通过，**不是同 CI 镜像认证**；本次全量也未显式采用 `env -i` 净环境壳。skip/xfail/warning 不算通过案例。

旧 `full21`、`full32`、`focused39` 等是开发中脏树/旧代码读数，不替代固定提交收据。后续文档提交未重跑全仓，不能把这份收据移绑到文档 SHA。SessionStart 的“最近一次收据”可能属于别的 worktree，接手应按上面的精确路径取收据。

## 一次真实会话：两种相反结果都保留

### A. 已准入终稿：局部保留通过

| 层 | 字符数 | 关系 |
|---|---:|---|
| `outcome.draft` | 979 | 安全清洗前后相同 |
| `semantic_verifier.public_answer` | 1102 | 原 979 字为精确前缀，仅追加核验批注 |
| 精确助手消息 / `answer.md` | 1145 | 两者逐字一致；在语义稿后追加历史完成度 notice |

原稿第 4 句的“置信度约 0.4”触发 `novel_numeric_condition`：原句仍在正文，句子账 `demoted_to_issue`，没有 `deleted`。核验批注指出数值条件缺少对应证据，不将其认证为阈值。

状态没有漂白：

- 传输/流程 run：`completed`，probe exit **0**。
- runtime：`partial / finalization_recovered`；结构：`verified_status=partial`，issues/missing_outputs 空，不代表业务无缺口。
- 语义：`partial / judge_status=rejected / judge_mode=llm`；交付：`preserved_analysis`。
- report：`partial`；publication 上限：`partial`，另附“尚未完成声明条件全集的历史比较”。
- `rejected_claim_indexes=[]`，但 preflight 句子账有 1 条机械疑点：不能只数 LLM 索引来断言“没拒绝”。
- `pending_rejudge=false`；guided 未触发，skip reason `mechanical_pending`；adapter repair_attempts/cycles 均为 0。

### B. 准入前：端到端保留未通过

| 尝试 | 原始内容 | 拒收/后果 |
|---|---|---|
| turn-6 | 2610 字符；正文后附 JSON，不是单一 JSON 对象 | `not_json_object`，格式拒收 |
| turn-7 | 合法 JSON 1871 字符，其中 draft **890** 字符 | `history_missing_comparison`：相似窗口和存研究草稿不能充当 `compare_cases` |
| finalization_recovery | JSON 1535 字符，其中 draft **979** 字符 | 新稿准入，runtime 降 partial；此前两稿没有作为正文或补充送达 |

例：turn-7 的“汽车零部件+1.40%/边际量+26.5%”在最终稿中不存在。这只证明该分析段未保留，不证明这句金融事实正确。恢复事件为 `status=recovered / answer_status=partial`，**不是“正文已返回、随后根截止超时仍保留”的真实覆盖**；后者本轮只有离线承重回归。

下一步不能删 `history_missing_comparison` 判据或把它改 passed。应把**可安全展示的同任务候选正文**和**已准入的执行结果/证据绑定**分开承接；保持历史完成度 partial、完整性硬拒与原调用预算。非 JSON 混合内容还需先定义可抽取正文的严格边界，不能发布任意模型消息、工具请求或私有协议。

## 引用、秘密与金融正确性：不同检查

公开稿引用 9 个 E号：E1、E3、E75、E69、E76、E77、E78、E71、E28；都映射到本次 93 张证据卡中的真实 hash，且出现在 outcome 绑定中。**编号存在和绑定存在，不证明被引用的话能推出结论。**

- 公开 run/report/trace/messages 的仓内 `PublicLeakScanner`：408 个字符串，零命中。
- 首轮 `SecretScanner`（上述公开投影及 private Episode）：19,218 字符串，零命中。
- 封存扩大检查（42 份 live 工件、模型上下文、server/probe 日志和启动元数据）：38,049 字符串，零命中。排除含假秘密 canary 的回归日志、量具源码与首次导入失败栈；具体范围见 `preserved-secret-scan.json`。
- 这些是既有模式扫描器和作者观察，不是独立安全证明。公开稿仍含 `research_only`、`decision_eligible=false`、`hindsight_reconstruction` 等机器字段措辞；零命中不等于公开文案已全部通俗化。

对引用卡与历史工件的只读核对还发现质量边界（未另调模型、未重算数据库）：

1. E3 的 13 / 27.66 / 第1、E75 的 -1.464187…、E76/E77 最近窗口 -0.903584… / 距离0.382876…、E78 的 -2.383652…均能在卡中找到；不代签供应商原始事实。
2. 本次板块历史查询 **只用 `return_pct`** 匹配，不足以称“相似热度/量价结构”；47 个枚举窗中 36 个无可比特征、2 个与参考重叠，仅9个返回，不是47个都可比。
3. 9个返回窗口的完整日期范围是 **2026-06-23—2026-08-31**，不能一概写“均在近1–2个月内”。收益差0.5606应区分“百分点”和相对变化百分比。
4. E1 已有市场情绪类比后5/10/20日结果，板块自身召回则缺后续结果；终稿边界需分清这两个对象，不能把局部缺口写成所有证据都没有。
5. `ranking_intent=false`、matrix_rows/flip_rows 均0；“哪个板块更有机会”仍未形成完整同窗板块比较。E28 是判读规则，不是当天方向锚、高度锚和最后一龙的逐项观测。

本轮不作投资排序认证、收益预测、框架优劣比较或单样本可靠性结论。旧8792的七类金融诊断、manual `mappingproxy` 故障不因本分支展示成功而关闭。

## 隔离与收尾

市场库使用 APFS clone（不同 inode），读取源库期间确认无 WAL、源 stat 稳定、源/副本 hash 一致；副本文件只读。exports/market_snapshot 同样复制并核对 manifest。快照行情截至 **2026-09-17**，与旧原题诊断的9/15不同；知识库、金融文件、L3和外部 web 输入未宣称全部冻结，因此不是严格前后 A/B。

显式分离 DB、exports/快照、users、episodes、deploy ledger、pending rejudge、L3 cache 与 vault 根；生产 launcher 只读取 export 行到内存，未执行生产启动命令，凭据未打印或落明文环境文件。只换端口/用户不够，特别是 `FORESIGHT_EPISODE_STORE` 必须换根。

11:39:52 收尾：保存候选最终 health/readiness 后停止本轮 PID94957，8848 不再监听；按 owner 移除本轮 live 锁。候选始终加载干净 `5f3b5b59`，代码匹配；8792 前后九项身份/配置一致，仍为 `bf662e9310ff751a4c31763815ee78fb7d6d5122`。市场副本和快照未变；本轮 Episode 仅在隔离根可见，两套已知共享 users 根无此测试用户，共享 Episode 根无此 run。不是操作系统级无写沙箱证明。

首个审计量具误命名 `inspect.py` 遮蔽 Python 标准库，导入 DuckDB 时失败；改名 `inspect_canary.py` 后成功。`inspect.log`/exit1 和后继 v2 原件都保留；没有因此重复提问。

## 继续工作时

先读 [日期决策快照](../../handoffs/2026-09-18-research-answer-preservation.md)，再取本次 turn-6/turn-7 反例。旧链真实模型验收、真实浏览器研究点击、独立审查未跑；finish 准入、SDK 共享 RepairGoal、`_carry_repair_finish()`及兼容 helper/eval 可达性待全审计。恢复提示的1200字、12卡/360字符投影上限仍在。

固定原件只读使用；若改业务代码，生成新 revision、新回归和新验收记录，不重写本次 `not_passed`，不自动重采样挑好答案。合并与8792部署仍需用户明确确认。
