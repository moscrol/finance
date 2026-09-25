# 工单 #53 · 2026-09-14 提取前置 P0（入口先取用户自己的观察剧本）

> **可独立分发；仅交付 P0 工程能力，实验开跑另受 §7 约束。** 本单包含背景、目标、边界、证据、步骤、验收、交付条件。
>
> **代码基线：最新 `gitea/main`，开工冻结完整提交号。** 本次远程核对为 `d7e5380551ba92758935d268fdd0e6fbfdd51ce8`。两条前置已于 09-06 通过 #598（`993c3b1d`，river-slice-v0）与 #599（`7c31dd9e`，observation-script）合入；旧交接“未合”仅是历史状态，**不得从旧前置分支开工**。
>
> **编号：撤回本单误登的 #27，改为 #53。** 主线 #27 是运行底座母单；#26 仍预留；#52 已被 `2026-09-12-trading-day-vs-data-arrival-workorder.md` 占用。09-14 核过本机 1897 个本地/远程跟踪 ref、263 个 worktree 的工单/INDEX，未见 #53 被占。后续分发复核冲突，不按旧树最大号取号。
>
> 设计依据：`~/foresight/docs/specs/2026-09-13-extraction-first-spec.md` rev.4；本单是 P0 执行契约，操作口径冲突以本单为准，同步设计稿执行指针。用户专属的 `offer.yaml / decisions.md / commitments.md` 不改。

## 1 背景与动机

终局设计 §3.1 原闭环是“系统生成观察剧本 → 用户确认 / 修改 / 跳过 → 登记 checkpoint（到期回检点）→ 回检”。用户先看到答案再表态，留下的主要是对系统的认可，与 D-002“减少对外部答案的依赖”方向不符。

本单在**向用户提供系统带读与剧本之前**，先收用户自己的观察剧本，再展示字段差异。差异帮助用户指出遗漏与分歧，**不代表系统更正确，不评分、不计算收敛指标**。用户可以显式跳过提取，跳过不计失败。

复用现有剧本对象、合规门、CLI、个人台账与回检引擎。主线已有每日复盘带读接线、上下文投影哈希（标识系统当时看到的材料）、hindsight（事后信息）传递；这些是当前合同，不再按 09-06 旧接口实施。

## 2 目标与行为合同

### 2.1 用户草稿：身份、版本、确认分开

- 新增 `observation draft`，复用 `observation_script.make/validate` 与 `ObservationScript` 对象，至少填写观察变量、降级 / 放弃条件。通过同一结构与合规硬门后才落盘；保存草稿不生成系统骨架、不登记 checkpoint。
- P0 每条草稿对应一个阅读目标，多实体输入返回可修正错误。关联键为 `user_id + as_of + scope + canonical_entity_id`；`as_of` 是所读交易日。实体复用 River 现有身份解析，**只解析身份不生成带读**；无法解析给错误。实体名称、CLI 输入别名不充当身份键，不能把“同日任意一条”当作已作答。
- “同日重写取最后一条”指**同一关联键下最后一次成功提交**。只追加记录，每版有唯一 `draft_id/submitted_at`，旧版保留；修改放弃条件也产生新版本。失败提交不替代已有有效版。
- 来源另记 `author_origin=user` 与 `extraction_attempt_id`，由受控入口写入，不接受用户注入来源标签。旧记录或系统骨架即使 `status=drafted` 也不算用户提交；无来源字段的历史记录仍可查。
- 保留完整手填 `confirm` 与 `confirm --from-slice` 原有语义，不自动把 draft 当确认。确认保留关联的 `source_draft_id/attempt_id`，不覆盖原稿。沿用 `projection_hash/hindsight/user_authored/late` 合同；**作者来源不复用 `user_authored`**，后者仍仅表示既有“产品外手填、无投影”的登记口径。不能把后来生成的系统投影伪装成用户作答前见过的材料。

### 2.2 开关先于提取门

| 条件 | 行为 |
|---|---|
| 带读显式关闭 | 沿用关闭行为，不生成带读、不创建提取尝试 / 事件；日报正文按既有逐字节不变合同处理 |
| 开关未显式指定 | 保留“显式参数 > `FORESIGHT_GUIDED_READING` > 新用户开、老用户关”的优先级 |
| 带读开启，同键有有效用户草稿 | 使用最后成功版本放行，展示差异 |
| 带读开启，无草稿，显式 `--skip-draft` | 记录 `draft_skipped` 后当前尝试放行；授权不跨用户 / 日期 / 实体 / 新尝试 |
| 带读开启，无草稿且未跳过 | 提示先提交或显式跳过；不生成、输出或登记系统骨架 |

“默认开启”指**开启的带读始终受提取门约束**，不翻转老用户默认开关。`--skip-draft` 不等于 `--on`，关闭时不凭它写跳过事件；已有有效草稿时优先使用草稿，不重复记跳过。仅记录提取过程不得改变新老用户判据。

开关控制 `read` 与日报的带读生成；显式 `draft/close`、草稿与事件查询仍可使用，不要求用户先打开带读。独立 draft 的尝试与提交事件按 §2.4 记录，但不因此生成带读或改变开关。

### 2.3 共用入口门，覆盖实际输出

系统构建 / 披露之前集中解析一份“允许读取 / 需要草稿 / 带读关闭”结果，CLI 与日报共用。纯构建函数保持可离线测试，不把后台作业变成交互等待。

| 入口 | 必须遵守的边界 |
|---|---|
| `observation read` 文本 / JSON | 未通过只返回提示、原因与 `attempt_id`，正文及 JSON 内嵌系统骨架均不泄漏 |
| `confirm --from-slice`、会生成 / 回显骨架的 `observation skip` | 共用提取资格检查，支持显式 `--skip-draft`；未通过不生成、不确认、不写 checkpoint。“跳过系统剧本”与“跳过提取”分开记录 |
| 完整手填 `confirm` | 保留直接登记，不用系统字段补齐；不冒充 `draft_submitted/read_completed` |
| 用户列表 / `list --json` / 事件查询 | 用户草稿、事件与历史元信息可查；所查询阅读目标尚无提取资格时，不回显系统骨架正文；日期按记录的 as_of 判断 |
| `daily → build_for_daily_review → merge_into_daily_review` | 无草稿时正常生成原有复盘，在附加带读位置放简短入口提示；不生成附加带读、不等 stdin、不因未作答使夜跑失败、不替用户记跳过 / 离开 |

`confirm --from-slice/skip` 本身属于用户显式操作，可请求系统骨架，不被“老用户默认关”静默吞掉，但必须通过提取门。`read` 和日报继续遵循 §2.2 的开关优先级；任何入口若接受显式关闭请求，该请求优先。

无人值守日报生成不证明用户进入页面，因此不创建用户尝试 / 完成事件。用户随后从 `read` 进入同一目标；已有草稿后重跑日报可附加带读，但后台写出仍不算用户 `read_completed`。

本单保护这些新增生成 / 披露系统带读的产品路径，不改原有复盘其他正文、底层事实查询或用户原始备份的权限模型。原始个人导出保留全部记录，不作为试验带读入口。旧版本已披露过答案的历史样本不能追溯变成独立作答；试验必须记录已知暴露条件。

### 2.4 单一台账与可观测事件

路径统一由 `userspace.user_space(user).observation_scripts_path` 解析，唯一写入者仍是 `observation_script.py`。复用这个文件存草稿来源、尝试和事件；**不写 `interactions.jsonl`**（任意非空行会改变新老用户判定），不把过程事件塞入 checkpoint。

用 `record_kind` 区分剧本 / 提取尝试 / 提取事件，兼容无类型字段的旧剧本。`load/status_counts/expire_stale`、列表及回检只消费相应类型；原始导出保留全部类型，事件不计入剧本 / 校准分母。在 `docs/learning/ledger-map.md` 登记格式扩展与同一写入者。

草稿提交 / 剧本确认的成功事件，**从成功剧本行内的动作元数据投影读取**（内含 event_id 与关联键），不再追加第二条成功事件行，避免保存成功与事件记录之间断裂；其他事件用独立事件行。新增记录按同一写入者的完整行 / 并发约束持久化，半行不算成功。不改变 checkpoint 的跨台账登记语义，失败要如实返回，不能用补造确认事件掩盖。

**尝试生命周期：**

1. 开启的用户入口首次调用创建 `attempt_id`，保存关联键、入口和 `opened_at`；同键最多一个未结束尝试。`read/draft/confirm/skip/close` 支持 `--attempt-id` 续接，未传则复用同键未结束尝试；其他用户 / 目标的 ID 拒绝。直接 draft 可创建尝试；完整手填 confirm 无关联尝试时只记录确认动作，不伪造曾进入提取流程。
2. read 提示后返回表示等待，**不是 abandoned**。关闭终端或不再回来都没有可证明的结束信号，保持 `pending`，不设推断超时、不把 pending 算离开。
3. 新增 `observation close --attempt-id ...` 表示用户明确结束。仅尚未提交 / 跳过 / 成功读取时记 abandoned；否则只关闭尝试，保留已发生事件。
4. 成功 read 关闭尝试；同 ID 查询 / 重试返回原成功收据，不重复完成事件、不重新生成或宣称重放完整正文。要重新读取使用新尝试；同键有效草稿仍可复用。显式 close 后旧尝试不能复活。后续确认可关联已完成尝试的具体草稿版本。
5. 事件带 `event_id/user_id/as_of/canonical_entity_id/occurred_at/entrypoint`；提取内动作必有 `attempt_id`，独立手填确认的 `attempt_id=null` 且标 `entrypoint=manual_confirm`。相关时附 `draft_id/script_id`。同动作重试去重，草稿新版本是新动作。并发认领、追加与去重由同一写入者完成，不靠 CLI 先查再写。

| 五业务事件 | 触发依据 | 不得误记 |
|---|---|---|
| `draft_submitted` | 新版本通过合规校验且成功持久化 | 被拒、保存失败、同版本重试 |
| `draft_skipped` | 开启的用户入口确实采用显式跳过，先记后生成骨架 | 后台日报、带读关闭、已有有效草稿 |
| `script_confirmed` | 现有确认登记成功，带实际 `script_status/checkpoint_id`；late 仍属确认动作，但不改校准排除 | 仅 draft、登记失败、重复确认收据 |
| `abandoned` | 用户显式 close，尝试从未提交 / 跳过 / 成功读取 | 等待、无后续动作、后台运行、重试 |
| `read_completed` | 用户入口完整带读过输出合规门且成功交付 | 只构建对象、无系统骨架、输出失败、后台生成日报 |

尝试记录不是第六个业务事件。`read_completed` 只证明**系统成功交付**，不证明人已读完或学会。CLI 先完成输出与 flush，再持久化完成收据；两者之间崩溃或收据追加失败标交付结果未知，返回可诊断失败，不补造成功，也不承诺 stdout 与台账跨介质“恰好一次”。只有已持久化的完成收据才能用于去重。`observation list --events [--attempt-id ...] [--json]` 分别列五事件与 pending，可按用户 / 日期 / 实体过滤，不合并成单一跳过率、不推断跳过动机。

### 2.5 差异摘要

比较所选用户草稿版本与**本次实际交付的系统骨架**。现有构建结果没有持久化 ID，系统侧使用 `system_script_ref`：对实际骨架的规范化业务字段、关联键与 `projection_hash/knowledge_cutoff` 做稳定内容哈希。读收据保留这一引用、系统投影信息及所选用户 `draft_id`；它不叫已登记 script_id，也不承诺能靠哈希恢复正文。不为 P0 新建完整带读快照。两侧须同一阅读目标；无系统骨架显示“本次无可比较剧本”，不冒充完全一致。

仅比较 `variables/upgrade_conditions/downgrade_or_abandon_conditions/machine_conditions`。逐项去首尾空白、去重、忽略顺序，差异稳定排序，按字段列“你写了、系统未列 / 系统列了、你未写”。ID、状态、时间、用户、证据引用、投影等元数据不比较；不做语义相似度、不调模型。

全部一致时结构为 `[]`，可显示中性“所比较字段无差异”。差异结构 / 文本同过合规门，不判用户答错。只持久化必要来源关联，差异展示时重算；差异及大小不写评分、画像、聚合指标或校准台账。

## 3 非目标与改动边界

- 只做 P0；不做 P1–P5 的知识分类、预埋提问、勾稽 / 试教台，或 §4.5 方案 C“AI 对用户的判断进回检台”；不新增 `object_type`。
- 不新建台账文件、回检引擎、学习评分或“差异收敛”指标。
- 不改 `checkpoints.py` 的既有语义，不弱化投影、hindsight、late 与合规门，调用方正确传现有合同。
- 不接实时数据源、不新增模型 / 网络外呼、不写外部系统；事实和身份走现有本地读取面。
- 不改用户专属决策台账，不填 §7 阈值，不启动真人实验、部署或合并 main。
- 实现范围：`observation_script.py/guided_reading.py/intelligence/cli.py` 相关接线、对应测试及必要文档。必要的纯函数 / 本地台账辅助模块可同目录新增并说明单一职责；词表、userspace 路径及无关模块复用现状。

## 4 开工必读证据

源码读冻结的当前主线；旧测试数量只作历史背景。

| 文件 / 入口 | 核对内容 |
|---|---|
| `docs/superpowers/specs/2026-09-06-personal-research-calibration-endstate-design.md` §3 / §4 | 闭环、观察对象、投影与事后信息 |
| `intelligence/services/observation_script.py` | 对象、校验、登记、台账读者、来源传递 |
| `intelligence/services/guided_reading.py` | 开关、构建 / 渲染、日报接缝、投影 |
| `intelligence/services/compliance_gate.py` | 用户与系统共用硬门 |
| `intelligence/services/checkpoints.py` 登记接口与测试 | 投影 / 作者声明 / hindsight / late；unverifiable 非终态 |
| `intelligence/cli.py` 的 daily 与全部 observation 子命令 | 真输出入口、手填与自动确认区别、JSON 回显 |
| `intelligence/userspace.py`、`docs/learning/ledger-map.md` | 用户隔离、路径、唯一写入者 |
| `intelligence/tests/test_guided_reading_daily_seam.py`、`test_river_projection.py` 及观察 / checkpoint 测试 | 当前接线与关闭不变；按符号检索完整消费者 |
| `docs/handoffs/inflight/feat-observation-script.md`、`docs/verification/2026-09-06-observation-script-g03.md` | 仅取设计理由与历史问题，合入状态以 Git 为准 |
| `~/foresight/docs/specs/2026-09-13-extraction-first-spec.md` §4.5 / §6 | 动机与实验约束，未批准阶段不带入 |

## 5 实施步骤与交付

1. 按 AGENTS.md 执行 `git status --short`、`git branch --show-current`、`git worktree list`、`bash scripts/session_facts.sh`，认清他人改动。`git fetch gitea` 后记录完整基线 SHA，从该提交另开 `feat/extraction-first-p0` worktree。本单若尚未合主线，只把本单与对应 INDEX 新增行带入新树，保留主线其他行，不能用旧树 INDEX 整文件覆盖。
2. 走代码地图正门并核对调用者。新树使用主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。干净基线跑相应回归与全量 pytest，保存 revision、命令、环境、测试 nodeid 结果和耗时，不只记通过 / 失败总数。
3. 实现台账分型、草稿版本、尝试 / 五事件与查询，再把同一顺序门接入 §2.3。使用临时 users 目录和固定本地切片，不碰真实用户台账。
4. 实现字段差异与来源关联，补 §6 验收及变异测试（故意拆掉逻辑，确认对应测试变红）。
5. 最终干净提交运行适用门禁：Python ruff + 全量 pytest；合入前按仓规补 frontend / e2e / registry 叶子。失败按 nodeid 在同环境基线逐项归因，不能靠总失败数不增判无回归；必要叶子红或无结论都不得宣告可合并。
6. 收据写 `docs/verification/2026-09-14-extraction-first-p0.md`，含基线 / 最终 SHA、环境、逐项验收、变异红绿、原始输出路径与未验证项。更新工单 / INDEX 状态、台账格式与受影响入口文档；工程完成不替代真人效果。
7. 用 handoff 写实现分支的 `docs/handoffs/inflight/feat-extraction-first-p0.md`，只用 pathspec 提交。完成条件是代码、验收、交接可复核；合并 / 部署 / 实验分别遵守授权条件。

## 6 验收清单

行为样本固定用户、交易日、实体、本地切片，用隔离 users 目录；开关状态显式写进夹具。

- [ ] **A1 草稿 / 身份**：draft → list 可查；同键最后成功版生效且旧版保留；用户、实体、相邻交易日互不放行；有效别名可对齐。旧系统 `drafted` 不冒充用户提交。
- [ ] **A2 原阳性对照 1**：双方业务字段一致，ID / 时间 / 顺序不同，差异仍为 `[]`，不崩。
- [ ] **A3 原阳性对照 2**：开启带读、无 draft/skip，直接 read 的文本 / JSON 被拦，系统构建函数未调用，无骨架 / checkpoint 副作用。
- [ ] **A4 原阳性对照 3**：违规 draft 被同一合规门拒绝，无新有效草稿 / 提交事件 / checkpoint；之前有效版本不变。另测结构违规。
- [ ] **A5 非空差异**：分别增删变量、修改放弃条件，断言具体字段和双方差异项；只变元数据无差异；无系统骨架明确不可比。
- [ ] **A6 跳过**：开启、无草稿，显式 skip 能读且只记一次；新尝试 / 另一目标不沿用。有效草稿与 skip 同在时使用草稿，不写虚假跳过。
- [ ] **A7 出口覆盖**：无资格的 from-slice、系统 skip、列表 / JSON 不绕门；完整手填 confirm 保留行为且不冒充提交 / 阅读事件。
- [ ] **A8 日报接线**：真实 daily 接缝无草稿时仅增加入口提示，非带读正文不变；不创建用户尝试 / 业务事件、不等输入、不因顺序门失败退出。有草稿可附带读 / 差异；后台生成仍不计用户完成。
- [ ] **A9 事件续接**：read→提示→draft→read 同一尝试，有提交 / 完成、无 abandoned；read→提示→close 只记一次 abandoned；无后续动作保持 pending。五事件分别可查，late 确认保留状态，事件不进回检分母。
- [ ] **A10 重试 / 并发 / 失败**：同 attempt / 动作不重复事件；并发进入最多一个 pending，草稿不丢版本；提交 / 确认事件随成功剧本行投影，不存在第二次追加才补成功事件的窗口。拒绝、保存 / 输出失败不记成功；输出后完成收据写失败标未知，不伪称已完成。跨用户 attempt 拒绝；原始导出保留类型但不误计剧本。
- [ ] **A11 开关矩阵**：显式开 / 关、环境开 / 关、新老用户默认各验；skip 不打开关闭的带读。首次及时确认并写入 checkpoint 后，次日默认关，显式 on 可正常 draft/read；仅提取记录不改变新老用户判据。带读关闭时独立 draft 仍能保存，但不会生成带读。
- [ ] **A12 旧合同**：无类型旧剧本仍可读；事件不进状态数、过期处理或 checkpoint。投影 / hindsight / late 回归全绿，checkpoint 测试不删不减语义断言；无伪造投影、作者来源混用或 draft 自动确认。
- [ ] **A13 有牙验收**：差异恒空→A5 红；绕过共用门→A3/A7/A8 对应红；系统 drafted 当用户草稿→A1 红；命令返回即 abandoned→A9 红；去掉用户关联→隔离用例红。每个变异还原后绿。
- [ ] **A14 不评分**：检查本单新增代码、输出和台账增量，只有字段差异 / 来源关联，没有相似度 / 一致率 / 收敛分数或对画像 / 校准的写入。不以全仓关键词零命中作证，其他模块合法指标不属本单。
- [ ] **A15 收据**：最终提交门禁、各验收观察面与基线差量齐全；工程 / 真人验证状态分列，收据可重跑，INDEX 与交接指向本次最终提交。

## 7 实验开跑前由用户定

本单仅交付工程能力。三项**不填就不开跑真人实验**，不得事后补阈值：

| 项 | 谁定 |
|---|---|
| 观察周期（建议至少覆盖一次回检到期） | 用户 |
| 可接受的额外耗时（先量原流程基线） | 用户 |
| 撤回条件（哪些可观测结果达到什么程度即撤回） | 用户 |

pending 不能算离开，read_completed 不能当人已读完。使用离开率 / 完成率前，确认入口确实收得到相应人类行为；拿不到的量标未知，不用系统交付替代。原始备份导出或旧版本已披露答案的样本注明暴露条件，不混入首次独立作答比较。

首批优先取定性信号：“这一步有没有让你看到一个原本没想到的点？具体是哪一个？”说不出记“无”。不做满意度打分，少量 Alpha 用户的比例读数不冒充统计结论。

## 8 执行红线

- 遵循 AGENTS.md 的解释器、独立树、pathspec、代码地图、合入门禁要求。
- 不合 main、不强推、不启动真人实验或改生产运行时；本次修订不扩大这些授权。
- 若实现另需 `R-日期-序号` 研究预注册号，用 `scripts/claim_ledger_id.py claim --branch feat/extraction-first-p0`；它**不分配本 INDEX 的工单编号**。
- 不静默关 PR，保留接替指针或废弃理由。状态以刚核验的 Git / 收据为准，不把历史交接重新写成现在。
