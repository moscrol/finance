# E2 P6（D6）第一片：逐事实材料锚点、条件化纯度与判官删句撤绑定

日期：2026-09-16。执行树 `fwp-wt-e2-p6-input`，分支 `feat/e2-p6-conditioned-input`，基线 `gitea/main@32bff514`，提交 `d17ebc27`。原作者树、主检出、8792 未改。本文记录本片发现顺序与取舍，不宣布 D6 全部完成。

## 背景

P4（D5）把 material_only 做成逐题交付：legal_gap、memo 槽、判官拒绝重开原题、投影后复验。它交代了「哪一题没答」，但没有交代「答了的那句从哪来」：judge 对材料零引用，一句「订单占比 20%」和一句凭空的「市占率 80%」在结构层长得一样。P4 交接把「纯度 / 锚点」列为 P6。

P6 的核心承诺：**锚点只证身份，不证蕴含**。`{material_id, quote}` 逐字命中用户材料，只证明这句话的输入确实来自用户给的那段文字；20÷100 是不是 20% 仍由语义判官逐句核。反过来，标签（reasoning / premise_declaration）不能替当前事实背书，历史引用只能绑到真实存在的旧答坐标。

## 按发现顺序

1. **前一会话留下 14 个未提交文件、5 条红测试**，分支上零提交。先认领工作树（`git status` 全是本任务文件），再跑三份触及的测试文件定位红：4 条是多材料计算夹具、1 条是适配器修复轮。
2. **多材料夹具红**：`split_user_message` 的 P2 编号题路径把残料整块交给 `material_from_text`，两段 `「…」` 是一份材料（`m-02ec0f2730`，正文含换行）。测试预期两份。决定不改切分器（见决策表），改夹具：两枚锚点、同一 material_id、不同 quote。算术 oracle 不受影响，`missing_input` / `unrelated_quote` 反例仍成立。
3. **适配器修复轮红**：现象是 `resumes=0, requests=1, status=degraded`，phase_trace `semantic_verify → repair(resume_for_gap) → degraded`，`repair_attempts` 从 1 回 0。前一会话试图去读不存在的 `repair_need.py`。改用 spy：monkeypatch `continuous_turn_adapter.admit_repair` 打印 need / warrant / admission，再 spy `_verify_semantics` 打印进修复轮的 `verified.issue_items`。
4. **根因**：判官拒绝「50%」那句 → `_reject_material_gaps` 删句、重开 `answer_q1`；`_finalize_outcome` 调 `recheck_material_public_delivery` 用**公开稿**重跑 `verify_episode_outcome`，但绑定还是模型原来的（claims 指向已删的那句）→ `binding_source_errors` 报 `claim text is absent from draft; every answered sentence must have exactly one ordered claim binding` → `MATERIAL_SOURCE_VIOLATION`（BLOCK）。`classify_repair_failure.material_rewrite` 只允许 {MISSING_REQUIRED_OUTPUT, REQUIRED_OUTPUT_NO_SUBSTANCE, REQUIRED_OUTPUT_GAP} → `input_only_rewrite=False` → 三种 shape 全 False，`admit_repair` 返 None。一句话：**门自己删了句子，又把「句子不在」当模型作弊，然后据此否掉唯一能修好它的修复。**
5. **修法**：`_reject_material_gaps` 记录每个被删句的归属 output（沿用已有的 owners 归属：题段 span → claims 匹配 → 全部 legal 兜底），删句后 `_without_deleted_claims` 只从归属绑定里撤掉 text 相同的 claim；撤空且无证据 / 无 gap / basis=evidence 的绑定转 `gap="语义判官拒绝了该输出的全部已答句"`（`OutputEvidenceBinding` 要求 evidence / gap / claims 至少一样）。`verified.outcome` 换成撤绑后的版本，模型原 outcome 在适配器产物里不动。
6. **两个方向都验**：修后 `NEED … shape input_only_rewrite=True`，goal `remaining_calls=0, reopen_tools=False`，resume 返回好稿，第二次判官通过，`repair_output_ids=[]`。另加一条测试：q1 两句只拒一句 → 只撤那一句的 claim、`material_source_violation` 不出现、公开稿保留另一句；随后人为再删保留句做投影 → 重验仍报违规（未被判官删的漂移照旧 fail closed）；两句全拒 → 绑定转 gap、`missing_outputs=("answer_q1",)`、无 legal_gap。
7. **ruff 两处未用 import**（`_mismatched_weekday_indexes` / `_mismatched_path_trend_indexes`）：前一会话给这两道本地扫描加了「已绑定历史句放行」却没写测试。补一条参数化测试：full 合同 + 绑定证据带 `2026-09-14` / 三点非单调成交额序列，历史句含错误星期 / 「成交额一路下跌」；绑成 historical_assistant_statement 放行，去掉 claims 或伪造 `historical_quote` 都回到被拒。
8. 提交 `d17ebc27`（pre-commit 11 道全过）后在干净树跑全量。

## 决策与被否方案

| 选择 | 被否方案 | 理由 / 边界 |
|---|---|---|
| 锚点 `{material_id, quote}` 只证身份；逐句事实 / 输入 / 推导交判官 | quote 命中即通过 | 命中只说明输入来自用户，20÷100=50% 照样命中；判官提示词明说「计算结果不必逐字出现，但必须由已绑定输入正确推出」 |
| `MaterialGrounding` 冻结进 `ResearchTaskContract`，`from_dict` 校验 `material_id_for(text)==material_id` | writer / 判官 / finalizer 各自从 prompt 现算 | 三处共用同一 payload（`material_grounding_payload`）；篡改正文 from_dict 直接 ValueError |
| 纯度按 data_scope：material_only 拒工具证据、local_only 只收 `io_effect=local_read`、full 不限；fictional 不改范围 | 按真实性或工具名判纯度 | 名字 / 新鲜度都可伪装；`io_effect` 由 `registry.execute` 按 spec 在缓存与序列化之前盖章，runner 不能自证 |
| 判官删句连带撤该句 claim，撤空转 gap | 放宽 `binding_source_errors`；或 recheck 时跳过 claims 校验 | 前者打开洗白洞（模型可把 claim 绑到不存在的句子）；后者让「公开投影改了字」不再 fail closed（`test_public_projection_rechecks_exact_claims_after_successful_judge` 就在守这条） |
| 转 gap 而不是删绑定 | 直接把绑定从 tuple 里拿掉 | 删绑定得 `MISSING_REQUIRED_OUTPUT`（BLOCK）；gap 得 `REQUIRED_OUTPUT_GAP`（PARTIAL_OK）且更真实：「有过绑定，内容被拒」。稿子里没有披露句，进不了 legal_gap |
| P2 编号题残料保持一份材料 | 改切分器按空行 / 引号拆多份 | 拆分改变 material_id 口径，跨轮 `conversation_materials` 身份与其它 E2 测试都建在上面；多输入靠多 quote 已能表达 |
| 只补测试不改 `_mismatched_*` 逻辑 | 删掉未测的放行 | 放行是 D6 要的（历史撤回句里的旧数字 / 旧星期不该被当当前事实拒）；缺的是反例，不是逻辑 |

## 验证与收据

- 干净树 `d17ebc27`：`ruff check .` 绿；`pytest -q` **11006 passed / 0 failed / 81 skipped / 2 xfailed**（7 分 36 秒）；收据 `~/.finance-runtime/test-receipts/20260916T070950Z-d17ebc27.json`，`check_test_receipt.py --expect-revision d17ebc27 --base-drift-max 5` exit 0（漂移 1）。
- 定向：`test_e2_material_grounding.py` 54 条、`test_e2_material_delivery.py` / `test_episode_protocol.py` / `test_episode_semantic_verifier.py` 合计 339 条全绿。
- 反例已跑：适配器修复测试修前红（`resumes=0`）修后绿；删句撤绑三段式（只撤被拒句 / 外部漂移仍红 / 全删转 gap）；星期与路径扫描三态（绑定放行 / 无绑定拒 / 伪造 quote 拒）。
- pre-commit 11 道（层级、路径字面量、表归属、工具可达性、运行时目录保鲜、红线）全过。
- `graph_audit.py` exit 0；新增在途行「材料逐事实锚点与条件化纯度（E2 P6/D6 在途）」五条 spec 全 PENDING。
- **不成立的结论**：判官全是离线替身与算术夹具 oracle，不证明 live 判官会按 `material_grounding` 规则逐句核锚点；作者自验，非独立 QC；前端 / e2e 未跑（本枝无前端改动，结构性等价）。

## 后续要做

1. **无编号 material_only 的修复准入**：`material_question_outputs()` 只认 `material.questions`，无编号题（`direct_answer`）被拒后 `material_rewrite=False`，直接 degraded（实测）。要么让 `classify_repair_failure` 在 material_only 下把 `direct_answer` 也当 input-only 可重写，要么在 P4 的 D5 口径里显式说无编号题不修。
2. live 判官真跑一次（先按记忆里的网关探针纪律探 `choices`），看它是否真的用 `material_anchors` 而不是只看 sentences。
3. 独立 QC；合并等用户确认；合入后图谱行去 `@branch`。

## 不要做

- 不要为了让修复轮进门而放宽 `binding_source_errors` 或 `classify_repair_failure` 的 issue 白名单：前者是 finish 时唯一的反洗白检查，后者一放宽，任何 BLOCK 违规都能借 input-only rewrite 再写一轮。
- 不要在 `recheck_material_public_delivery` 里做「凡不在公开稿里的 claim 都撤」：那会让投影删句静默通过，正是它要抓的漂移。
- 不要改 P2 切分器来凑「两份材料」。

## 可迁移

门自己改了产物再回头验，必须连带更新产物对自己的描述（这里是 claims），否则门会把自己的改动判成违规，而且违规等级往往恰好高到否掉修复。只撤自己删的那部分，别一刀切；容器要保持合法（空绑定转 gap）；两个方向都要有反例。已沉淀到用户级记忆。
