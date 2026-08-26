# feat/disclosure-scan-p1c-claims（已收口：#401/#402 已合、8792 已切 `6876a6e7`、R5 判据达成）

> 2026-08-26 质检后重写过两处结论。**「当前状态」里带 ⚠️ 的那段务必先读**——
> 初版把 registry 预算说反了，按旧说法会去加固错的那一层。

## 这个分支做什么

修 P1-① 残差写手被有据呈现器必然拒收的根因：`prepare_disclosure_residual_answer`
此前走通用 builder（claim 被 `[:8]` 截断），shadow 有据链输入完全从 answer_spec
生成，#395 预置的完整包与残差契约进不了这条链。两件事：①
`build_disclosure_residual_answer_spec` 全行 VERIFIED claim + 聚合统计 claims；
② 残差契约经 `spec.prompt_constraints` 进 shadow 链 required_outputs 槽。

## 当前状态

**已收口（2026-08-26 凌晨）。** #401 已合（merge `fe657cbca987`；main 在 PR 开出后
前移 #400，已在 PR 树并入重跑合并闸：ruff 绿 + 全量 6531P/0F/12S，merge commit
与已测树零 diff）。8792 已从 `06622cc6` 切 `fe657cbca987`：T+45s healthy /
readiness 13/13 / 账本 record+check ok。冻结题 R5 重放**通过**
（`run_20260826_013124_466907`）：公开稿 = P0 纯包形状（骨架 0 命中）、31 公告号
全部包内、主名单 21 行零删除、degrade `disclosure_residual_dropped:grounded_rejected`；
**shadow raw_answer 1631 字符归纳形状**（m 轮 2541 字符复述消失），逐句绑行级
claim（`disc:row:*`）。切流正文
`~/.finance-runtime/cutover-20260826b-8792.md`，探针归档
`~/.finance-runtime/disclosure-scan-p1c-probe-20260826/`。

> ⚠️ **本节初版有两处错，2026-08-26 质检时改正，别按旧说法走。**
>
> **错 1：「registry 64 条全装下无截断注」——说反了。** 64 是 `verified_facts`
> 的**长度**，不是进 prompt 的行数。用生产 pack + 生产 query 在 `fe657cbc` 上忠实
> 重建 registry block：**68 条 claim、12k 预算只装下 18 条 + 1 条截断注，丢 50 条**；
> `disc:excl` 0 行、`disc:counter` 0 行、61 个 code 里 45 个从未进入 prompt。
> 直接证据：模型正文那句「另有部分结果**因窗口预算未纳入**，同样按缺口处理」是截断
> 注的原话改写——`因窗口预算未纳入` 全仓只出现在 `answer_model.py` 那条 note 里。
> 初版把它归给了 `disc:gap:budget`（那条讲的是「回购」关键词没查完，措辞完全不同）。
>
> 影响：P1-①c 的卖点是「全行 claim 集」，spec 层确实建出 64 条 ✓，但**在 prompt
> 边界被砍到 18 条**——机制在生产只交付了约四分之一。同款形状：给出的预算必须在
> 执行点被读到，接通不等于生效。
>
> **错 2：护栏测过但没护住。** `test_residual_registry_holds_all_rows_within_budget`
> 断言的正是「12k 装得下全行 + 无截断注」，它一直是绿的——因为 fixture 只有 11 行，
> 生产是 61 行。金样本把理想写进了断言。

## 下一步

1. ~~judge URLError~~ **已修并已上线**：`LLM_JUDGE_BACKEND=grok-cli` 下
   `judge_provider()` 返回 `cli://grok`，`synthesize_messages` 缺 `complete()`
   那个 cli 分支，发包前 URLError（三轮误标 zhipu，因为存证的 provider 字段填的是
   composer 的）。**#402 已合**（merge `6876a6e7`），8792 已切，
   T+55s healthy / readiness 13/13 / 账本 record+check ok。
   **R5 判据达成**（`run_20260826_021909_393039`）：`shadow.status=repaired`
   离开 `judge_unavailable`，`judge_report` 是真实 grok 判定，`degrades=[]`，
   残差**首次真上场**；名单侧零回归（31 公告号全部包内、主名单 21 行零删除）。
2. ~~模型解读反证行越界~~ **归因改了，别按旧方向加固**。初版写「绑了
   `disc:summary:1` 而非反证行自己的 claim」，并提议「在 registry note 里点名
   『解读反证请绑 disc:counter 行』」——**`disc:counter` 根本没进 prompt**（见上面
   错 1），在 note 里点名它没用。真正的杠杆在预算与排序。
   **PR #405 已开**：① registry 行里的 atom 去掉与同行逐字重复的三个键
   （`claim_text`/`entity_id`/`provenance`，占整段 70%）；② 反证与缺口 claim
   预算内优先占位，不许被支持性事实挤掉。实测同一个包：19 行 → 32 行，
   `disc:counter`/`disc:gap` 从「一条没进」变成必进。
   遗留：主名单仍有 1 行会被「排除名单里含医药/公告字样」的行按 query 加权挤掉
   ——通用 ranker 分不出主名单与排除名单，要分需要动 spec 的领域模型，单独一轮做。
3. **新发现的 fail-open（judge 修好后才暴露）**：judge 判否并点名两句越界，
   其中一句**原样上了公开稿**。根因在 `resolve_judge_sentence_indexes`：一条 issue
   带引文能定位，`resolved` 非空就直接 return，另一条只写中文「句3」、不带引号的
   驳回被整条吞掉。**PR #404 已开**（判据改成按条数比，少于报的条数就并入原序号）。
   此前被 URLError 掩盖着——judge 从没跑起来，残差一律 fail-closed 回纯包，
   那是**偶然**的安全，不是设计的安全。
4. deterministic_issues 的 4 个标题 warning（建议标题集合外）不阻塞；若要消除，
   把残差契约的建议标题集合与 composer 实际产出对齐。
5. **shadow 各阶段没有落 trace**（只有 `disclosure_residual_gate` 一条），
   上面第 3 条查了很久才定位，靠的是拿归档件在生产 revision 上逐段重放。
   补一条事实投递（至少记 judge 报的序号与实际采用的序号）能把这类问题从
   小时级降到秒级。

## 踩过的坑

- `disclosure_scan_pack` 顶层 import `answer_model` 会循环，import 下沉函数内。
- `AnswerSpec.system_notices` 是必填位置参数。
- worktree 无 venv：用主树 `.venv-workbench/bin/python`，cwd 决定加载哪份代码。
- 账本 `record`/`check` 的 `--repo-root` 必须给**数据仓**（`$FINANCE_WS`），给快照
  会把 switch 行写进快照自己的 `state/`（误置账本），check 则读到 `~/.finance-runtime/`
  回退位的陈旧账。
- shadow 存证的 provider/model 字段是 **composer** 的，不是 judge 的
  （`ask_synthesis.py` 里 `provider=composed.provider` 与
  `failure_reason=judge_reason` 装在同一个结构体）——判 judge 用哪个 provider 要看
  `judge_provider()` + **活进程的 env**（`ps eww -p <pid>`），不是抄启动器脚本。
  这个字段误标一次就烧了三轮，judge 修好后它更误导（写着 zhipu，实际跑的是 grok）。
- 收据的脏判定会漏掉 porcelain **首行**：`_git` 对整段输出做 `.strip()`，未暂存
  改动行形如 `" M path"`，首行前导空格被吃掉后 `line[3:]` 多切一个字符。当它是
  唯一的脏代码文件时 `dirty` 记成 False，收据自称干净树。写方 `conftest.py` 与
  检方 `scripts/check_test_receipt.py` 是同一份逻辑的两个拷贝，两边都有。
  **PR #406 已开**。现场：#402 那份 6533 收据只列出 `test_grok_cli_judge.py`，
  漏掉同样未提交的 `llm_refine.py`。
- 别拿 `verified_facts` 的长度当「进了 prompt 的条数」。要知道模型实际看到什么，
  就用生产 pack 重建 `grounded_claim_registry_block`——registry block **没有归档**，
  事后只能重放。

## 工具沉淀盘点

无新脚本。「组件写正文、模型只写边注」的补全应用：claim 集就是组件事实的完整
投影，投影缺行（[:8]）= 边注必然越界。

**但本轮质检推翻了「投影已补全」这个说法**：投影在 spec 层补全了（64 条），
在 prompt 边界又被预算砍回 18 条。可复用的判据是——**「投影完整」要在模型实际
读到的那一份上验，不是在生成它的那一份上验**。同类形状本仓已有先例（额度写进
telemetry 但下游没读）。验法很便宜：拿生产 pack 重建 registry block 数行数。

第二条：**偶然的 fail-closed 会掩盖真正的 fail-open。** judge 因 URLError 从没
跑起来时，残差一律回纯包，看起来很安全；transport 一修好，`resolve_judge_sentence_indexes`
吞掉半个驳回的问题立刻暴露成「judge 点名越界的句子照样出稿」。**修好一个坏掉的
组件之前，先想清楚它坏着的时候是谁在替它兜底、那个兜底是不是设计出来的。**
