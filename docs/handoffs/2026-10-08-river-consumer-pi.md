# 市场历史镜头：Workbench 正门与 pi 消费接缝

## 背景与边界

用户要求在 PR #75 的工程回归之后，继续验证研究底座能否被真实调用和消费，再让 pi 尝试消费，写手保持 GLM 系列。
前置工程收据属于 `b7a5bcf3b`，不能移签新代码；原轮次只验证 Episode 首个模型接口与 B 合成接口，未走完整 Workbench 会话入口。
本轮从该版本另开 `feat/river-consumer-pi-1008`（工作树 `~/fwp-wt-river-consumer-pi`），不修改 PR #75 原树。

本轮代码 **`b1c709de65ee55b5a8c289d3ca3a792b25d8952d`** 已本地提交。
未推送、建新 PR、合并、部署、重启服务、写生产数据库或用户画像，**真实模型调用为零**。
沿前轮授权边界，真实/付费模型及生产操作分别待确认；已告知用户下一步拟用现有 GLM 做小样本，而非更换写手或改默认配置。

## 按发现顺序

1. 确认 `market_history_context.market_history_blocks()` 已是 A/B 共用的只读接缝。复用其两块完整文本，不再复制研究计算、候选筛选或时间语义。
2. 新增 `intelligence/history_context_cli.py`：数据库与截止日显式输入；日期/预算校验、缺库不创建、JSON 信封、逐块内容哈希、整块输出预算。
3. 新增 `integrations/pi/market-history.ts`：注册 `finance_market_history`。模型只传 `as_of`；代码根、解释器、库由操作人环境变量提供。无 shell 字符串拼接，子进程不继承模型密钥和用户态变量。
4. 从 `POST /api/conversations`、messages 到真实 orchestrator/adapter/Episode 装配，替换最下游 `GLMModelClient.complete()` 捕获完整镜头，返回故意失败。
   首次测试错把 `Run.status=completed` 当成伪成功；实际报告 `partial`、`llm.used=false`、降级说明均在。修正的是**测试对状态的理解**，没有改业务状态机。
5. pi 使用真实 CLI 和原生工具执行循环。脚本 provider 发 tool call，工具真实启动 Python 计算，再到第二轮 provider 收取完整工具结果；终稿仅输出哈希回执。
   这证明宿主调用/传输合同，不证明 GLM 或金融答案质量。六个场景分别验证成功、非法日历日、缺库、未配置、超长输出、坏 JSON。
6. 加强协议形状/块顺序/截止日/等级/哈希校验；JSON 解析失败不用异常原文，避免坏输出带入私有路径；超长则整体拒绝，不留“前半表成功”的误导。
7. 加入合成库前后哈希、子进程环境标记、启动前取消、Workbench 网络尝试计数和交付收尾等待。网络错误即使被底层吞掉，测试也会在最终计数处失败。
8. 固定代码提交后，在干净 revision 重跑扩大定向测试、Ruff、TypeScript、收据检查和代码地图。pi JSONL 与 Workbench 临时产物保存在私有测试目录。

## 决策与被否方案

| 议题 | 选用 | 否决 / 理由 |
|---|---|---|
| 外部接入 | pi 原生工具 → Python JSON → 共享接缝 | 不另造 HTTP/MCP 服务或研究引擎；本机试验无需服务生命周期与第二套计算 |
| 调用权 | 模型只选截止日，路径由操作人配置 | 不给任意 SQL、路径、shell；避免验证任务升级成通用数据库访问 |
| 证据运输 | 两块原文+INFERRED+内容哈希 | 不手贴摘要冒充工具消费；哈希只证身份，不能升成事实认证 |
| 输出预算 | 48KB UTF-8 整体拒绝 | 不使用截断到前N行的通用方案；读数不能脱离来源/时间限制 |
| 超时 | 共享30秒启动预算+35秒子进程超时/取消 | 不宣称底层 deadline 是查询硬取消；不改 Workbench 原预算 |
| 凭证范围 | Python 子进程环境白名单 | 不全量继承 pi 环境；这仍不是 OS 沙箱，代码根与解释器必须可信 |
| 离线验收 | 真入口/真工具循环，provider 替身 | 不以 mock 算法证明装配；替身也不能代签真实模型利用 |
| 成功判断 | 终态+业务报告+实际内容分开看 | 不只看进程 exit 0 / Run completed；pi JSON 模型失败也可能 exit 0 |
| 新宿主依赖 | pi 测试可选，缺宿主明确 skip | 不为 Python 项目自动安装全局 pi；CI skip 不称 pi 验证通过 |

## 收据

私有根：`~/.finance-runtime/reviews/river-consumer-pi-20261008/`。不提交原始研究材料、合成库或运行 JSONL 到公开仓。

| 验证 | 原件 / 身份 | 结论 |
|---|---|---|
| 初次接口测试 | `consumers-first.log` | 12P/1F；错误预期 transport 必须 failed，非镜头丢失 |
| pi 初次原生循环 | `pi-offline-first.log` | 六场景通过；脚本 provider，不是 GLM |
| dirty 扩大 | `expanded.log/xml` | 549P；后续增加缺表场景及测试护栏，不移签 |
| 最终干净代码 | `fixed-code.log/xml`，`b1c709de6` | **550 passed / 0 failed / 0 skipped**，1条既有 TestClient 弃用警告；明确是定向，不是全仓 |
| 身份收据 | `~/.finance-runtime/test-receipts/20261008T014641Z-b1c709de-be1586b593c6.json` | `--expect-revision b1c709de… --base-drift-max 0` 校验 exit0，见 `fixed-code-receipt-check.log` |
| 静态 | `fixed-code-ruff.log`、`fixed-code-typescript.log` | 全仓 Ruff；两份 TS 的 strict/noEmit（skipLibCheck）通过 |
| 提交门 | `code-commit.log` | 实际 pre-commit 通过，含层级、路径、注册可达性及目录保鲜 |
| 注册表 | `registry.log` | exit0；未改现有工具注册表 |
| 地图 | `fixed-code-map-status.txt` | structure ready `n=38952 @b1c709d`；非语义召回验收 |
| 原生消费证据 | `fixed-code-tests/test_pi_native_tool_loop_*/events.jsonl` | 成功例完整结果哈希 `f1052b77997d821425b8b141dd87fb3a29126860e9f4a791111b646d8eb866e6` |

解释器：目标树 `.venv-workbench/bin/python`，锁定 Python 3.12.13；pi 0.87.1，Node 26.0.0，TypeScript 5.8.3。
TS 编译器复用前轮工作树前端依赖，未新装包；配置原件 `tsconfig.json` 留私有收据根。
私有能力图谱/项目索引已回写此续作范围：graph audit 前后 exit0，新节点为分支 PENDING；
vault lint 前后均 exit1，同样48条存量 ERROR，新增/移除0，不称整库 lint 绿。

550项目标：`test_history_context_consumers.py`、`test_pi_history_bridge.py`、`test_river_*.py`、`test_market_regime_analogs.py`、`test_agent_episode.py`、`test_continuous_turn_adapter.py`、`test_asof_prefetch_*.py`、`test_workbench_conversation_integration.py`、`test_financial_publication_integration.py`、`test_e2_material_turn_delivery.py`（均在 `intelligence/tests/`）。新增消费者两文件合计20项，pi其中6项。

## 未验证与下一步

- 尚无真实 GLM 的 tool call、工具后模型请求或金融答卷。待用户确认模型调用与数据发送范围，先合成库验证利用，再经授权只读真实数据验证答案；都记录实际 provider/model、时间/调用上限、输入哈希与原始终稿。
- 不开启全量私有上下文：pi 仅白名单工具，停其他扩展/技能/上下文文件；真实调用不得加载 `tests/offline-provider.ts`。启动配方及判读规则在 [`integrations/pi/README.md`](../../integrations/pi/README.md)。
- Workbench 完整入口仅验到替身模型接口及降级交付；未跑真实作者/判官或多轮材料消费。无前端/E2E重跑、无本轮全仓或CI收据，前置 #75 全绿不移签。
- 只做启动前取消断言；尚未故意压满35秒超时或对运行中的 DuckDB 做取消压力测试。可信代码场景的子进程信号不是操作系统隔离边界。
- 所有新运行使用合成库；前轮真库可计算收据不能称这次 pi 已用真库。教学特征、用户判断及环境剧本闭环没有因此接入。
- 两组候选仍独立；日期截断、单cutoff PIT和逐日历史可知性仍分账。后续金融审查须复算解释，不能只查免责声明关键词。

## 工具沉淀盘点

重复消费验证已落正式 pytest 与 pi 测试夹具，没有把一次性探针变成另一个研究框架。
复用了既有收据检查、注册表、地图和提交门；本轮没有新增通用门禁缺口。
“终态不代签业务成功”“验到消费者下一轮请求”沿已有证据卫生原则，不重复造知识笔记。
真实金融质量仍需要语义复核，不能把是否提到某个词升级成自动通过判据。
