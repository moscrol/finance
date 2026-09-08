# 在途交接 · docs/finance-agent-bp

> **2026-09-04 已合入**：PR #584 → `gitea/main=c6e702a6`（分支尖 `ead7366d`，纯文档 11 文件，用户确认后合）。合入后 8792 不必切。
> 本分支自己的 main-tip 批次门禁没跑成（等其他 agent 的 pytest 时 shell 会话结束、等待脚本被带走）；但 #23 执行方在含本次合入的合并点 `03259062` 跑了全量门禁 **7783P/0F/15S/1x**（收据 `20260905T021432Z-03259062.json`），代码与 main 逐字节同源，视为已覆盖。
> **09-05 派单结果**：#23 → PR #593（`feat/judge-token-usage`，首个全口径成本 ¥0.4902/次，判官 grok CLI 有 usage）；#24 → PR #592（`feat/checkpoint-rule-id-bias`，真库 `bias-scan`：late_streak 2 / post_miss_streak 34 / revenge_reentry 9 / rule_not_firing 83 不适用）；#25 → 分支 `feat/historical-replay-engine`，真跑 160 次调用出首份重放读数（`memory_bucket` 全 unknown：glm-5.2 官方未披露截止日；臂间差 strict −2.6 pt / trade_date_only **+11.2 pt**），收尾中（schema 两加法 / 交接 / PR）。三张都**未合 main，等用户确认**。
> 下文为合入前原状，供溯源。

## 这个分支做什么

两件纯文档：
1. 创业比赛 / 孵化器申请用的商业计划书 `docs/bp/2026-09-finance-agent-bp.md`（12 章 + 路演页映射 + 来源 + 待填清单）。
2. 用户 2026-09-04 提出的新方向「历史行情 / 题材编译成结构语言，用历史成功率给纠偏设统计门」的设计稿 `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` 与可分发 P0 工单 `2026-09-04-methodology-backtest-p0-workorder.md`（INDEX #21）。

## 决策与被否方案

- BP 定位：主线卖「证据可追溯的个人研究工作台」面向半专业个人投资者；harness 方法论写成壁垒页不单独卖；机构版放第二阶段。被否：单卖 harness 工具包（是文档不是产品）、直接 To B（无渠道、单人）。
- 合规红线：不写「AI 荐股 / 智能投顾」；产品边界三个不做（不选股、不给买卖时点、不预测价格），依据 2012 荐股软件规定与 2026 防非宣传月口径。
- 数据源：当前会话抓取不作商业叙事，BP 写三步合规化路线。
- 方法论回测形态：规则标签（不做图像识别 / 学习表征）、声明式 JSON → 参数化 SQL（不给 agent 开 run_sql，沿 2026-08-20 决策）、旁路库（不改主 schema）、Wilson + 基准率 + 前后半段四态（不用贝叶斯起步）。
- 形式默认：BP 为 Markdown 长文 + 页映射（问答工具两次回传失败，未拿到用户对形式 / 团队的明确选择，按默认走并在 BP 附录 C 列占位）。

## 当前状态

**2026-09-04 第八轮后**：分支已 `merge gitea/main@5c7fe2eb`（含 P0 / P1 三个方法论回测 PR），INDEX 撞号已解（判官 token 工单 #22 → **#23**），BP v0.5 / 设计稿（含新 §10）/ deck 已回正为「已上线 + 首批读数」。未合 main。以下为各轮累积记录。

BP 中数字：仓内为 2026-09-04 只读核数（52 表 / 413 交易日 / 4,599 实体 / 124 纠偏 / 83 可证伪点 / 7,386 测试通过），外部 21 条来源见 BP 附录 B。

**2026-09-04 第二轮（BP v0.2）**：用户令「继续 BP，设计稿另派 agent」。改动全在 `docs/bp/2026-09-finance-agent-bp.md`：
- 修正：技能数 38→37（`skills/` 38 项含 `lib/`）；「前瞻复盘台账约 50 个交易日」无出处→改为「双盲前瞻答卷台账 23 个交易日（2026-06-30→09-03）」，且该夜跑 09-03 已退役（`ledger-map.md`），对外不得说「每日在跑」；Rogo Series D 日期 2026-09→**2026-04-29**（PR Newswire）；Hebbia 改引 TechCrunch 2024-07-09；Perplexity 改引官方定价页。
- 新增第 8 章「市场进入与获客」：素材来自 `docs/marketing/{products,claims,personas}.yaml`（三人群 + 渠道 + 可说不可说）、记忆底座 `finance-research-site.md`（Astro + Cloudflare，GEO）、`vidio.md`（短视频）、`finhot.md`（开源阅读器，抓取已暂停）；漏斗 候补 200 → 注册 2,000 / 付费 50–200 → 注册 1 万 / 付费 1,000 → 付费 1 万；CAC ≤ 250 元、LTV/CAC ≈ 4–6。
- 新增第 12 章「财务预测」：全假设模型，收入按年内平均付费用户计（300 / 2,500 / 7,000 × ARPU 1,500），三年净利 −113 / −40 / +192 万元，累计最低 −153 万元（第 2 年末），约 5,500 付费用户盈亏平衡，敏感性以转化率与 ARPU 为最大；免费层推理成本记入市场费用而非销售成本。融资章用途比例由 40-30-10-20 改为 55-15-10-20（对齐模型 18 个月支出结构），建议融资 200–300 万元（6 个月小额口径 80–100 万元）。
- 新增附录 E 评委问答预演 12 问；附录 A 页映射扩到 17 页并给 12 页压缩方案；附录 C 新增 3 项待拍板；附录 D 新增 5 行核对路径。
- 章节重编号：原 8–11 → 9–13，全文交叉引用已核对（`rg "第 [0-9]+ 章"` 逐条过）。
- 未做且为什么：没把 `market_feature_store/exports/*-daily-agent.md` 当产品样例放进 BP——那是内部研究队列产物，含个股名，脱离上下文像荐股；demo 截图仍留用户填。

**2026-09-04 第三轮（用户再令「继续」）**：
- **推理成本实测替代占位**：读生产用户目录 `linxiaoqi5111/runs/*/continuous-episode.json` 的 `outcome.usage`，356 个 completed run（08-12→08-31，全 `ask`，`continuous_glm`）：输入中位 37,504 / 均值 48,292 / p90 79,988，输出中位 1,403 / p90 2,930，输入占 96%。按智谱官方定价页（新增 B-22）旗舰档 8/28 元折算：中位 0.34 / 均值 0.43 / p90 0.72 元；判官链（grok CLI）token 不在此字段，估加三到五成 → 全口径 p90 ≈ 1 元 = 模型假设，属保守上界。写进 §7.3 / §12.1 / 附录 E 第 8 问 / 附录 D 计数方法。顺带两个产品判断进了正文：96% 是重复上下文→提示词缓存（命中价 1/4）是最大降本杠杆；创始人 20 天 495 次远超每年 240 次假设→Pro 必须日配额。
- **deck 落盘** `docs/bp/2026-09-finance-agent-deck.md`：17 页 Marp Markdown，每页 HTML 注释=约 30 秒讲稿 + 视觉建议，文件头写了 12 页合并方案与导出命令。母本为准，数字先改 BP 再同步。
- 114 个 run 无 episode 文件（引擎 B / 旧 schema）、17 个 completed 但 usage=0，未计入实测；判官侧 token 需另加埋点才能量——可作 Alpha 期指标。

**2026-09-04 第四轮（BP v0.3，靶心改变）**：用户澄清「不是融资 BP，是想法验证阶段，要入驻 OPC（一人公司）社区，对方要一份 BP + 路演」。此前 v0.1–v0.2 按「创业比赛 / 孵化器」默认写，融资章与三年 8 人模型对不上靶。查了 OPC 社区入驻通行口径（B-23 opcquan 指南：梯队「有收入 > 有用户 > 有 Demo > 有 BP > 只有概念」，Demo 阶段要体验链接 / 1 分钟录屏；B-24 极客部落 12 项评审维度）后改写：
- 新增「一页纸版」（可直接贴申请表）；阶段自评「有 Demo + 自用数据，尚无外部用户」写进头部。
- §1 执行摘要重写为「一人公司 + agent 团队 / 只验证一个假设 / 不融资 / 向社区要什么」。
- §3.5 新增「给评审的体验入口」：邀请码账号（身份门已有）+ 录屏建议（拒答不存在日期、登记判断次日回检）。
- §5.1 SOM 行改为一人公司三条线（自给 10 / 可持续 120–150 / 小而美 1,000）；「1 万付费」降为附录 F 参考。
- §8.4 漏斗按一人产能缩：候补 100 → 注册 500 / 付费 50–200 测试 → 12 个月付费 120–150 → 24 个月 1,000；强调内容由 agent 生产人审。
- §10 改「现状与验证计划」：V1–V4 每段写通过线与停止线（V1 核心判据=≥ 半数用户主动登记判断；V2=转化 ≥ 10%），§10.3 两条退路（收缩产品 / 转方法论咨询）。
- §11 改「一个人怎么带一支 agent 团队」：六岗位分工表（规划 / 执行 / 验收 / 生产运行 / 内容 / 记忆）+ 四条纪律；§11.3 不雇佣、按需合作；注册状态待填。
- §12 改「一人公司账本」：月固定约 1,000 元（两项待填）；月贡献 160 = 180 − 20；自给线 6→取 10；可持续线 (1,000+2,000+0–2,000+15,000–20,000)/160 = 113–156 → 120–150；12 个月现金逐月累加最低点第 8 个月约 −1.5 万至 −2 万、第 11 个月累计转正；敏感性对可持续线。**结论「验证只需约 2 万元 + 12 个月，所以不融资」**。
- §13 改「入驻诉求与回馈」：要（算力额度 3–5 万等值 / 合规导师 / 种子用户 / 数据商对接 / 同行 / 工位待拍板）、给（方法论工作坊 / 开源 FinHot / 公开验证读数）、3-6-12 承诺。
- 附录 A 改为 12 页 OPC 映射并标注命中的评审维度；附录 C 按「申请当天就要」重排（目标社区要求、注册状态、体验链接、录屏排前）；附录 E 12 问改 OPC 口径（新增「什么阶段」「为什么不融资」「验证失败怎么办」「会一直是一人公司吗」）；**附录 F** 收纳 v0.2 的三年扩张模型（−113/−40/+192，融资 200–300 万只在走这条路时才需要）。
- deck 重写为 12 页（8 分钟；5 分钟精简讲法写在文件头）。
- 全文 M1–M4 → V1–V4 已 `rg` 清零；「融资」仅剩于 B-10/B-11 来源描述与「不融资」表述。
- 未做：没替用户选目标社区——不同社区表格 / 时长不同，附录 C 第一行等正式通知。

**2026-09-04 第五轮（申请表落地）**：用户给了《OPC 项目孵化申请表.docx》（创新国度 OPC 创业营，杭州；用户说杭州 OPC 注册很快；路演性质=分享项目、听投资人建议，**不是拉融资**）。
- 表结构：无表格、94 段、勾选框「□」与下划线都是纯文本、每个选项独立 run → 用 `/tmp/opc_form/fill.py`（临时脚本，不进仓）只改 `<w:t>` 文本节点填表，39 处替换；产物 `~/Downloads/OPC 项目孵化申请表-已填草稿-2026-09-04.docx`（二进制不进仓），textutil 回转 + minidom 解析验证通过。**python-docx 不在 venv，故走原生 zip + regex；ElementTree 会重写命名空间前缀（mc:Ignorable 引用前缀名），所以没用它。**
- 文字母本 `docs/bp/2026-09-opc-application-form-answers.md`：每格填法 + 勾选理由 + 提交前自查。诚实项：「已上线 / 已有用户」勾了但加括号注「自用生产运行、尚无外部用户」，Q6 只勾「已上线」；「资金 / 资本支持」不勾；「形成收入 / 0-1 验证」不勾（V2 才验）。简介 96 字（≤100）。
- BP：头部用途改为「创新国度 OPC 创业营（杭州）」；新增 §13.4「路演上想请教的三个问题」（付费点 / 合规路径 / 一人公司边界）；附录 A 第 12 页、附录 C 首行、B-23/24 注同步。deck 最后一页改为「要 / 给 / 承诺 + 三个问题」。
- 待用户：姓名电话微信签字日期；所在城市「杭州」确认；身份类型若单选保留「AI创业者」；场地空间要不要勾；产品名；Demo 链接 + 评审邀请码；网站链接；1 分钟录屏；路演时长（决定 12 页还是 7 页讲法）。BP 导出 PDF 时删附录 D。

**2026-09-04 第六轮（BP v0.4，壁垒重构；用户拍板「证据可追溯是入场券不是护城河，上限是沉淀进去的 know-how」）**：
- 标题「证据可追溯的…」→「**会校准你判断的 A 股个人研究工作台**」，副题「把自己的研究方法变成可回测、可校准的系统；结论带证据只是地板」。
- §2.2 三个恨点按痛排序：判断不被校准（主攻，没人服务）→ 千人一面 → 编造（地板）；加创始人自用数字作「我先被这个痛点折磨过」的证据。
- **第 4 章重写为三层**：4.2 地板（入场券，不当卖点；能力是入场券、纪律下攒的存量是资产——板块快照分代举例）；4.3 上限 = 编码进系统的 know-how 六层表（结构语言 / 题材叙事图谱 / 方法论库共享层 + 私有层 / 证伪库 / 按阶段条件化 / 专家纠偏数据，各标护城河类型与现状）；4.4 抬上限的机制（升格流水线 + 统计门——**方法论回测定位为「壁垒生成器」**、评测体系、harness、**共享层合规硬门**：登录可见 / 必带样本量与 CI / 只到板块题材层 / 不用于对外内容 / KOL 匿名为策略族）；4.5 反定位与诚实品牌；4.6 护城河类型对照（切换成本 / 独占资源 / 流程能力 / 反定位 / 弱网络效应 / 品牌；证据可追溯、PIT、RAG、Agent 框架、模型明列「不是护城河」）。
- §6.2 加注「第一行附来源是地板，差异在后四行」；§6.3 改名「反定位」。附录 A 第 6 页、附录 E 第 6/9/10 问同步，新增第 13 问「证据可追溯 Perplexity 也有，壁垒是什么」。附录 D 加两行（结构语言现有定义出处、快照分代）。
- deck：封面、第 2 页（痛点排序）、第 6 页（三层表）重写，讲稿同步。
- 申请表：项目简介（100 字，卡满）、核心痛点、核心优势三格按新口径重写，`/tmp/opc_form/fill.py` 重跑，`~/Downloads/…已填草稿-2026-09-04.docx` 已覆盖并验证；`…-form-answers.md` 同步。
- 全文 `rg` 确认「三张牌 / 壁垒一二三」清零；「证据可追溯」只剩地板 / 入场券语境。

**2026-09-04 第七轮（用户令「执行补充」：三件我方可落的配套）**：
- **设计稿 P1 补三条产品约束**（`…-structured-history-design.md` §6 P1）：规则 `scope∈{shared,private}` + `owner` + `source_perspective`；证伪库当资产（`methodology/refuted/` 单独落 + 台账登记，P1 `report --refuted` 按阶段汇总）；共享层合规硬门四条（登录可见 / 必带 N 与 CI / 只到板块题材层 / 不进营销内容，KOL 匿名为策略族）。**P0 工单 §2.3 同步补占位字段**（schema 三字段 + 收据带 `scope`/`entity_type` + refuted 收据同格式、文件名含 verdict），不实现逻辑。INDEX #21 一句话更新。
- **新工单 INDEX #22** `2026-09-04-judge-token-usage-workorder.md`（P1 小单）：判官 token 记进 `LLMCallLedger`（不新开账本、不改 `complete()` 三元组契约）；`_post_chat` 读 usage（双命名，复用 `glm_agent_runtime._message_token_usage` 逻辑但需下沉到 services，layer_audit 禁反向 import）；grok CLI **先探明** stdout 有无 usage，无则估算并全程带 `estimated` 标记；`purpose=judge` ContextVar 包住 `episode_semantic_verifier` 三处 `_judge_request` 之后的调用；`continuous_turn_adapter.metrics.judge_usage` 差分汇总；读者 `intelligence/eval/research_cost.py`（照 `tool_hunger.py` 形状）+ 价目表 `intelligence/eval/pricing/llm-prices.json`（手工核对、带 `checked_at`）。证据路径行号读自本分支 2026-09-04。
- **评审体验账号清单** `docs/bp/2026-09-opc-reviewer-access-checklist.md`：先拍板 A 录屏 + 现场演示（默认）/ B 时限账号 / C 脱敏账号（未做）；B 的步骤抽自 `hosted-alpha-gate.md` §1–§3（向导、Access 先于 DNS、启动器 env 建议值 配额 5、名单热重载、七条验收）；§4 录屏脚本；§5 收尾。**关键发现：运行手册 §4.1「知识库未脱敏」——评审账号会看到私有研报正文**，故 BP §3.5 / 一页纸 / deck 第 5 页 / 申请表补充材料 / 附录 C 全部改为「录屏 + 现场演示为默认，账号可选待拍板」。
- 顺带：一条 `sed|rg|ls` 组合命令在本树挂起 41s 被手动 kill（与此前 `git fetch`/全树 `git status` 挂起同现象，原因未查），后续用 Read/Grep 工具替代，不影响产出。

**2026-09-04 第八轮（接手；合 main、改号、状态回正、理念落稿）**：
- **发现本分支文档已过时**：P0 工单（#21）在本分支还写「⏳ 待派 / 未实施」，但当天 19:50 已由另一 agent 实施并合入 `gitea/main`（PR #573），随后 P1 两刀也合了（#576 统计门 + `min_n` 2→10；#581 `propose` + 日期配对基准率）。实施方直接从本树读了设计稿与工单——工单「可独立分发」成立。
- **撞号**：本分支把判官 token 工单登记为 INDEX #22，而 main 上 #22 已是 RAG worker 内存工单 → 合并冲突。处理：`git merge gitea/main`（合并提交 `731cd4df`），INDEX 手工解决：#21 改为三个 PR 的已合状态 + 剩余 P1；#22 保留 main 的 RAG worker；**判官 token 工单改为 #23**（扫过全部 793 个本地 / gitea ref，#23 无人占用）。工单文件名不含号，正文未动；其代码锚点（`llm_refine.py` 440/452/505/683/742/762、verifier 1071/1286/1427、adapter 477/1430–1488）对 `gitea/main@5c7fe2eb` 逐条复核无漂移；开着的 PR #556（run-credits）不碰 `llm_refine` / `grok_cli_judge`，无重叠。
- **设计稿回正**：头部状态改「P0 已合 / P1 前两刀已合」；§3.4 表加「结果」列；§6 P0 七条各附真库读数与三处实施偏离（`mainline_flag` 取 `fact_mainline_sector_daily`、`market_stage` 用真库实际值、`data_gap` 单独成表）；P1 拆 ✅ / ⏳；§8 成立条件更新。
- **设计稿新增 §10「学习闭环路线图」**：把用户当晚六句理念（理性决策巩固复现 / 非理性规避 / 先喂经验 / 再发现规律 / 回顾历史理解为什么 / 站相似节点推导拿后续验证）逐条对到仓内实物——其中四句已有实物：①统计门 + `promoted_to_code`，②可证伪点校准，③`propose`，⑥ `fidelity_replay` 历史重放（2026-07 已建，`input.snapshot.json` / `outcome.snapshot.json` 物理分离）+ 双盲前瞻答卷台账。写死四条守门：理性 / 非理性按**过程**定义不按结果（否则就是结果偏差）并给偏差目录 v1 四条；「发现」只能产出规则 JSON 进同一道门、发现窗 / 验证窗分开；「理解为什么」防事后归因（as-of 因果链 + 重放 / 回顾双模式差异量化）；「站节点推导」的两种泄漏——数据泄漏已有守门，**模型记忆泄漏（训练截止日）全仓无守门**，给三件（收据带模型截止日分栏 / 实体匿名化对照臂 / 与双盲台账按类别对账）。顺序建议把「发现」挪到闭环末端当产出。§10.4 给分期（新增 P1.5 重放引擎），**不派单不取号**。
- **BP v0.5**：§1 / §4.1 图 / §4.3 三格 / §4.4 / §6.2 矩阵行 / §10.1 / §10.2 V1 / §13.3 / 附录 D 两行 / 附录 E 第 6 问，全部从「规划 / P0 待交付」改为「已上线 + 首批读数」。**叙事选择**：三条种子规则全 `not_distinguishable`、种子规则 1 的 +10 点按事件日配对后归零——写成「统计门先打了我们自己」，作诚实品牌的自证（§4.4、附录 E 第 6 问、deck 第 6 页与讲稿）。附录 D 明写 BP 未重跑这些数字、对外引用前先 `report` 重出。
- **未做**：没有派 #23；没有动 `hosted-alpha-gate.md`；申请表母本与已填 docx 未动（这轮改的段落不在申请表三格内）。

**2026-09-04 第九轮（用户令：立 §10.4 的 P1 与 P1.5 单）**：
- **#24** `2026-09-04-checkpoint-rule-id-bias-catalog-workorder.md`：可证伪点加 `rule_id / rule_verdict / rule_receipt`（读者 `calibrate.by_rule` + `render_report`，unread-fields 门禁要求同提交）；`checkpoint register --rule-id` 用 `latest_receipt` 回显四态（照 `cli.py:885–899` 经验卡写法，**不拦截**）；新模块 `checkpoint_bias.py` 四条偏差 `late_streak / post_miss_streak / rule_not_firing / revenge_reentry` + `bias-scan`。核过的事实：`rg rule_id checkpoints.py` = 0；`register_checkpoint` 非测试调用方 5 处；`checkpoints.py` docstring 承诺只用标准库，所以目录另开模块。设计稿原拟「锚定」不可计算，换成 `rule_not_firing`（编译器窗口 `[D0, D0]` 取事件集）。
- **#25** `2026-09-04-historical-replay-engine-workorder.md`：重放引擎 `intelligence/eval/replay_engine.py`，两臂（命名 / 匿名）× 两车道（A 规则复现一致率对照编译器，零泄漏；B 双盲 `hypotheses[]` 格式前瞻假设，只 market / direction）→ `history_outcomes` / `market_actuals` 自动判分 → 复用 `checkpoints.calibrate` 出 `pit_grade × memory_bucket × arm × category × horizon` 分格（N<10 不出率）→ 与双盲台账对账。**只读核数发现的硬约束**：`fact_market_daily.updated_at` 最小 2026-08-12（整表重写过），严格 `updated_at` PIT 只过 17/413 日；每日快照 33 份（07-10→09-02，缺 07-21/07-28/08-04/08-06/08-25/08-31）；故 `pit_grade ∈ {strict, trade_date_only}` 定为一等字段，380 个历史节点只能弱边界。模型截止日表 `model_cutoffs.json` 只认官方来源，查不到填 null 视同污染。顺带规则 schema 三加法（`discovered` / `windows` 双窗 / `sharing` 占位）。
- **发现 P0 §2.3 占位字段从未实现**：那段是 21:07 补进 P0 工单的，P0 19:50 已合；`rules.py` `_TOP_KEYS` 无 `owner / source_perspective`，`scope` 已是实体范围对象。改由 #25 承接并改名 `sharing`。写进设计稿 §6 P1 与 §10.4。
- 发现双盲台账 `dual_blind_forecast.py manifest --perspective` 只是冻结清单（`duckdb_cutoff` 取当前 max），**不是** PIT 快照；历史重放的输入必须走 `fidelity_replay.build_input_snapshot`（加 `strict_updated_at` 参数，默认不变）。
- INDEX 加 #24 / #25 两行；设计稿 §10.2 第一条偏差名对齐、§10.4 指向工单、§6 P1 加占位字段未实现一条。
- **未做**：未派 #24 / #25。
- **合并前再同步（23:1x）**：`gitea/main` 期间又前进到 `47a4fcde`（PR #585 第三刀个股标签已合），再 `merge gitea/main`（`c6fc7669`）。发现**第四刀在途** `feat/methodology-backtest-p1-refuted`（`e520e31e`，未开 PR）已实现 `sharing / owner / source_perspective` 扁平字段 + 证伪库 + `report --refuted`——与 #25 原拟的 `sharing{level,…}` 嵌套块撞车，**#25 去掉该项**、schema 步骤改为第四刀合入后 rebase 再做；车道 A 只跑 sector / theme 规则（`stock` 现已是合法 scope）。#24 / #25 行号按 `47a4fcde` 重核（`rules.py` `_TOP_KEYS` 95 / `PROVENANCE_KINDS` 98 / `validate_rule` 266；`labels.py` 103–113；`outcomes.py` 46/48）。INDEX #21 补第三刀 ✅ / 第四刀 ⏳；设计稿 §6 P1 与 §10.4 同步。之前写的「占位字段从未实现」改为「P0 没做、第四刀补齐」。

## 未验证 / 已知边界

- 外部数字全部来自媒体转述或三方报告，未核对监管 / 中国结算原文；BP 已注明「口径以原文为准」。
- SAM / SOM 是估算与目标，口径写在 BP §5.1，未经用户确认。
- 定价三档为假设；第 12 章全部参数为假设，其中数据授权报价（30/60/100 万元）与人力全成本（30 万元/人年）最无依据，已列附录 C。
- 第 8.3 节三个入口的现状（短视频账号是否在运营、FinHot 是否纳入）未经用户确认，已标 `【待确认】`/`【待拍板】`。
- 第八轮写进设计稿 §6 / BP §4.4 / 附录 D 的实施读数全部**抄自三份交接**（`feat-methodology-backtest-{p0,p1-gate,p1-propose}.md`），本分支未重跑 `methodology_backtest.py`；对外引用前先在主树重出收据。
- §10 对「模型记忆泄漏无守门」的判断基于 `rg` 训练截止 / 模型记忆 / memoriz / cutoff：仓内只有 `task_frame.py` 检索地板（服务侧）与 `ceiling_leakage` 的 `post_cutoff_result`（基准冻结日，非模型截止日）两处近义，未发现评测侧对应物。
- 判官 token 工单（#23）的行号锚点只复核到 `gitea/main@5c7fe2eb`；派单时以 `rg` 重定位。

## 下一步

- **合 PR**：本分支已合入 `gitea/main`（无冲突残留），等用户确认后合 main。合入后 8792 不必切（纯文档）。
- 派 **#23** 判官 token 工单（分支 `feat/judge-token-usage`，从 `gitea/main` 新开树）；产出回填 BP §7.3 的 `【待填：Alpha 期含判官的全口径实测】`。
- 派 **#24**（`feat/checkpoint-rule-id-bias`）与 **#25**（`feat/historical-replay-engine`），三张单互不依赖可并行；#25 调 LLM 约 160 次，派前确认预算窗口。下一个空号 **#26**。
- 剩余 P1 中「个股标签」已有树 `fwp-wt-methodology-backtest-p1c`（分支 `feat/methodology-backtest-p1-stock-labels`，尚无提交），不要再开第二棵。
- 用户拿到目标 OPC 社区的正式材料要求后，按其表格 / 页数 / 时长裁一页纸版与 deck（附录 C 第一行）。
- 用户填 BP 附录 C 占位（注册状态 / 体验链接与邀请码 / 录屏 / 产品名 / 创始人 / 创始人目标收入 / 月支出两项 / 工位 / 数据商报价 / 入口现状）。
- BP 若要 PPT / Word，从附录 A 页映射压（17 页或 12 页两版方案已写在附录 A 下方）。
- CLAUDE.md 的「12 个工具」「31 个技能」两处已过期，本分支未动，待合并后另开小修。

## 踩过的坑

- **09-05/06 派单撞车**：三个执行 agent 的运行时都报「failed after relaunch recovery」，但它们其实还在跑（#25 是被模型用量上限打断，另一条对话「A 线」用同一上下文把它续起来了）。本线据「失败」通知给 #25 又派了一个收尾者，两个执行者在同一棵树 `/Users/a77/fwp-wt-replay-engine` 上先后 merge main、提交同两个报表文件，原执行者 hard reset 掉了收尾者的提交（blob 逐字节相同，读数未丢），收尾者随即按 AGENTS.md「同树两 agent → 先停」自行停手。**教训**：派单 / 接手前除开工三连，还要看 `git reflog` 最近时间戳与正在运行的 shell / transcript；「失败」通知不等于执行者已停。同一张单只能有一个 dispatcher。
- 主检出树在 `feat/content-ops-copilot` 且有他人 51 个未提交改动，故另开树 `/Users/a77/fwp-wt-finance-agent-bp`。
- 本机 `git fetch gitea` 与全树 `git status` 曾长时间挂起；本地 `gitea/main` ref 可直接用于 `worktree add`。
- shell 会话 cwd 不一定在仓内，git 命令要显式 `cd` 或 `-C`。

## 已验证

- 主库只读查询成功（`read_only=True`），四张表区间与行数已入 BP §9.1 与设计稿 §2.1。
- 代码地图查询确认无现成「标签层 / 方法论编译器」实现，只有 `backtest_sector` / `detect_turning_points` / 双红定义。
