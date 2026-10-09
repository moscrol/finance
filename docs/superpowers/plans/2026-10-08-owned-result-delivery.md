# 同源计算结果文字所有权 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 同源已计算结果由程序生成可核验文字，作者选择结果并自由分析，明确区分局部保真与全文语义未评。

**Architecture:** 新纯计算module放在已有ToolObservation投影、finish准入和最终公开核验seam。稳定ref来自已获授权source bundle，ownership receipt随已有finish事件保存；旧None不新增wire/序列化字段。只支持已拥有的D4资格/规则/范围，不追加IO或第二引擎。

**Tech Stack:** 现有Python dataclasses、ResearchRunContext、ToolObservation、EpisodeStore、canonical market_feature_store.signals；locked venv。

---

原件与设计：`docs/superpowers/specs/2026-10-08-owned-result-delivery-design.md`；外部只读证据在 `~/.finance-runtime/answer-evidence-quality-1007/round2-release/`，不要把私有整包或宿主路径写进产品。CI fixture只取已授权公开行情小片段并去掉用户/run/私有locator；原真实完整输入另由本地只读控制验证。

## Task 1: 纯计算source catalogue与结果生成

**Files:** Create `intelligence/services/owned_results.py`; Test `intelligence/tests/test_owned_results.py`。

- [ ] 添加实际工具source的小fixture：9/30/LM002.LOCAL/990080.FP，pct3.5228/diff44.2976/amount349.327，strictfalse/complete；同源scope4主题68行/24预览/44省略。真实事实键连接而非标题匹配。
- [ ] 先红：测试两个公开入口的observable行为，source compiler不借整Episode摘要，render不能接受模型覆写结果值。

```python
catalogue = compile_owned_results(source_observation, authorized_context)
ref = catalogue.ref_for(("2026-09-30", "LM002.LOCAL", "990080.FP"), "strict_double_red")
result = render_owned_parts([{"result_ref": ref}], catalogue)
assert result.free_blocks == 0
assert result.owned_blocks[0].value is False
assert "不满足" in result.draft
assert catalogue.unavailable("market_unique_mainline")
```

- [ ] 实现以上两个入口及其只读值对象；严格解码已登记D4 schema、复用canonical函数/常量、source事实键及scope，按source/input/definition的canonical JSON生成稳定digest和短ref。源未知返回无catalogue；源冲突返回带稳定reason的拒收。源卡hash与metadata只是身份，不自己授真实性。
- [ ] rendered_result包含draft、精确owned区间、free块数和程序生成receipt；ref-only和自由str文档块分别处理，拒绝ref对象的未知字段、未知ref和嵌套/篡改。None为未知，False不进数池。
- [ ] 一次必要控制覆盖真实true/false、NULL、500/501、diff10、source flag冲突、异日期/对象/单位/scope/定义及原None。原旧坏稿不得转绿。
- [ ] locked venv跑该模块与ruff；pathspec提交core/测试。不要增加十几个配置开关或派生类型族。

## Task 2: 现有投影/ack/finish接线

**Files:** Modify `intelligence/services/research_harness.py`, `intelligence/services/episode_protocol.py`, `intelligence/services/research_contract.py`（仅必要尾置私有来源缓存）；Test `intelligence/tests/test_owned_results_harness.py`, existing `test_research_harness.py`/`test_episode_protocol.py`。

- [ ] 先用真实FinanceResearchHarness投影建立RED：catalogue在同一D4结果模型投影中出现短ref和对应文字，所有原query_basis完整保留，私有source witness不进模型。
- [ ] 在project_tool_result派生源视图，在实际消息被追加后的acknowledge_tool_result登记同一source。每run/context独立、无全局慢IO锁。复用现历史交付记录，不能覆盖历史状态。

```python
projection = harness.project_tool_result(observation,
    evidence_so_far=evidence, seen_prose=set())
harness.acknowledge_tool_result(observation, projection, context=context)
admission = harness.admit_finish({
    "status": "completed", "draft": "", "gaps": [],
    "bindings": existing_valid_bindings,
    "answer_parts": [{"result_ref": published_ref}, "这是后续待验证的研判。"],
}, context=context, evidence=evidence, registry=registry)
assert admission.accepted
assert admission.owned_answer is not None
assert admission.owned_answer["free_blocks"] == 1
```

- [ ] ordinary finish_json_schema增加可选封闭answer_parts；现material_author_schema保持，拒新parts与material render混用。parts在场draft必须空；生成正文后继续所有原binding/hash/材料/输出/floor检查。EpisodeFinish与FinishAdmission尾置可选owned_answer，None不增加旧键。
- [ ] source登记cache可只在context内存在、默认空；用严格source/context授权重建，不能从作者receipt或旧公共文本授日期/IO权限。更多元数据不算更多证据卡。
- [ ] 跑实际harness正负控、schema闭合、legacy byte control、材料/private/source/cutoff邻域测试。旧高要求断言不改弱；pathspec提交。

## Task 3: 原生finish/repair/carry/finalizer/恢复保真

**Files:** Modify `intelligence/runtime/agent_episode.py`, `intelligence/runtime/episode_finalizer.py`, `intelligence/services/episode_restore.py`（仅必要控制面/恢复）；Test `intelligence/tests/test_owned_results_runtime.py`, `test_episode_restore*.py`, `test_repair_carry_just_written_finish.py`与实际已存在的carry/recovery测试。

- [ ] 用真实AgentEpisode与JsonlEpisodeStore、模型替身先红：主finish保存actual被接纳owned_answer，工具返回以后追加model/finish不改变ref身份。
- [ ] 主/repair/finalizer正常finish只在receipt非None时追加同名payload；在carry旧稿、格式拒收、超时/取消路径，选择与被采用draft摘要一致的先前有效receipt，拒绝新稿/旧receipt错配。旧路径不得增加空字典或额外event。

```python
extras = {} if admission.owned_answer is None else {"owned_answer": admission.owned_answer}
ledger.add("finish", {**existing_finish_payload, **extras})
```

- [ ] 重开时从原获准tool_result和当前context重建catalogue，再验证source/ref/定义/draft一致；缺来源或改变权限停在具体缺口，不重新查DB/模型、不扩大权限、不从旧text反推choice。不能把整个最终Episode SHA当合成前稳定ref。
- [ ] finalizer通过已有payload看到已送达refs和同一次finish字段规则；不传private source身份，不改预算/次数。对不支持parts的旧/材料/非continuous调用维持原行为。
- [ ] 测真正caller主finish、有效repair、invalid repair→carry、finalization recovery、缺持久源、重开restore、权限收窄；源/公开旧None比对。pathspec提交。

## Task 4: 真实semantic/public出口资格范围

**Files:** Modify `intelligence/services/episode_semantic_verifier.py`（小接线，逻辑仍收进owned_results）；必要Modify `intelligence/runtime/continuous_turn_adapter.py`私有产物投影；Test `intelligence/tests/test_owned_results_publication.py`, original numeric/condition/material controls。

- [ ] 原真正semantic boundary RED负控保留。真实新finish的receipt通过同一verifier，owned false保真；自由错句无自动certification，原A845全文仍不改判。
- [ ] 在数值条件检查中仅排除程序生成receipt所证明的精确owned spans，范围来自被采用draft/source重算，不是文本命中或通用数池。相邻自由条件和未来持续数字照旧；定义角色10%/500仅获本地规则来源资格。
- [ ] 最后public出口重核实际仍存在的owned文本/范围，并输出可选coverage私有回执（owned faithful/free unassessed/changed或removed）；不修改legacyNone公共字节或将free正文自动semantic通过。其它合法删改不算已送达；若会改owned结果，应拒其仍保真声明并按原有机制保真/保留具体问题。
- [ ] source/calc身份、写手自选kind/basis、合法schema或正确ref不认证未声明自由段落，原坏稿和故意相邻否定/因果段仍未评。最终owned片段错误不能藏在pending括号。
- [ ] 测R20原历史/未来角色边界、owned结果vs同字自由重复、公开删改、private泄漏；无新judge/call/deadline。pathspec提交。

## Task 5: 独立与发布验收

- [ ] 固定clean候选，准确code/tree/source hashes；Spec核本设计、Standards核仓规范，任何实质finding先修真实接缝，不改弱fixture，旧负控保留。
- [ ] 更新docs/agent-product-door与本分支inflight，说明已实现确定性保证和仍未评的自由正文；capability graph只更新现节点，不新建第二清单。
- [ ] 全仓Python收据核fullscope及失败数；frontend六项/registry五项/触发CI叶均绿。新code PR正常合入（已有用户执行上线授权），实际main自己完整门禁；固定snapshot与locked venv，按既有switch helper核8792完整SHA/fingerprint/13readiness/ledger/备份。
- [ ] 新生产部署后沿原题/实际预算/实际model/RAG新用户新批仅一次首答，另注册max1，旧批只读。原生完整物理attempt账、所有模型前缀/child分支、首稿修订公稿身份冻结，独审全文。局部ownership绿不得代签整题或整体胜Pi。

**全程不做：** 同版重抽、评审真值进作者prompt、新judge、增预算、跨用户数据、写生产DB、整库copy2、Root与Pi双写同一计算、动ask_synthesis/Pi在途树或重新合旧PR74。
