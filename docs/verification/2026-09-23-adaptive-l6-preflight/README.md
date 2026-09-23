# #76 L6 离线预检与执行准备

## 状态

`BLOCKED_RETRIEVAL_DEPENDENCY`。用户先批准三题预算、只读副本及候选先验顺序，核对判官差异后又说「继续推进」；本次继续按终稿判官 llm/flash、检索判官 auto 固定。现已冻结数据、重跑严格截止探针并完成失败阳性对照，但本地 BGE-M3 权重缺失，离线加载失败，故仍 `can_execute=false`。尚未发真实模型请求、启动旁车、合入或部署，不再重复索要已有授权。

候选 PR #868：`31f1b40dd788d36c71da249d59fb769c50d7cd30`；完整工程收据仍绑定 `7ad61a0d3`。既有工程收据不移绑。本轮新增的是验收工装和定向测试，运行候选仍固定不变；新分支 head 不冒充已过原九项全量门禁。

## 发现的前置问题

1. **工单顺序成环**：#72 要求严格探针后先真实改稿、再 #75 终审；#75 要求代码 PR 合入前独立审查；#76 L6 又指定 #72 合入后的 main。建议授权修订为「冻结未合入候选跑 L6 -> 独立终审 -> 另行确认合入」。本轮用户已批准该顺序修订；不包含合 main 授权。
2. **旧启动入口不满足新端口红线**：`scripts/compare_adaptive_research.py:48` 固定首选 8796，`intelligence/eval/live_probe.py` 回退扫描 8796--8820，均落在 #76 禁用的 8780--8830。该 compare 命令也不负责数据冻结、授权检查和完整 closure，不能直接当 #76 runner 使用。可复用其真实 Episode 协议，提交侧可用已有 `scripts/workbench_probe.py` 的显式 `--port` / `--skill-mode hybrid`，但仍须配套冻结与收尾控制，不等于现在可以直接开跑。
3. **历史样本不能冒充候选验收**：三题源协议均请求 glm-5.3-flash，而待验方案为 K3 写手 + flash 判官；Q3 源协议 `dirty=true`，所有旧样本 `data_frozen=false`。题面可原样复用，旧记录可作判定器失败夹具，不能算新代码效果或严格 A/B。
4. **判官状态不是内容验收结果**：Q3 历史字段为 `judge_status=repaired`，同时有六条 `novel_numeric_condition` 删除记录；这六条须逐句检查证据、单位和公开稿去向，不能只按 repaired 签通过，也不能只凭 bound_evidence_hashes 就认定六条全部有充分证据。

## 本轮离线执行

复用候选中的 `scripts/inspect_adaptive_research.py`，对 Q1 / Q2 / Q3 / absence 原件分别使用树外 `--output`，没有启用 `--project-current-judge-status`，所以保留的是历史捕获字段，不是当前代码重建的判官请求。

输出根：`~/.finance-runtime/reviews/pr868-l6-preflight-20260923-1220/`。每个目录含 `off.json`、`controls.json` 和 `sha256.json`。

| 原件 | 历史 revision | dirty | 捕获的 judge_status | 删除记录 | 新清单校验项数 |
|---|---|---|---|---:|---:|
| Q1 寒武纪 | d9a6f6a81 | false | repaired | 0 | 17 |
| Q2 东阳光 | f80bad256 | false | repaired | 0 | 15 |
| Q3 固态电池 | f80bad256 | true | repaired | 6 | 14 |
| 09-22 absence 东阳光 | a1da0c98e | false | unavailable | 1 | 15 |

清单项包括原件与本次提取件；61/61 当前哈希复核通过，不宣称有 61 份独立样本或历史封存链全审计。表内删除数不是误删定性。旧 `elapsed_seconds` 属历史运行耗时，本轮没有重新请求模型。

相关既有测试 `tests/test_compare_adaptive_research.py`：**9 passed**，候选树执行前后干净，收据 `~/.finance-runtime/test-receipts/20260923T042251Z-31f1b40d-8b9018e2adae.json`；JUnit 在证据根 `inspector-tests.xml`。这是提取器/探针的离线工程回归，不是 L6 三题验收。

## 已批准的范围

- 候选固定为 `31f1b40dd788d36c71da249d59fb769c50d7cd30`，独占 detached 检出；代码若变化重新议定，不追着动态分支运行。
- 三道原题逐字固定，SHA256 在 draft；各首发 1 次、重发 0、续问 0，串行运行。网关探针最多 1 次，HTTP 400/429 停批，不换模型/账号硬顶。
- T900 / Episode 600 / 单发 75 / 修订 30 / 每次核验共享窗 150 秒不变。150 秒不是整个用户回合判官的总预算。
- K3 写手、glm-5.3-flash 判官；差异见下节。核对后用户要求继续，终稿判官固定 llm，检索判官显式保留继承值 auto；不改生产、不扩成两组真实对照。实际起跑仍须记录 served model。Q2 保持 local_only 四只读能力，不开 derived_calculation。
- 已完成只读市场库和匹配快照的冻结及 manifest；KB/外部来源未冻结，不称全输入冻结。
- 拟用 19897 / 19898（未启动、未预留），起跑时核实空闲；禁止回退到 8780--8830。独占 users / Episode / 待重核根，remember=false，不落密钥。
- 保留原始回答与 trace，闭环核生产身份、冻结输入和进程/锁；不合 main、不部署、不覆盖旧样本。

## 判官开关核对（2026-09-23）

本轮检查 `9c9c0c0a1`；与获批候选 `31f1b40dd` 的差异仅四个 docs 文件，运行代码相同。未修改运行代码或生产开关。

| 项目 | `ASK_SEMANTIC_JUDGE=llm` | `ASK_SEMANTIC_JUDGE=off` |
|---|---|---|
| 第二模型审稿 | 有，可能含修订复判/重试 | 无，首判/复判均绕过模型 |
| 规则检查 | 保留 | 保留：结构、数值条件、引用、日期、材料缺口等；不是任意语义错误都能机械识别 |
| 删句与写手改稿 | 可发生 | 同样可发生；规则反馈仍进入原回合修订，受原预算约束 |
| 判官引导补检索 | 满足条件才运行 | `skip_reason=judge_off`；不影响正常研究检索 |
| 掉线风险 | 可能出现判官不可用、扣稿或降级 | 没有此模型调用造成的掉线，但结构失败仍可能出现 `unavailable` |
| 私有记录 | `judge_mode=llm` | `judge_mode=deterministic`；`passed/repaired` 不证明独立模型审核 |

代码依据：`intelligence/services/judge_mode.py:24`、`episode_semantic_verifier.py:1743,3040,3856`、`intelligence/runtime/continuous_turn_adapter.py:850`、`intelligence/services/ask_synthesis.py:2238`。共享开关覆盖 Episode 与 ask 的合成判官，但两条引擎的规则门不完全相同。

三个不能混淆的开关：
- `ASK_SEMANTIC_JUDGE` 控制终稿判官；此候选未设置时仍默认 `llm`，拼错也回到 `llm`。
- `ASK_EVIDENCE_JUDGE` 控制检索候选相关性判官，默认 `auto`；要关闭这两类模型判官，两个都须显式 `off`。这是省去判官调用，不是省去写手/其他模型调用。
- 历史目录和协议中的 `adaptive_arm=off` 对应 `WORKBENCH_ADAPTIVE_RESEARCH=off`，不是关闭判官。

L6 可在 off 下观察真实写手改稿与数值保真，但迟到判官回包路径必为 `NOT_EXERCISED`，不能把零调用带来的零迟到采纳签成通过。严格传输探针可独立验证截止机制，不冒充自然模型触发。日常产品不用判官与本次有判官兼容路径验收应分别决策，不因验收把判官恢复成产品必需条件。

离线回归 **113 passed**，无外呼：`test_judge_mode_off.py`、`test_judge_mode_receipt_independence.py`、`test_boundary_partial_delivery.py`、`test_financial_forward_seams.py`、`test_research_delivery_repair.py`、`test_evidence_judge.py`（均在 `intelligence/tests/`）。收据 `~/.finance-runtime/test-receipts/20260923T043519Z-9c9c0c0a-45899dbd697b.json` 校验通过：revision、解释器、依赖与干净树一致。这不是自然 A/B，不据此量化延迟、费用或质量收益。

## 获批后的实际推进（2026-09-23）

新证据根：`~/.finance-runtime/reviews/pr868-l6-natural-20260923-1315/`。

- 独占、加锁候选检出：`finance-workspace-private/`，HEAD `31f1b40dd788d36c71da249d59fb769c50d7cd30`，首尾干净。
- `strict-deadline.json`：候选原有诊断脚本 `--assert-deadline` exit 0，13 个本机模拟 HTTP 场景，`deadline_violations=[]`。迟到判官场景 `report_received=false`、`unavailable=true`，调用记录 `failed/timeout`。这是模拟证明，不是三题自然模型验收。
- `positive-control-review.json` / `positive-control-audit-final.json`：历史固态电池答卷的一条条件句引用 E1；原始 09-10 行为 `成交额亿=1295.9673`，草稿写 `1295.97 亿`，实体、日期、窗口、单位与四舍五入均匹配，但该条件句被 `novel_numeric_condition` 删除。公开稿虽在关注列表保留数值，却未保留该条件。判定器正确返回 `NOT_PASSED`（exit 1 为预期），不把其余五条删除一并判成误删，也不认证这条策略的预测有效性。
- `preparation/frozen-data.json`：数据库独立 inode 的写时复制，3,855,626,240 字节，SHA256 `75ff8d41eebf1a514140081c2899c9b4fd8df7287a0e5e3462fd52f3c975c941`。加上快照/导出文件，共 751 项只读 manifest；JSON 快照契约通过。市场与个股截至 09-22，published 板块/成分 VIEW 截至 09-18，后续作答必须披露并对齐比较窗口，不补库凑齐。
- `preparation/retrieval-probe.log`：用知识库自己的 RAG 解释器和 `rag.embedder.get_embedder('bge-m3')` 离线加载，报 `OSError: no file named model.safetensors, or pytorch_model.bin`。没有下载、换模型或降级检索；观察到其他进程持有 `.incomplete` 文件，不干预它。
- `preparation/closure.json`：生产七字段前后全一致，冻结 manifest 不变，候选仍干净；没有起旁车/占锁。旧字段 `processes_started=0` 指旁车为零，实际执行了一个已退出的本地检索探针子进程；最终根 `closure.json` 明确区分。没有消费网关探针或三题额度。

工装归位：`scripts/review_probes/prepare_adaptive_l6.py`（授权与题面哈希、只读冻结、原始数据鲜度、离线依赖探测、前后身份核对）和 `audit_adaptive_l6.py`（绑定原件的逐句复核汇总，缺审计/缺实际改稿/缺迟到样本不签 PASS）。后者不是自动语义判官，也不是独立 QC。相关测试在 `tests/test_adaptive_l6_audit.py`；验证收据以本节后续记录和 Git 提交为准，脏树开发读数不作 clean-revision 证明。

## 仍需完成

本机检索权重可用并复核 -> 补齐真正 live controller 的独占端口、单次提交预占、400/429 立即停批、启动/收尾验证 -> 使用已冻结输入三题各一次 -> 逐项审计 -> #75 独立终审。正文保留的语义审计不能由 activity counts 替代；没有发生迟到回包时，该自然分支标 NOT_EXERCISED，严格传输探针证据单列。单位错位仍归 #852，不能在批内顺手修后重跑刷绿。

没有通过改运行时代码、换题、换数据或降级检索绕过阻塞。新增工装不发模型调用；正式 live controller 仍须围绕候选原有 Workbench 入口装配，不复活旧端口扫描入口。
