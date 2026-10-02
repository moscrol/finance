# 审架构

对象：Harness（驾驭层）方向与发布候选的有限切片复核，不是全系统架构认证。

**结论：方向继续坚持“让弱模型更可靠、让强模型有更大发挥空间”，但当前只能认可部分工程机制，不能签模型净收益或发布通过。** 已交付证据按需补读、真实展示记账、快照日期身份保护属于改善输入和能力边界；普通同义追问却仍因旧输出名拒答，说明输出合同仍有封上限风险。原浏览器用例绿不能解除这个缺口。

## 1. 固定对象与协作分工

本次只读另外两条线，不接管产品实现或真实模型实验：

| 线 | 固定树 / revision | 本次看到的状态 |
|---|---|---|
| 发布集成 | `/private/tmp/harness-opt/tmp/arena-harness-release-1002`，`fix/harness-release-1002-takeover@2aea7c27ed469530bc73fb232e65830acc754647` | 干净；最终专用产物显示工程检查通过，`release_authorized=false` |
| 四格评测准备 | `/Users/a77/fwp-wt-model-harness-f4-1002`，`eval/model-harness-f4-1002@38a670be1d0c40b0f5918e9fe580ef41a59edcad` | 干净；PR19/PR18 关系来自交接，本轮未查询远端 |
| 评测续作 | `/Users/a77/fwp-wt-model-harness-f4-live-1002`，同起点 `38a670be1` | 有 owner 的台账与 live-plan 在途改动；读取时仍为准备阶段、真实模型帽 0，不触碰 |
| 本助手复核 | `/Users/a77/fwp-wt-harness-release-qc-1002`，detached `2aea7c27e` | 独占、干净，只跑离线复核；收尾移除，固定 SHA 可重建 |
| 本助手交付 | `/Users/a77/fwp-wt-pr16-qc-1002`，`fix/pr16-qc-1002` | 仅扩展诊断量具与文档，不改产品；量具提交 `ddba3fb7d21bc071a42e1085a48935bd4eb0eda3` |

发布候选与 PR16 的共同基座是 `3a2718c6c7dbf5af8ddad249b50835d09deef8a4`，不是同一补丁栈。`07a2879b7`、比较器修复 `f1e90ae3a` 和评测提交 `ec9295732` 均不是发布候选祖先。不能把 PR16 的旧红灯直接移签给候选，也不能把候选工程绿移签给 PR16。

主路线：**控制面**，让任务、工具、证据身份与校验规则自洽；本轮只做诊断，不再叠加新政策。当前反路线风险是继续扩自然语言词表、固定模板和末端删稿规则，用它们代替模型解释任务。

## 2. 谁拥有循环

依据产品门及对应 runtime 源码，形态分开，不把所有后端平均成“SDK”：

| 后端 | 形态 | 边界 |
|---|---|---|
| `GLMAgentRuntime` / `ContinuousAgentEpisode` | 拥有循环 | 本进程控制模型、工具、消息与进展记账；本轮相关工程测试覆盖此线 |
| `OpenAIAgentsRuntime` | 拥有循环（进程内 SDK） | `Runner.run` 内部推进，按 SDK 接口注入工具、上下文、轮次和截止；不表示与原生 Episode 的每个恢复接缝等价 |
| `CodexHeadlessRuntime` | 租用循环 | 调 `codex exec`，主要在网关/工具边界守门；未做真实后端验收 |
| `DshStubRuntime` | 拥有脚本回放循环 | 测试替身，不是自然模型能力证据 |

产品入口仍有 A 连续引擎与 B 旧问答/专项 owner 路径。此次手动 `stock-deep-dive` 离线追问压到的是专项 owner 合同，不是全部后端的通用循环。

## 3. 六层结论与约束三筛

以下“通过”只覆盖列出的机制。没有检查的入口、真实模型和部署不能跟随通过。

| 层 | 状态 | 证据与边界 |
|---|---|---|
| L1 提示词 / 政策 | **缺口** | `query_understanding._definition_subject` 和继承合同可把相同诉求变成不同必需输出；详见下节。词法分类不应成为不可修订的交付形状。属于行为硬编码风险 |
| L2 上下文 | **通过（补读切片）** | `evidence_read._page` 按序列化后的预算分页，保留游标；`EvidenceReadCoverage` 只累计实际展示字符区间，重读不奖励新进展；未审所有注入入口 |
| L3 工具 | **通过（补读切片）** | `bind_evidence_read_tool` 只读当前 Episode 已呈现 E 编号，参数显式、错误结构化，模型自选是否补读；不读任意路径、不新增独立来源 |
| L4 安全 | **通过（授权/日期切片）** | 开关不授予能力；开关与 contract 授权都要满足。`market_snapshot_sync` 不把最新现货冒充历史/未来/未知交易日，历史数据保留真实日期 |
| L5 韧性 / 纠正 | **缺口** | 同义追问的 `direct_answer` 无候选，`fail_closed_answer_spec` 用缺口提示替换草稿；只改旧名的旁路即可结构通过，说明该失败不是新增证据能修好。不能把它解释成模型笨 |
| L6 可观测 | **通过（本次路径）** | 真实模型输入投影、展示记账、工具事件可定位；探针记录 frame→继承→owner→claim→判决与公开正文。但 message `completed` 不等于任务 `complete`，也不等于内容正确 |

约束逐条过三筛（拦输入还是输出、失效会错还是会笨、模型更强会不会挡路）：

| 已存在约束 | 判词 | 保留或改写方向 |
|---|---|---|
| 工具授权、同 Episode 身份、原引用与截止日 | **保下限** | 模型更强仍需要真实来源和权限，继续硬执行 |
| 有界分页、共享次数/时间帽、只对实际交付记账 | **保下限** | 防无界输入和重复进展；具体帽值是否浪费强模型空间须做可比预算对照，不据结构测试拍量纲 |
| 现货不能贴历史日期，未知交易日不猜可抓 | **保下限** | 限制事实资格，不限制推理能力 |
| 初始词法题型的默认输出与继承输出机械并集，专项投影不归一 | **封上限** | 生成与验证共用一种输出身份；保留本轮真正独立要求，不能用旧字段名否决已有合法内容。不是加更多公司名/问法词表 |
| 单个未识别输出名触发整稿缺口替换 | **可改写成拦输入** | 在合同交付给生成器之前发现身份不一致；输出侧继续检查真正缺答、伪来源与越权。若需修订，给出可执行的具体错误，保留已核验内容，不直接删门放行 |

生产公式后三项：**约束=有；验证=有（结构与语义不等价）；纠正=有但本路径存在缺口**。本轮没有完成 API/工具/上下文/控制流所有恢复路径的审计。

## 4. 可复现发现：同义追问暴露未修的输出身份错位

### 判据

先问 `请个股深挖英维克的液冷业务`，手动选择 `stock-deep-dive`，再用三种措辞问同一风险/验证诉求。要求系统既不丢主体，也不能仅因默认字段别名而替换成缺口提示；**出现公司名或任务结构 complete 均不单独证明回答切题**。

### 定位与实测

全部经真实 Workbench HTTP 路由的进程内 ASGI TestClient；独立 fixture、users、Episode 目录，无 provider、禁 Keychain，Python 网络审计覆盖子进程。不是浏览器 E2E，也不是 OS 级网络沙箱。

| 二轮问法 | 初始 frame | 实际任务判定 | 公开答案 |
|---|---|---|---|
| 那它的主要风险和下一步验证是什么？ | `concept_definition` | `complete` | 有公司名；沿用深挖模板 |
| 那它有哪些主要风险，下一步该怎么验证？ | `general_finance_qa` | `missing` | `direct_answer` 缺口，无公司名 |
| 那它的风险呢？接下来怎么验证？ | `general_finance_qa` | `missing` | 同一缺口、逐字相同正文 |

[实测] 三种均继承正确主体/专项 owner。原句被定义后缀识别成概念题，附加 `direct_definition`；另外两句附加 `direct_answer`。后者与专项的 `direct_assessment` 同时存在。

[实测] `research_contract.build_turn_intent` 合并前后要求，`rebase_task_frame` 保留这些字段；`conversation_orchestrator._specialized_owner_required_outputs` 原样投影。已有 `_LEGACY_OUTPUT_ALIASES` 声明 `direct_answer→direct_assessment`，但专项路径没有采用 `_merge_frame_outputs` 的去重规则。`task_fulfillment._claim_candidates` 给 `direct_assessment` 三条候选，给 `direct_answer` 零条，最终 `missing/no_candidate_claim`。

[实测] 仅在目标槽位已存在时去掉重复 `direct_answer` 的反事实重算，另外两句从 missing→complete；仍保留 `evidence_boundary`。**反事实从未返回产品**，实际公开失败正文不变：

- 原句公开正文 SHA256：`7ae8358ff3aa3fda1df0c9e2613b9bfd890732885634b42ad12f295c9c9683fb`。
- 另外两句公开正文 SHA256：`32ce560097813cddf6569e61e4ee60c3b0ec376b11535b10996330bda45e8e7c`，与 PR16 旧失败相同。

[实测] 先在本助手指定 Python 环境运行，再借用发布方已存在的锁版本解释器只读复跑，三种判定、正文哈希和七个源码哈希均一致。因此本例不能仅归咎于本助手环境的 httpx 漂移。未安装或更改任何依赖。

[限制] 原句的 `direct_assessment` / `supporting_evidence` / `direct_definition` 都能被同一条 `ONTOLOGY` 研究范围摘要满足。公开稿确实含风险与下一步栏目，但有重复公司段落和模板化内容；本轮没有独立完整答案评分，不能断言“完全没答”，也不能据 complete 签内容达标。此发现证明候选仍有问题，不证明由本次发布补丁新引入。

### 检索与修复方向

本地规范 `harness-reference@gitea/main:849c62090b6f7e83eb0c99a0b15da7344a5a82fe` 的 `DESIGN-stack.md` 和 `PLAYBOOK.md` 已完整读取，固定副本与该 ref 的 SHA256 一致；三筛要求减去对输出形状的不必要管辖权、保留事实输入边界。这里只把它当评审判据，不当自然模型效果的第二份证据。

不直接给发布线补代码，避免与 owner 冲突；不 cherry-pick 整个 PR16 来救这句，两个补丁栈不同。后续应在单独认领的产品切片中统一输出身份，并验证本轮诉求与正文的对应关系。负例至少含：目标槽位不存在不得去重、真正缺内容仍拒收、不同主体/转题、无 provider 降级、独立要求不得误删。继续保留原 desktop/tablet/mobile 断言，并加入同义追问，不放宽旧断言。

## 5. 实际验证与不能转签的读数

私有证据根：`/Users/a77/.finance-runtime/reviews/harness-alignment-20261002T080000Z/`。

| 证据 | 来源 / revision | 结论边界 |
|---|---|---|
| `release-related.json/.xml/.log` | 本助手独立执行，干净 `2aea7c27e` | 证据补读、Episode、子研究、收件箱、快照及 conformance **320 passed / 6.04s**；不是全仓 |
| `ruff.log` | 本助手，干净 `2aea7c27e` | 全仓 Ruff 通过 |
| `probe-related-dirty.*` | 本助手，未提交量具候选 | **97 passed / 1.21s**，保留，不冒充提交收据 |
| `probe-related-committed.*` / `probe-receipt-check.log` | 本助手，干净 `ddba3fb7d` | 量具 CLI 六例及比较器相关四文件合计 **97 passed / 1.31s**，收据核过；不是发布候选全量验收 |
| `committed-{exact,natural,short}/` | 已提交量具→干净发布候选，本助手 Python | 三种追问对照；`committed-local-default/` 另验证旧默认入口仍复现 PR16 失败 |
| `locked-{exact,natural,short}/` | 同量具/同候选，发布方现有锁版本 Python | 三种判定与正文均复现；每次新模型/网络尝试 0 |
| `committed-followup-comparison.json` | 两解释器原件对账 | 判定、正文、源码指纹一致；不是新评分器 |
| `owner-snapshots/release-summary.json` / `release-pytest.json` | **发布方产物，非本助手重跑**，干净 `2aea7c27e` | Python **19731P / 99S / 2X / 0F / 0E**，collected=19832；来源 SHA 核过 |
| `owner-snapshots/release-frontend.json` / `release-e2e.log` | **发布方产物，非本助手浏览器验证** | frontend 命令均 exit 0，E2E **34P / 2S**，日志 SHA 核过 |
| `owner-full-receipt-check.log` | 本助手先用共享 Python 校验发布收据 | 正确拒收：解释器/依赖指纹不同；不是测试失败，不覆盖此原件 |
| `owner-full-receipt-matching-env.log` | 改用收据原解释器，仅执行校验器 | `--require-full-scope --expect-revision` 通过；只证明这张作者收据的成立条件，不替代独立全跑 |

量具新增 `--repo-root` / `--questions`，核 import 根并记录前后 SHA/脏状态、解释器和源码/量具哈希；证据目录必须新建。该工具依赖本项目 owner/fixture，不登记成跨项目通用量具。测试只检 CLI、代码根选择和证据不可覆盖；真实离线回放另外留证，不能把 CLI 单测写成端到端回归。

复跑示例（从量具所在仓运行；目标须另建固定 SHA 的干净树，输出必须为新目录）：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/probe_owner_followup_contract.py \
  --repo-root <fixed-release-tree> \
  --questions '请个股深挖英维克的液冷业务' '那它有哪些主要风险，下一步该怎么验证？' \
  --output <new-evidence-directory>
```

## 6. 对“弱模型发挥好、强模型有空间”的验收界线

- 支持继续：增加可理解的工具、按需补读、错误反馈和真实来源结构；模型仍决定何时补读、如何解释、何时结束。
- 不支持据此宣称收益：这次未发真实模型请求，没有强弱标定、同题同数据同可比预算的模型×引擎四格，也没有留出题或多轮质量证据。
- 评测线自己已记录旧 scorer 会把指标错配的 D1 答案打满分；兼容运行不是内容评分可靠性。下一真实四格由其 owner 冻结全文评分、完整 HTTP/流式路径、父子物理请求账、同池串行和绝对预算。本助手不再发第二套实验。
- 强模型是否被限制，要看换强模型后能否利用额外证据/工具并提高正确性，而不是允许它越权或伪造事实；弱模型是否受益，要看逐题错误减少且无回退，不用总分抵消严重退步。

独立验证：本助手未参与发布产品实现，使用真实代码路径、结构化 trace、公开正文及自动断言复核；已读作者文档，**不是盲评，与作者模型是否独立未核验**。量具修改由本助手自验，也不冒称量具得到第二方签字。没有用自然模型裁判本轮答案质量。

成立条件：tree=`/Users/a77/fwp-wt-harness-release-qc-1002`（检验期间存在且干净）；revision=`2aea7c27ed469530bc73fb232e65830acc754647`；dirty=false。主解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13，指纹 `e1c50cb821a30f00`；doctor blocked（httpx 0.25.2 vs lock 0.28.1）。对照解释器 `/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`，收据指纹 `66726d345bf37ce5`。正门：AGENTS、`docs/agent-product-door.md` 相关入口/引擎/补读段、两线交接及源代码；design_ssot=`gitea/main@849c62090b6`，已核哈希。复核树代码地图 empty，不用它断言架构完整；未查当前生产，也未执行远端 CI。

**本轮 0 新模型请求；未推送、合并、部署、改业务库或共享依赖。发布全量绿是已核条件的作者事实，同义追问缺陷是独立新事实，两者必须同时保留。**
