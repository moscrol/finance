# Pi 原生 + Knevo Skill 层（验证臂）

这一入口在 Pi CLI 挂载常驻 `finance-mode` 和四个按需读取的专项，数据走与 8792 同源的工具注册表。
它是隔离验证入口，不改 8792、不写生产库、不持久化个人记忆。接入生产及质量放行另验。

设计：`docs/superpowers/specs/2026-10-09-knevo-skill-layer-design.md`。
当前读数：`docs/handoffs/inflight/fix-knevo-pi-runtime-1010.md`。

## 首答

先提交源码，选择新的树外产物目录。用工作区事实报告的 Python 解释器运行：

```bash
python integrations/pi/run_native.py prepare \
  --root <新产物目录> --db <源库.duckdb> \
  --question-file <问题.txt> --as-of 2026-09-30 \
  --today 2026-10-09 --rag-bindings <受管代际绑定.json>
python integrations/pi/run_native.py run --root <产物目录> --dry-run
python integrations/pi/run_native.py run --root <产物目录>
```

`prepare` 固定提交号、runner/kit/skill 哈希、APFS 只读克隆、问题、截止日、模型与调用上限，复制 RAG 绑定并固定端点摘要。
`run` 前后校验源码仍干净且这些输入未变；已经启动的目录不能重跑。真实验证使用受管 RAG 绑定，`off` 仅用于离线测试。
凭证从环境或现有启动器的 export 行读取；只支持字面密钥及受限的 `security find-generic-password` 钥匙串引用。
不执行启动器或任意 shell 表达式，不落盘密钥。未解析表达式在发请求前失败。

默认只验证方法论层。`prepare --second-look` 另开一次自检续写，`--subagents` 另开研究派单；它们是独立实验变量，按需分批验证。
二看或aligned会认领进程级 `finance.pi.continuation-owner`，与采用同键的reviewed-history修订互斥；
第二个所有者（包括同名副本）在首模型调用前拒绝加载，session_shutdown释放。没有续写的模式不认领。
这只协调遵守该约定的扩展，不是任意第三方扩展的隔离机制。
`finance_call.tool` 从冻结菜单生成枚举，数据集名只能放进 `args.dataset`，不会作为工具名发送。
工具桥对齐生产公开/审计边界：模型只拿公开证据、查询范围、缺口和领域状态；`telemetry` 与原始 trace 仅留本地审计。
晚于截止日而被扣留的材料不能从诊断字段重新进入模型。`pi-tools.jsonl` 同时保存原始 observation 和实际 model_observation，便于逐字核对。
子任务共享根模型/工具调用上限及绝对截止日，带相同工具参数说明，只能读取自身挂载的专项，不再派单。
失败、取消、长度截断、没有终稿的子任务都不作为成功结论；局部失败在主线程可见。

## 固定证据定稿

用于定位表达阶段问题，不重取数据、不沿用旧答案：

```bash
python integrations/pi/run_native.py prepare \
  --root <新定稿目录> --source-run <已有研究运行目录> \
  --delivery-style direct --delivery-skill finance-market-review \
  --turn-seconds 300 --call-cap 12
python integrations/pi/run_native.py run --root <新定稿目录>
```

`direct` 在干净上下文直接定稿；`aligned` 先生成可公开的主张/证据/范围表，再续写一次完整正文。
每种方式用不同的新目录。定稿必须指定 `--delivery-skill`，其完整正文由宿主在首个请求中注入；
`delivery_method_in_first_request` 从实际请求核对完整方法是否送达，不能用最终read次数冒充先加载。
源运行须完整、身份匹配且输入稳定；它的内容质量可以未通过。
证据包只包含实际送达的公开工具结果，保留诊断与缺口；旧稿、私有审计和审查意见不进入模型。
源原件、证据包和提示资产均做哈希校验，模型默认保持与源运行相同。
只有显式 `--author-model <id>` 才能做作者模型轴实验；`--model` 仍标识源运行模型，plan/RESULT分别记录源与作者身份，
实际响应必须匹配所选作者。没有自动模型回退，不能把换模型的结果当成同模型对照。
此模式不克隆DB、不初始化数据工具注册表、不访问RAG；Pi只开skill读取，桥接端也拒绝取数和重新授权。
`completed-drafts.json` 中 aligned 第一稿是工作表，第二稿才是最终正文；阶段正确不等于语义通过。
设计：`docs/verification/2026-10-10-frozen-evidence-delivery-design.md`。

可另加 `--numeric-checks`，从已有D4结构化输入生成确定性核算记录，并验证首请求完整送达。
它复用既有严格双红校验器，分开价格/成交方向、规则资格和完整组计数；没有全量字段时不从预览补造。
原始证据包不删改，旧市场总览的展示文字没有结构化列，不在核算覆盖内。
`numeric-checks.json` 带来源摘要且执行前后复算；计算正确不代表正文的资金因果、解释或假设通过。
在direct定稿中同时指定 `--numeric-checks --analysis-only`，程序会独立生成 `checked-facts.md`，
模型只生成 `pi/analysis.md`（`pi/answer.md`保留相同原文便于既有审计）；数字表不经过模型重写。
全量统计与已核预览分表，缺失保留未知。数字表、核算记录和原证据均在执行前后复算校验。
两份产物分别审查；`delivery_scope=fixed_numeric_document_and_unreviewed_model_analysis` 不代表解释已通过。
两阶段aligned未证明质量收益，仍只作显式诊断。设计：`docs/verification/2026-10-10-frozen-numeric-support.md`。

定稿另有可选 `--evidence-view factored`（默认raw）：相同的证据行元数据归并为公共字段，
重复正文用明确索引引用，但每个原字段与字符串均可还原。原始证据包不变，另存 `model-evidence.json` 和还原收据。
执行前后重新生成核对，实际请求必须带完整视图；这不是摘要、截断或语义过滤，也不继承内容质量认证。
设计：`docs/verification/2026-10-10-reversible-evidence-view.md`。
两份冻结题的实际总输入token减少约31%/33%，但内容仍未通过，默认仍为raw；不把可逆性当语义等价的效果证明。
结果与跨线续写协调：`docs/handoffs/2026-10-10-evidence-view-and-continuation.md`。

## 验证与产物

```bash
python -m pytest -q tests/test_pi_native_runner.py tests/test_pi_finance_extension.py \
  tests/test_pi_model_view.py tests/test_knevo_market_scope_cases.py tests/test_frozen_numeric_checks.py \
  tests/test_factored_evidence.py \
  intelligence/tests/test_knevo_skill_layer.py
```

Pi 子进程测试只连本机模拟接口，不调用付费模型。没有 Pi CLI 的环境会明确跳过子进程测试，不能把跳过算作已验证。
测试覆盖工具真实可见性与调用、skill 读取、自检停止、子任务参数传递和错误传播、读路径限制、冻结校验及完整 runner/bridge 往返。

真实 history 适配器的跨线测试也已入仓。两适配器尚在不同分支时，显式指定已审核的 #83 检出根；合流后默认从本树读取：

```bash
FINANCE_PI_HISTORY_TEST_ROOT=/absolute/path/to/history-checkout \
  python -m pytest -q tests/test_pi_finance_extension.py -k real_history
```

该测试覆盖二看/aligned两模式的双向启动冲突，以及无续写模式共存；不调用真实模型。未提供该环境变量且本树没有history适配器时明确skip；显式提供的根缺文件则失败，不借用机器上恰好存在的邻树。历史脏树临时改测试的4P仅是开发观察，不能替代这份已提交测试的净树收据。

产物包括 `plan.json`、`pi/answer.md`、`pi/events.jsonl`、工具与脱敏模型请求/响应、`RESULT.json` 和哈希清单。
`RESULT.status=completed` 只说明完整终稿、模型身份和执行完整性成立，`quality=UNREVIEWED` 仍需全文核验。
`skill_reads` 只计成功读取；`tool_calls` 计桥接层预占的全部尝试，`tool_observations` 单列返回的观察，父线程尝试/错误另外记录。
`pi/completed-drafts.json` 保留所有完成稿，可直接比较二看前后；空答案、错误停止、型号不符和输入变化会非零退出并保留现场。

内容验收检查：全集边界、量价与资金的区别、指数贡献依据、反证可观测性、缺口声明。
字数和调用数不代替质量。同题对照还要固定代码、模型参数、数据库、截止日和工具上限；n=1 不签总体胜率，失败不重抽补绿。

## 成文层归属

用户已选择本A线统一命题/证据合同：工具 `qualifications` 与逐句命题类型是主要核对依据，词面标注只作补充；问题回灌一次修订，保留原稿，不拒收或伪装为已核验。清点线只补专项方法与反例，B线reviewed-history保持实验且不再扩写。该属主决定不是功能已实现或金融质量已通过；当前direct/aligned的行为不变，实施与验收待独立切片。

## 边界

- 验证入口使用独立 Pi 配置目录，显式工具白名单，不加载全局扩展或项目资源。
- 子进程仍运行在当前用户权限下，继承模型传输所需环境；这是可信本机验证，不是操作系统沙箱。
- `--offline` 停止 Pi 的自动目录联网，不会阻止模型请求。
- 本入口使用隔离的新用户空间，不据此宣称个人记忆召回或跨轮 report/track 已验证。
- Pi JSON 模式可能在模型报错时退出 0，必须同时核对停止原因；一次自检的状态按用户输入重置。
