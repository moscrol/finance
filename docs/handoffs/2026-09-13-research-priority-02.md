# 2026-09-13 · 研究进化 02「下一步研究排序」实现决策快照

分支 `feat/research-priority`，提交 `46922d3f`（实现）、`fb41459b`（进度）。规格 `docs/superpowers/specs/2026-09-13-research-evolution/02-research-priority.md`（`194241dd`），总合同同目录 README。写完不改。

## 背景

总合同把「时间长河后续优化」拆成六轨并行：01 判断维护、02 研究排序、03 方法验证、04 个人诊断、05 价值测量、06 Workbench 集成。02 的输入依赖 01 的 `judgment-maintenance/v1` 报告，最终由 06 接进 `GET /api/conversations/{id}/research-evolution`。用户已定的默认：单用户私有、市场库只读、不新增定时任务、排序结果只称「研究优先级」不称收益或概率。开工时 01 的模块在另一棵 worktree 里边写边改、未提交；06 尚未开工。

代码基线 `gitea/main@5fb13a8c`；本树从规格分支 `docs/river-next-specs@28804505` 开出（代码与 5fb13a8c 零差异，只多 9 份规格文档），这样 PROGRESS/BLOCKED 的路径与规格能在同一棵树里解析。

## 按发现顺序

1. **任务 0 核对符号**：`build_research_queue` 的条目是中文键、无 id、无对象引用 → 全部只能是 `legacy_unbound`（P11 由此成立）。`DataRequest.consumers[].user` 跨用户聚合 → 适配层只留 owner 的消费者。`ResearchTrigger.status` 六值里 hit/partial/miss 已裁决。`foresight.rank_questions` 与 `ranking_contract` 不复用、不改。
2. **合同层先写**：`validate_task` 归一深拷贝；越权 / 未知 schema / 裸时间戳整份拒绝并给稳定 `code`。`abandon_or_downgrade` 在校验层就要求 `condition_result=true` + 证据引用 + 对象引用，这是 P02 的第二道闸（第一道在适配器）。
3. **排序器**：分组 → 合并 → `evaluation_at` 可执行性 → 排序 → 贪心预算。冒烟时发现合成任务的问句 / 结束条件只提首条维护项 → 改成列全维护项。
4. **P10 红**：重复读取后报告 id 变了。原因是给「合并」统一改写了问句，而纯重复（同一来源两次）成员数 >1 也被改写。改为按**去重后来源数**判断是否合成。
5. **P09 红**：两个「未来记录」测试任务共用同一证据引用被合并成一条。这暴露了合并对 as_of / cutoff 的处理是「取首条」——改为取最新（同一证据在不同市场日重复观测，知识状态应是最新那次），测试改成不同证据。
6. **两条测试期望错**：现役队列把「降级/观察」也算进 `summary.total`（4 不是 3）；同组按 due 早→晚，09-10 到期的 unverifiable 项本就该排 09-11 前。修期望，不改代码。
7. **反向证伪**：M1 未知耗时当 0 → `test_p05_unknown_effort_is_not_zero_under_a_budget` + `test_effort_estimates_from_context_attach_by_source` 红；M2 hash 变化当放弃 → P02 + 冻结 golden 红；恢复后 55 绿，`cmp` 字节一致。用 `-B -p no:cacheprovider` 并先删 `__pycache__`。
8. **发现 01 在途模块可跑**：`ls /Users/a77/fwp-wt-judgment-maintenance-01/intelligence/services/judgment_maintenance/` 有 `assess.py`，且自带 `fixtures/research_evolution/01/complete/input.json`。用 `PYTHONPATH=<01 树>` 子进程跑 `assess()`，产物零改动通过 02。真产物与我手写合同夹具的差异：`knowledge_cutoff` 是日期、`condition_result` 是字符串、item 多出 `dependency_ref / condition_evaluation / first_known_day / management`。冻结为带来源哈希的夹具 + 一条测试；BLOCKED 写定稿后重跑。

## 决策与方案对比

| 议题 | 选择 | 被否方案 | 为什么 |
|---|---|---|---|
| 任务 id | `rt_`+sha256(合并键)；有证据引用 → (owner, effect, availability, 证据版本集合)，否则 (owner, effect, availability, 归一问句, entity_refs, as_of, due, 对象集合) | 沿用来源 id；把 policy_version 掺进 id | 同证据新增受影响判断时来源 id 会变，05 按 task_id 追踪就断；policy 进 id 会让换策略后历史事件全部失联，报告 id 已含 policy |
| 合并粒度 | 同证据版本集合 = 同任务，对象取并集；无证据时问句+实体+时间窗+对象全同才合并 | 文本相似度去重（现役 foresight 的做法） | spec P07 明令「文本相似但对象或时间窗不同不合并」；相似度阈值不可回检 |
| 合并冲突字段 | 耗时取已知最大；pit_grade 取最弱；as_of / cutoff 取最新；condition_result 不一致 → unknown + gap | 取首条 / 取平均 | 首条随排序漂（P10 红过一次）；平均会低估预算；unknown 是唯一不编数的三值结果 |
| 未到期条件 | blocked(not_yet_due, available_at=due) | 不生成任务；deferred | 要随 evaluation_at 跨越自动变可选（P13），blocked 有解除条件字段，deferred 没有 |
| 未来记录 | blocked(future_record)，不进评分 | 拒绝整份输入 | 拒绝会让一条脏记录拖垮整份报告；blocked 仍可对账 |
| waiting_release 到点 | 视为 actionable | 要求调用方改 availability | 06 只需注入时刻，不必重算每条可执行性 |
| 有预算时 max_items | 仍生效（默认 3） | 有预算就不限条数 | spec 把前三项写成界面约束，06 可传更大值；不确定时取保守 |
| max_per_object | 只对已绑定对象生效 | 对未绑定任务按问句分桶 | 未绑定任务没有对象身份，硬造桶会引入相似度判断 |
| 队列四桶 | do_ima / find_official → explore；wait_market → waiting_release；downgrade → skip | downgrade 也生成探索项 | 队列已判「减少研究投入」，再生成任务自相矛盾；skip 记录在 `skipped` 可对账 |
| 队列热度分 | 不读 | 作为同组次级排序 | P01：热度不改变证据等级；同组只按 due / 对象数 / 耗时 / id |
| 时间解析 | 日期 ≡ 当日 00:00Z 只用于比较；裸 datetime 拒绝；evaluation_at 必须带时区 | 裸时间默认 UTC / 默认本地 | 差 8 小时且事后看不出；拒绝会在接线第一天就暴露 |
| 01 → 02 availability | condition_unknown 且有 gap → missing_data，解除条件列 gap；dependency_missing → actionable fill_gap | 全部 actionable | 缺观测值时用户做不了判定，任务本身是「等数据」；而找回丢失引用是用户能做的事 |
| 01 管理状态 | closed/superseded/rejudgment_requested → skip；snoozed → deferred(user_snoozed) 且仍进 critical 名单 | snoozed 直接 skip | 用户推迟不等于关键变化消失，spec 要求不隐去 |
| 02 是否触用户态 | 不触：包内无文件 / 库 / 网络 / 时钟 | 自己解析 `userspace.user_space` 读 01 报告 | 总合同 §4：01–05 只收已验证输入，路径解析归 06 |
| P12 真输出 | 用 01 在途树的真 `assess()` 产出并冻结（标 synthetic、带哈希） | 等 01 定稿再联测 | 早一天发现日期 / 字符串 / 多余键三处口径差异；定稿后重跑成本很低 |
| 沉淀成工具 | 未做：收据 runner 与跨树探针只留在收据 / BLOCKED / 10_knowledge | 加进 `scripts/` | 总合同白名单不含 `scripts/`；跨仓 harness-reference 当时树脏 |

## 验证与收据

- `docs/superpowers/plans/2026-09-13-research-evolution/02/receipts/final-46922d3f.txt`：collect-only 56、suite 56 passed、ruff 0、现役 7 套 98 passed、三门禁 exit 0，绑定提交 SHA。
- `mutation-01-*.txt` / `mutation-02-*.txt` 各 exit 1、2 failed；`green-after-restore.txt` exit 0、55 passed（当时尚未加 P12 真产物测试）。
- pytest 读数收据在 `~/.finance-runtime/test-receipts/`（时间戳-revision 命名）。
- 不成立的结论：任何「用户省时 / 更准 / 漏检更少」——本轨没有 field 样本；所有夹具 synthetic。

## 后续要做 / 不要做

要做：01 定稿后按 BLOCKED §1 重跑替换 `from_01_inflight_assess_report_synthetic.json`；06 接线时 `evaluation_at` 取服务端 UTC，owner 取部署允许的用户上下文；05 用 task_id + policy_version 关联。

不要做：不要在 02 里读 `userspace` 或系统时钟（P13 有源码级断言会红）；不要把队列「优先级」接进排序（P01 会红）；不要为让 golden 通过而改 `expected_combined_synthetic.json`——它红就说明合同或规则变了，先改合同文档再更新夹具；不要把 abandon 校验放宽成「降级为第 2 组」——spec 要求拒绝整份输入。
