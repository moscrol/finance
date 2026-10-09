# knevo 工具包 / skill 层炼化：设计与对照（2026-10-09）

状态：**Pi 验证臂已写，当前修复与读数看 `docs/handoffs/inflight/fix-knevo-pi-runtime-1010.md`。**
原分支 `feat/knevo-skill-layer-1009` 的未提交成果由 `fix/knevo-pi-runtime-1010` 保全接手，基 `6c1d9f5d4`。
原版只过文案/注册测试，未实际开放金融工具；不能把原版「已实现」当运行验收。
用户决策（2026-10-09 深夜）：先在 Pi 原生验证，再作为 8792 可切换后端接入。本文是机制对照表的规范源；
全量审计（炼化状态、台账出入、代码对账 20 条）见会话记录，这里只保留决策与可执行的映射。

## 1. 根因与形状

8792 没有**面向模型的方法论层**：仓里的 `skills/*/SKILL.md` 全是编码 agent 的工作流，Episode 的模型一个也拿不到
（`skill_tools.py` 只注册 serenity-alpha，且只在 `intelligence.cli agent` 可达）。「怎么研究」于是被塞进两处替代品：
程序门禁（`admit_finish` → 语义校验器 → `invalid_model_finish`）与预塑形合同（`evidence_plan` 把 `mainline_context`
设 mandatory）。knevo 把同一份知识放在 `finance-mode`（OS）+ 8 个专项里让模型自己执行，harness 只管传输、身份、预算。
2026-10-09 同模型对照里 Pi 赢 8792，不是机制多，是没有这两样替代品。

对应 70_tutor《单入口派单与平铺 skill 路由》：Router 定路径、Base Contract 定下限、专项定上限、Presenter 不新增事实。
8792 有 Router（`mode_governor`）与 Presenter（`session_projection`），缺 Base Contract 与专项两层，并把 Adjudicator 做成了拒收门。

## 2. 资产层（harness 中立）

| 文件 | 层 | 吸收的 knevo 机制 |
|---|---|---|
| `skills/finance-mode/SKILL.md` | OS，常驻 | OS/应用不平级与四类裁决；反顺从；检索硬触发表 + 工具硬映射；并行齐发、空结果纪律、重试 1+2；循环纪律；路由三档 × 四维升档 + 粒度词；report/track 分流；派单判据（信息流依赖、并行≤4、串行≤2）与 task 三段式；记忆三层/三口径/四问/三桶/冲突三层/引用三纪律；缺数三层、敏感度翻转、诚实缺口模板、降级七项；输出纪律、一票否决、追问四角度；交付前自检五项 |
| `skills/finance-market-review/SKILL.md` | 应用 | 复盘骨架；两批并行一轮输出；防遗漏清单来自 Pi 对照的五类错句（全集边界 / 量价≠资金 / 指数贡献 / 广度与中位数 / 一股多题材）；跟踪信号清单接口 |
| `skills/finance-analyze-stock/SKILL.md` | 应用 | knevo analyze-stock + earnings-review；`research_workflow_guidance.financial_analysis` 的纪律并入 |
| `skills/finance-industry-track/SKILL.md` | 应用 | report↔track 接力；track 参数（记忆窗、只查变化节点、新闻窗、delta-only、四态对照、信号灯、下期关注） |
| `skills/finance-forecast-event/SKILL.md` | 应用 | 突发六步法；情景树；`research_workflow_guidance.event_forecast / news_impact` 并入 |

红线与既有运行时注入件相同：只含章法，不得夹带市场事实、数字或板块名（`intelligence/tests/test_knevo_skill_layer.py` 钉住）。
`finance-longtail-baseline` / `finance-degraded-fallback` 的内容已并入 finance-mode；两者与 env 开关在 8792 接线时退役，本分支不动。

## 3. 接线层：Pi 原生（本分支已做）

`integrations/pi/`：`finance-mode.ts`（OS 注入 / 只读守门 / `finance_call` / `spawn_sub_agent` / 可选 second-look）、
`bridge.py`（共享注册表与审计传输，`/configure` 不再依赖产品臂的 episode）、`run_native.py`（冻结→首发→收集）。
对照表与边界见 `integrations/pi/README.md`。

Pi 接缝：`before_agent_start.systemPromptOptions.sections` / `--skill` 渐进加载（system 只列名与描述，需 `read`）/
子 `pi` 进程 + `--append-system-prompt` 预设 / `agent_before_settle` 的一次续写。
`--tools` 是所有工具的白名单，主线程显式列 `read,finance_call`，开启 `--subagents` 才增加派单；
子线程显式列 `read,finance_call`，携带相同菜单、参数 schema、截止日。自检标志按用户输入重置，而不是按低层续写重置。
冻结前必须提交全部源码；执行前后重验干净树、提交号、runner、kit、skill、只读库与 RAG 绑定快照。

## 4. 接线层：8792 Episode（后续，不在本分支）

| 动作 | 位置 | 备注 |
|---|---|---|
| `list_skills` / `use_skill` 两个只读工具进注册表 | `research_tool_registry.py` | 只读 SKILL 正文、不执行脚本，不破「只读 + 无外呼」红线 |
| finance-mode 正文进 system 分段 | `episode_protocol.py` | 替换 `reading_baseline` 默认全塞（减法审计 §3：方法按需） |
| `judgment_extract.propose_from_answer` 接 finish 之后 | Episode 主路径 | 现只在 Engine B `ask.py` |
| `memory_lookup` 复用 `closed_loop_retrieval` 窄/宽/反 | `research_tool_registry.py` | 代码已有，接线 |
| `mainline_context` 由 mandatory 降为触发建议 | `evidence_capabilities._RUNTIME_CAPABILITY_FLOOR` | 底线是「必须检索」，不是「必须用这张表」 |
| 输入层加「相关记忆 N 条标题行 / 同日已讨论主题」 | `episode_protocol.py` | 路由的记忆丰度维度需要它 |

出口门（恢复器带原稿 / 失败发最后可解析正文 / 自算比例不印「待核」）**留给 Codex 线**在 `codex/claim-support-quality-1009` 之上做；本分支不碰 `episode_finalizer / research_harness / episode_protocol`。

## 5. 故意不抄

| 不抄 | 理由 |
|---|---|
| 照六层图建第二总控 / 全栈重写 | 架构审查已否；缺的是第 3 层（skill 正文）与第 5 层（模型自检），不是循环 |
| 程序化「按记忆条数定工具数」 | join-kernel spec §9 否决成立（限制模型）；改为 OS skill 启发式 |
| 块数 ≤2/≤5、阈值 7/30/90、置信 0.7/0.8/0.9 | 量纲是它的；本仓阈值按自己台账定 |
| 共享记忆平面 | 2026-08-28 gate 证伪，promoted_to_code |
| 子 agent 只回最终文本 | 「证据进父账本」更强；只补文本摘要 |
| 再加判官 / 来源桥 / 凭据图 | 减法审计 §4：多张「通过」互相翻译不出内容通过 |

保住的强项：工具结果逐项状态与截止日拒收、伪造引用拒收、证据身份与账本、取消 / 预算 / 绝对 deadline、确定性 `suggest_options`。

## 6. 验收

同模型（glm-5.3-flash、temperature 0、thinking 关）、同库、同截止日、同帽子，与 `run_pair.py` 的控制变量一致；
每次只上一个变量（先 skill 层、后 second-look、后派单）。读数不看字数与调用数，看：模型是否真的读了专项
（`skill_reads`）、是否调了记忆 / 知识库 / 图谱（`tools_used`，本周生产为 0）、独立全文阅读的五类错句是否消失。
n=1 不签总体胜率；失败入样本不重抽。
