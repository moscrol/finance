# feat/adaptive-research-loop

## 这个分支做什么
模型自主选视角并随证据调整；不固定股票池。继续同会话反馈/公开保真，不转K3外审。树 `~/finance-worktrees/adaptive-research-loop`。

## 决策与被否方案
- 原句/阶段回原REPAIR_GOAL；否按删句后编号猜原句。
- 诊断与授权分离；否让诊断改预算/增额度。数字补证诊断仅在授权后投递。
- SDK复用领域消息，否私自截短/另造提示；缺历史仍闭工具。
- 发布只对未解决机械/前置反馈降级；`judge`语义删句或降级为issue算已处理，否一律降级会误伤合法历史完成态。
- 不恢复拒句/拼私有gaps。完整理由见 `docs/handoffs/2026-09-21-adaptive-repair-publication.md`。

## 2026-09-21 下午：三处修法已落 + 已前向合入 main
`00d35ae80` 修三处（各配红→绿测试与单点撤线）、`9e08b6b39` 补两条钉子测试、`8293ec69e` 前向合入 `gitea/main@c615adbd2`。

1. **终局修复重核**（`continuous_turn_adapter`）：`repair_model_stop` / 截止带稿只约束「不再开下一轮」，不豁免「公开的正文必须是被审过的那份」。修复轮只要改了 draft 或 bindings（`_repair_changed_submission`，与 harness 的 `revised_without_tool` 同口径），就对新稿重跑判官；没改就沿用旧审查结果（省一次判官）。**进度规则 `admit_repair_result` 未动**：它答「这轮有没有进展」，新判据答「公开的是不是被审过的那份」，两者正交，改进度规则会牵动预算与轮次语义。
2. **未复核修订上限**（`episode_semantic_verifier.with_unreviewed_revision_publication` + `UNREVIEWED_REVISION_NOTICE`）：重跑判官来不及（截止/取消）时仍发旧稿，但公开状态压 partial 并附「核验后产生的修订稿未及复核，本轮按修订前版本发布」。未复核的新稿不出门。
3. **数字门单位无关**（`_bound_observation_values` + `_quantity_supported_by_evidence(observation_values=…)`）：结构化观察值的单位在字段名里，比对时按候选单位的基准量级匹配（`成交额亿=20764.84` 同时支撑 `20764.84 亿` 与 `2.08 万亿`）；`E\d+` 与 `Q3/2026Q4/三季度` 不当数量。**只放宽观察值，不放宽 detail 文本里的裸数**（日期碎片、序号不该获得单位背书）。
4. `scripts/probe_tool.py` 新增 `PROBE_CAPABILITIES`（`ALL_TOOLS ∩ DEFAULT_RESEARCH_CAPABILITIES`），修掉三个历史工具名当能力传导致的构造失败。

**撤线（每门一次，单点变异，改完即还原）**：M1 去掉观察值传参 → 1F；M2 去掉 E 号/季度剥离 → 1F；M3 终局一律跳过重核 → 1F/1P；M4 上限规则永不触发 → 3F；M5 适配器不接上限 → 1F/1P；M6 probe 面回退成 ALL_TOOLS → 2F。还原后 8P。日志 `~/.finance-runtime/adaptive-fix-mutations-20260921.log`（含首轮 M3–M5 因 zsh 不分词误报 `no tests ran` 的记录与重跑）。

**合入前向（两次）**：`8293ec69e` 合 `c615adbd2`（#770/#819），`5bb3817ea` 合 `adcda94b5`（#825 判官理由码分流 + 8792 公开交付收口、#826 文档）。第二次三处冲突都是「两边各加一个键」：判官载荷 `declared_gaps` + `ranking_contract`、动态输入 `adaptive_research` + `premise_calculation_rule`/`calculation_delivery`、门页两节，全部并存；合并后接缝套件（含 ranking / e2 / protocol）1285P/4S、Ruff 通过。第一次的冲突五文件均按「两边行为都留」解（数字门：历史句跳过 + 短日期掩码 → E 号/季度剥离 → 单位无关匹配；判官提示：采用 main 的累加结构，`declared_gaps` 须知接在基底后，`nonfactual_review` 保留 main 的短路；修复轮同时传 `review_feedback` 与 `rejected_claim_notes`；`user_task` 用 `is_material_only_instruction` + `_is_local_only_head` + 放宽词表三支）。合并后两侧相关套件 1199P/4S、Ruff 通过。

**活体复验（同题、同配置、修法 revision `9e08b6b39`）**：
- 冒烟 2 原题 → `run_20260921_131925_583952`，131 s：修复轮自报 completed → 复核 → 判官 passed，`outcome/verified/public/answer.md` 四层同稿，`semantic_verifier_stale=false`，两句被打回的原句不在公开稿。**注意**：本次模型自报 completed，走的是原本就会复核的路径；「无工具 + 自报 partial」那一格未被自然触发，该格仍只有离线测试。原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q2-fix/`。
- 冒烟 3 原题 → `run_20260921_132228_700906`，243 s：前置门从删 6 句降到删 1 句，且那 1 句（「排名持续 100 名以外」）复算确认唯一 UNSUPPORTED 量是模型自设的 `100`，真新阈值仍被拦；公开稿保留 7 家/21.88%/2.53%/排名 118/1295.9673 亿等有证锚点，无悬空列表项；`下期关注清单` 与 `裁判变量` 同时在正文，`missing_outputs=[]`；partial + 提示句为 `88a12753` 既有路径。原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q3-fix/`。

**全量**：合并后 `8293ec69e` 干净全量 `12480P/87S/2X/17W`，exit 0，收据 `20260921T064012Z-8293ec69.json`。合并前 `9e08b6b39` 为 `12102P/87S/2X/18W`。相比 `7172ba30` 的 12096P/85S/17W：`+8` 条是本片新增测试（其余 +372 来自 main 的 #770/#819），`skipped` 85→87 **未逐条归因**（两次跑都是 87，非本片改动引入，跑时机器 load≈143、另一会话并发合 main/切 8792）；`warnings` 在合并后回到 17，说明 `9e08b6b39` 那次的第 18 条是环境性的。不作零 warning / 零 skip 结论。

## 当前状态
最后一个业务提交 `7172ba30e`，其后只有文档提交；代码树干净，未push/PR/合main/部署。公开发布上限已接入并完成误降级修正。证据目录 `~/.finance-runtime/adaptive-repair-publication-20260921/` 已补齐 README / 范围审计 / 目录外校验日志。

2026-09-21 复核已撤回一项曾未提交的改动（悬空连接词剥离），见下「候选：悬空连接词剥离（已撤回）」。

2026-09-21 11:10 跑了真实模型冒烟第 1 题（寒武纪可证伪跟踪条件，单臂 off，生产配置 glm-5.3-flash + judge llm），代码未改；结果见下「真实模型冒烟 1/3–5」，原件 `~/.finance-runtime/adaptive-live-smoke-20260921/`（README / SHA256SUMS，目录外校验日志同名 `-verification.log`）。12:09 跑了第 2 题（东阳光，「只用本地资料」型），见「真实模型冒烟 2/3–5」，原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q2/`。12:37 跑了第 3 题（固态电池，theme_track 全工具），见「真实模型冒烟 3/3–5」，原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q3/`。三题原件各自 SHA256SUMS 封存，目录外校验日志同名 `-verification.log`。

## 已验证
**收据与 revision 的对应关系（2026-09-21 下午起，`7172ba30e` 那份已不代表当前代码）**：
- `20260920T220029Z-7172ba30.json` → `7172ba30e`，`12096P/85S/2X/17W`。只对合并前、修法前的代码成立。
- `20260921T055918Z-9e08b6b3.json` → `9e08b6b39`（三处修法 + 钉子测试，合并前），`12102P/87S/2X/18W`，`dirty=False`、`worktree_dirty_total=0`、exit 0。
- `20260921T064012Z-8293ec69.json` → `8293ec69e`（第一次前向合入 `c615adbd2` 后），`12480P/87S/2X/17W`，exit 0，`dirty=False`、`dirty_paths=[]`、依赖指纹未绕过。跑时工作树有 1 个未提交文件，是本交接（纯 docs，`worktree_dirty_total=1` 而 `dirty_paths` 为空 = 代码面干净）。日志 `~/.finance-runtime/adaptive-merged-full-pytest-8293ec69e.log`。
- `20260921T092038Z-ba8c55c3.json` → **`ba8c55c35`（当前 HEAD，含 `finance_query` 代码后缀闸）**，`12636P/87S/2X/17W`，exit 0，`dirty=False`、`worktree_dirty_total=0`、`dirty_paths=[]`、依赖指纹未绕过。**这份是当前代码的收据**；HEAD 可能比它多出若干条纯 docs 提交（本交接自身），接手用 `git diff --name-only ba8c55c35..HEAD` 验证只出 `docs/` 再沿用，出现业务文件即失效。前一次同 revision 的全量 `12 failed/3 errors` 全是 `sqlite3.OperationalError: disk I/O error`（`test_workbench_db` / `test_agent_*`），把那 12 条单独重跑 21P —— 机器高负载下的环境性失败，不是本片改动；红的那份日志 `adaptive-fq-full-pytest-d9e2875c0.log` 保留，不当收据用。
- **主线漂移**：本枝 `ba8c55c35` 领先 `gitea/main` 32、落后 5（`f2c3e9e1a`，含 #830「K3 写手兼容与无判官独立性统计」，动 `llm_refine.py` / `gate_receipt.py` / `variance_baseline.py` + 两个测试）。这 5 个文件本片一个没碰，但**落后即收据不代表合并后**：接手先前向合并再重跑全量，别沿用本条。
- `20260921T073452Z-d5d212a1.json` → `d5d212a1d`（第二次前向合入 `adcda94b5` 之后），`12629P/87S/2X/17W`，exit 0，`dirty=False`、`worktree_dirty_total=0`、`dirty_paths=[]`、依赖指纹未绕过。日志 `~/.finance-runtime/adaptive-merged2-full-pytest-5bb3817ea.log`（跑起来时 HEAD 是 `5bb3817ea`，收尾时已到 `d5d212a1d`；`git diff --name-only 5bb3817ea..d5d212a1d` 只出本交接一份 docs，故收据代表同一份代码）。**这份代表当前 HEAD**；再有业务提交即失效，接手请自己重跑这条 diff 验证。
定向历史4P、发布矩阵21P、跨后端24P、Ruff通过。合并后两侧冲突接缝套件 1199P/4S。最终撤线：去发布上限16F/恢复24P；误把已解决语义修订当未解决3F/恢复22P。

## 候选：悬空连接词剥离（已撤回）
问题真实：语义删句后幸存句以「反之/但/因此」开头，公开投影留悬空半句。实现有缺陷，已撤回，补丁存 `~/.finance-runtime/adaptive-repair-publication-20260921/orphan-connective-candidate.patch`（`git apply` 可恢复）。

撤回原因：`_strip_orphan_backref_connective()` 只判断行首是否**以**连接词开头，不要求该连接词是独立话语标记，把词素当成了标记。四条反例（实测，撤回前跑过）：

| 输入 | 该实现输出 |
|---|---|
| `相反的观点认为量能不足。` | `的观点认为量能不足。` |
| `同理可证丙。` | `可证丙。` |
| `所以说丙。` | `说丙。` |
| `但丁的观点是丙。` | `丁的观点是丙。` |

随附的 5 条测试全部只覆盖「连接词后接标点或独立成句」的顺风样本，加一个假朋友 `但凡`，四条反例一条都红不了。

要重做须先解决：连接词表里 `但/相反/同理/所以/因此/不过` 都是**兼类**（既是话语标记也是词素），而主用例 `但上涨家数仍待改善。` 恰恰不带标点，所以「必须后接标点」这个统一守卫会废掉主用例——需要逐词分档（无歧义的多字标记可裸剥，兼类词要求后接标点），不是一张词表能收的。收益只是 partial 答案的表面整洁，而 partial 状态与公开提示已把不完整讲清楚；且本分支立场是宿主只删无据句、不改已接受正文，剥连接词是在改已接受句。重做前先论证这条收益值得。

## 真实模型冒烟 1/3–5（2026-09-21，n=1 诊断非裁决）
run `run_20260921_111040_597004`，490.72 s，`outcome=partial / stop_reason=repair_model_unavailable / judge_status=repaired`，公开稿无提示。修复回路在生产路径上真点着了：repair_goal #1 打回两句「毛利率跌破45%」（`novel_numeric_condition`），模型**整体重写**（改为以 55.25% 为锚的相对条件 + 新增「阈值性质声明」，并自行去掉未点名的其他推演阈值）；宿主未恢复任何拒句，判官降级的两句「东阳光模式」由 v11 检索抬回但**公开稿无引用**。repair_goal #2 要 `track_next_watch`，调用 93 s 后流式失败 → partial 带稿交付。发布上限未触发且**应当**未触发（无未解决审查反馈）。发现（详见原件 README）：① 模型写「裁判变量」（judgment_delta 词汇），`track_contract` 只认「下期关注」，两解析器对「**粗体内联**：①②③」都解不出，`_ITEM_START` 把 `**` 首个 `*` 当项目符号——多余修复轮由此而来（解析器在 main 就有，本分支让它从进收据变成花预算）；② partial 只在 report/gate_receipt，`message.status=transport=completed`，前端 `MessageBubble` 显示「已完成」，webapp 无 `answer_status` 消费者；带稿的 `repair_model_unavailable` 没有公开成因通道；③ 授予 30 s 只是 `urlopen` 单次读超时，非墙钟上限；`_failure_reason` 只进进程内 `_CALL_LEDGER`，原件分不出超时还是网关错；④ 四张个股表键 `stock_ts_code='688256.SH'`，模型 3/4 次传裸码，`finance_query` 不归一也不报格式错，数据到 09-18 都在却答成「本地缺失」；唯一带 `.SH` 的查询打在 `fact_stock_daily_hithink`（最大日 09-08），gap 文案读起来像全局；⑤ 判官注册表只含绑定∪引用证据，东阳光证据在 `outcome.evidence` 里但未绑未引，判官「不存在」相对其投影成立；⑥ 首稿非 FINAL_JSON，+1 调用。

## 真实模型冒烟 2/3–5（2026-09-21，「只用本地资料」型，n=1）
run `run_20260921_120952_719744`（东阳光 9 月量价 vs 板块），169.73 s，`outcome=partial / stop_reason=repair_model_stop / judge_status=repaired / semantic_verifier_stale=true`。`local_only` 上限活体成立（授权面收为 `finance_query/evidence_lookup/memory_lookup/mainline_context` 四工具，10 次调用无越界，v11 因 `no_retriever` 跳过；注意该上限**不含 kb_search/evidence_search**，「本地」= 已审定的纯本地 runner，不是 wiki）。判官 round 1 降级三句真实错误（「换手率始终低于1%」在 9/01–9/04 无数据、「9/17 板块普跌」与 E48/E49 不符、20 日 vs 单日口径混用），修复轮 27 s 内把三句全改对并如实自报 `partial`；`admit_repair_result` 规定无工具修复须自报 completed 才算进展 → `repair_model_stop` → 适配器按终局处理、不对新稿重跑判官、置 `semantic_verifier_stale=true` → **公开稿 = 修复前稿 A，三句错句原样发布**，而 `outcome.draft` 是改好的稿 B（三层稿件比对见 q2 README）。发布上限对此形状盲：judge 记录被当作「已处理」。`completed_without_tool` / `_TERMINAL_REPAIR_STOP_REASONS` / stale 不重核 都在 gitea/main 上；本分支新增的判官原句回传（`semantic_repair_feedback`）让修复轮得以开启，净效果是「多一轮调用、公开文本不变、状态变 partial 且无解释」——这是本分支承诺链（反馈→修订→公开保真）的最后一环断点。其余：裸股票代码 2/2 复现（模型第二批自改 `.SH`）；「当前用户任务未授权历史窗口」挡住 8 月末基准价，模型如实记缺口；`scripts/probe_tool.py` 因 `ALL_TOOLS=tuple(_DEFAULT_TOOL_METADATA)` 含三个非能力工具名（`history_query/read_history_result/save_history_research`）在本分支与 main 上都 `ValueError` 构造失败，`test_probe_tool_arguments.py` 只测参数抓不到。原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q2/`（README / SHA256SUMS / 目录外校验日志）。

## 真实模型冒烟 3/3–5（2026-09-21，theme_track 全工具，n=1）
run `run_20260921_123745_556321`（固态电池可证伪跟踪条件），130.79 s，`outcome=completed / stop_reason=repair_model_finish`，**`publication_assessment.max_status=partial` 且公开稿末尾带提示句——发布上限活体首次观察到触发**。对照第 2 题：修复轮无工具但自报 completed → `progressed=True` → 判官重跑（2 次）→ 无 stale 发布，证明丢稿只发生在「无工具 + 自报 partial」一格。但 round 2 前置门 `novel_numeric_condition` 删了 6 句数值条件（降级/证伪/量能/下期关注①③），用模块自己的 `_bound_evidence_quantities` + `_quantity_supported_by_evidence` 在原件上复算：这些数字（1.82 / 118 / 165 / 2.53 / 21.88 / 1862.79 / 1295.97）**全在绑定证据的数量集合里**，被判 UNSUPPORTED 的是 `1.82%`、`2 家`、`7 家`、`1862.79 亿`……——结构化观察值渲染成 `市场占比=2.53`、`涨停家数=2`、`成交额亿=1862.79`，单位在字段名里，模型按人话补了单位，`_same_quantity_dimension` 判不同维度；`E6`→`6`、`Q3`→`3` 也被当数量。一道「给数值条件」的题六条数值条件全被删，剩悬空的「① 量能…」和失效的「以上四条」；模型补的「下期关注清单」标签句因带数值被删，`track_next_watch` 再判缺（数字门与表达槽互相拆台）；cycle 2 因账本覆盖无进展不批。第 1 题模型靠「推演阈值声明」绕过同一道门，第 3 题按门的意图锚到观察值反被删。修复调用 35 s 超 30 s 授予窗仍完成（授予窗=单次读超时，第 1 题同源）。原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q3/`（README 含逐句复算表）。

## 未验证 / 已知边界
自然模型公开保真、披露重要限制、持续观察后改向未验；脚本模型/SDK runner不代表质量。其他后端、真实费用/上下文窗口、裸代码后缀、监管覆盖、独立Spec/Quality、合流/部署未验。judge off不审gaps；17 warnings非零warning结论。

## 下一步
### 三项遗留的处置（2026-09-21 下午二轮）

1. **「无工具修复 + 模型自报 partial」在自然模型下未触发** —— 仍未闭合，但已排掉一条路。K3 可达（`mirasim-kimi` → `http://127.0.0.1:18788/v1`，`pi auth print-api-key --provider mirasim-kimi` 取钥），小请求稳定 200（5.4 s），但 **episode 尺寸的请求被网关间歇性拒绝**：抓包代理（`/tmp/k3_capture_proxy.py`，原件 `/tmp/k3-capture-1/`）录到 `400 {"error":{"message":"The request was rejected as invalid.","type":"invalid_request_error"},"request_id":…}`；把同一份 96 KB 载荷原样重放三次得 `200/400/200`，去掉 `thinking`/`temperature`/`tool_choice`/`tools`/`additionalProperties`/截短正文各三次也都是混合结果 —— **是网关/上游的间歇故障，不是我们的载荷形状**（HTTP 400 在运行时按不可重试处理，这是对的，不因网关说谎而改）。K3 首轮能出工具调用但返回的 tool_call 无 id（运行时按 `<name>_<i>_<hash>` 合成），且把推理正文漏进 `content`——这两点单独看都不致命，真正挡路的是那 50% 的 400。同题在 GLM 上修复版共跑三次（`-q2-fix`、`-q2-fix-reroll1`、`-q2-fix-reroll2`），修复轮都自报 `completed`（`repair_model_finish`），该分支取决于模型自报的状态词，碰不到就是碰不到；不再刷次数。**闭合条件**：网关侧修好间歇 400 后用 K3 复跑，或换一个能稳定驱动 episode 的第二模型；在那之前这一格只有离线测试。K3 全部证据与复现方法封在 `~/.finance-runtime/k3-gateway-intermittent-400-20260921/`（含抓包代理、两份被拒载荷、逐项重放表）。
2. **删句残片** —— **决定：不做正文外科手术**。理由：宿主改已接受正文正是上一片撤回悬空连接词候选的原因（中文兼类连接词误剥四条反例）；残片是呈现瑕疵，而发布上限已经把「本轮有表述未通过核验」公开讲清楚，读者据此能解释残留编号。数字门修好后同题复验未再出现悬空列表项（`-q3-fix` 删句 6→1，且删的那句是模型自设阈值），说明**残片的主要来源是误删而不是删句机制本身**，源头已收窄。若日后仍高频出现，先量化再动手，别先写规则。
3. **`finance_query` 股票代码** —— 已修（`d9e2875c0`）：`stock_ts_code`/`sector_ts_code` 这类列上做 `eq`/`ne`/`in` 精确比较时，裸 6 位码不再静默返回零行，而是拒绝并给出带后缀族的重试提示；**不替模型改值**（6 位码到交易所的映射有 B 股等例外，猜错比查空更坏），`contains` 传裸码是实测有效的正常写法，不受影响。撤线：去掉这道闸 7 条里红 4 条；query / episode_tools / agent_research 三套共 504P/16S。

修法 B/C/D 与 probe_tool 已落（见顶部「三处修法」），候选 A（改进度判定）**刻意不做**：`admit_repair_result` 答的是「这轮有没有进展」，牵动预算与轮次；「公开的是不是被审过的那份」由适配器新判据独立回答，两者正交。剩余未做项：① 「无工具修复 + 自报 partial」在自然模型下未被触发，只有离线测试；② 删句式修订的残片（悬空列表项、失效计数）仍无策略——冒烟 3 复验没复现，但成因未消除（上一片撤回的悬空连接词候选是同一条链，重做须先按兼类分档并论证收益）；③ `finance_query` 的股票代码归一（裸码 `600673` 查空、不报格式错）未做，两次冒烟各出现一次变体。

两个参数不需要用户选：生产 `/api/health` 自报 `agent_runtime.model=glm-5.3-flash`；`ASK_SEMANTIC_JUDGE` 在生产进程未设 → `judge_mode.py` 默认 `llm`（关着的是独立判官，启动器 `LLM_JUDGE_API_KEY` 被注释）。冒烟 1/3–5 已跑（上节），剩 2–4 道**未见**题单臂跑 `scripts/compare_adaptive_research.py --arms off`（解释器用主树 `.venv-workbench/bin/python`，树里没有 `.venv-run`）+ `scripts/inspect_adaptive_research.py --project-current-judge-status`，每题另建目录。**每题发前先用 `scripts/probe_tool.py` 走运行时工具路径验数据前提**（带 `.SH` 后缀查 `finance_query`），别直接查库。四道旧题 + 寒武纪已烧成回归题。题里要含一道「只用本地资料」型（`b6df991f` 只有工程验证）。冒烟发现 ①–④ 是候选工单，都涉及 main 上的共用件（`track_contract` / `judgment_delta` 解析器、状态投影与前端、`_post_chat_message_stream` 超时语义、`finance_query` 代码归一），要不要在本分支修、还是另开分支，待用户定；不要顺手改。

合入前另需：在最终 revision 重跑前端与 E2E（`3c30eceb` 之后只改了后端与文档，前端叶子结论可沿用，但 E2E 跑的是后端，最终 revision 上没有 E2E 结论）。不要push、合main、部署、K3、付费外审或删生产，除非明确授权。

## 踩过的坑
`judge_status=repaired`不是单独发布判据；必须结合`sentence_verdicts`阶段/原因。历史`demoted_to_issue`是已完成的保留式语义降级，不是残句。撤线前先固定提交并让临时树指向精确revision；收据不能移绑后续文档tip。

中文连接词表做正文改写必须按「是否兼类」分档，不能统一规则：`但/相反/同理/所以/因此/不过` 既是话语标记也是词素，`但丁/相反的/同理可证/所以说` 会被整片误剥。配套测试若只取顺风样本（连接词后接标点），四条反例一条都红不了——**每条规则至少配一个兄弟措辞反例**，否则测试绿只证明写法一致，不证明规则成立。

结构核验判「缺 X」时，先把交付稿喂给那个槽的解析器复现，再决定是模型没写还是解析器不认：本次「缺 track_next_watch」实为词汇不相认（模型写了裁判变量），修复轮白花。`judge_status=repaired` + 两句 `lifted` 的组合不代表公开稿有引用支撑——抬回不补 E 号。冒烟题的数据前提要经运行时工具路径验，直接查库会漏掉代码格式这层。

`judge_status=repaired` + 有修复轮 ≠ 修复进了公开稿：先比 `outcome.draft` / `semantic_verifier.verified.outcome.draft` / `semantic_verifier.public_answer` 三层，`semantic_verifier_stale=true` 且 outcome 稿与公开稿不同 = 有修复被丢。`probe_tool.py` 当前构造即失败，用 /tmp 包装器把 `ALL_TOOLS` 里三个历史工具名滤掉再跑（q2 README 有法子）；探 `finance_query` 前要先 `eval` 启动器全部 `export`（`FINANCE_WS` 决定库路径，`OPENAI_API_KEY` 由 `FORESIGHT_BUILTIN_LLM_API_KEY` 派生，单独 eval 一行会得到空密钥和 401）。

复算数字门要用模块自己的函数在真实 outcome 上跑（`_bound_evidence_quantities` 含 observations 的结构化值，纯文本 grep 会漏掉 `1295.97`），并逐个量打印 `_quantity_supported_by_evidence` 的结果，才看得出是「数字不在证据里」还是「单位不一致」。
