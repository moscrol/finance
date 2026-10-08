# 普通 Episode 成稿合同 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 已批准parts接口进入同一真实模型成稿合同，开场/修订/finalizer/准入不各教一套。

**Architecture:** 两入口纯计算finish_authoring module集中已有格式知识；harness是runtime既有接触面。D4与材料owner不搬走，native events承载实际描述，旧回合不自动迁移；新system改变与legacy payload/public不变分别验证。

**Tech Stack:** 现有Python dataclasses/mappings、ResearchRunContext/FinanceResearchHarness/EpisodeStore、locked venv、已有捕获模型Adapter。

---

设计见同日期ordinary-finish-contract-design.md；actual baseline为origin/main bd66，PR80已部署。外部三案minimal/flexible/caller及原独审在 `~/.finance-runtime/answer-evidence-quality-1007/owned-delivery-1008/`。原scope/task/window/预算和判官off不扩。只一名source writer，Root不并写。

## Task 1: 作者合同与编译的同一owner

**Files:** Create `intelligence/services/finish_authoring.py`; Modify `intelligence/services/episode_protocol.py`仅必要兼容adapter/作者编译接线；Test `intelligence/tests/test_finish_authoring.py`；既有material/owned准入测试不改弱。

- [ ] 先建真caller RED，schema/模板/编译同一variant，普通无目录默认parts自由块、material由旧owner、旧schema无context原样。接口类型只含json_schema/model_payload和编译envelope/claim origins/可选receipt，不新增状态机柄。

```python
author = finish_author_contract(ordinary_context)
assert author.model_payload['format'] == 'ordinary_answer_parts_v1'
assert author.model_payload['wire_template']['draft'] == ''
compiled = compile_finish_authoring({
    'status': 'partial', 'draft': '', 'answer_parts': ['原正文。'],
    'gaps': ['仍缺明确数据。'], 'bindings': [],
}, context=ordinary_context)
assert compiled.envelope['draft'] == '原正文。'
assert compiled.owned_answer is None
```

- [ ] RED后实现纯入口，复用现有材料编译及owned编译，保持旧类型/错误前后顺序；不得新JSON恢复器或compile.accepted自签。closed schema明确parts/legacy非重叠分支，未知ref或作者receipt不能通过。
- [ ] 模板仅自由示例不假ref；currentcontext/source/ACK重核由原owner做。单向imports无runtime依赖/重复谓词；material原schema/source/floor/历史例外保留。
- [ ] 只跑新模块+实际protocol/owned/material必要邻域，Ruff变更files；pathspeccommit。记录准确scope/dirty/head，定向绿不叫全仓。

## Task 2: 初始system与实际native前缀

**Files:** Modify `intelligence/services/research_harness.py`/`episode_protocol.py` build_episode_instructions/input、`intelligence/runtime/agent_episode.py`必要既有装配；`intelligence/services/episode_messages.py`只在实际必要兼容时改，不新override事件；Test `intelligence/tests/test_finish_authoring_runtime.py`。

- [ ] 真FinanceResearchHarness/registry/ContinuousAgentEpisode/JsonlEpisodeStore捕获模型RED：第一实际system不能仍普通draft-only，user真实finish_format匹配owner；工具后只从实际message读ref。

```python
messages = capture.request_messages[0]
assert 'ordinary_answer_parts_v1' in json.dumps(messages, ensure_ascii=False)
assert 'answer_parts' in messages[0]['content']
assert to_provider(derive_messages(native_events_before_request)) == messages
```

- [ ] 装配阶段取得同合同，声明最终正文规则与parts默认，但不要求选择refs/固定章节；nativeprompt实际记录当前描述。初轮空catalogue可自由写，ACK后才允许合法ref。
- [ ] 新请求可现代，旧未终态prompt则保持旧合同与eventbytes；用既有原生payload字段辨识，None不自授权新形式。恢复授权仍先于格式恢复。
- [ ] 实测数据完整query_basis/allowed card/hash未被format吞掉，legacy已有catalogue也可以合法draft且无receipt；Unknown/ref/noACK/当前cap/cutoff/owner负控仍拒。必要caller邻域后pathspeccommit，停止下一个阶段前自验。

## Task 3: 修订、诊断、兜底和恢复

**Files:** Modify `intelligence/services/research_harness.py::repair_goal_message`，`episode_protocol.py` steering/unsupported/finalization builder，`intelligence/runtime/agent_episode.py`真实repair/carry，`episode_finalizer.py`普通system/payload，`episode_restore.py`仅必要格式标识；Test `test_finish_authoring_runtime.py`及existing restore/repair/material控制。

- [ ] 捕获实际请求RED：unsupported/invalid提示不能另教完整draft-only，repair和finalizer共享format，材料每原分支不变。正反原因分开，不用verified呈现给拒收盖章。
- [ ] 当前context生成模型描述，编译重新授权，旧保存描述不可授来源；refs来自当回合sourceview。有效修订采用新receipt，invalid/timeout/carry沿旧draft同hashreceipt，格式不制造新binding/floor。

```python
assert (store.episode_dir(episode_id) / 'events.jsonl').read_bytes().startswith(original_event_prefix_bytes)
for messages in capture.request_messages:
    assert expected_format_id in json.dumps(messages, ensure_ascii=False)
assert carried_outcome.draft == previous_outcome.draft
assert last_finish_payload['owned_answer'] == previous_finish_payload['owned_answer']
```

- [ ] 确认格式只作为描述，field失效/未知/撤cap/收cutoff/缺durable源应在原源规则拒；有tool_result但旧证据checkpoint仍不能补evidence。真实native→semantic/public，free旁边错误不获prog证书。
- [ ] 一次必要caller邻域+session_projection/module layer/metadata变更规范核验；pathspeccommit，准确clean终点停source。不用反复跑旧602/657/1218刷绿。

## Task 4: 独立与同版事实验收

**Files:** Update `docs/agent-product-door.md`同runtimecommit；Root后实际完成再写本枝inflight/日期快照、现capability节点。

- [ ] writer交cleanHEAD/tree/base/source hashes，真实contractdiff、legacy/material/oldarchive/public不变矩阵与caller receipts；Root独立Spec→Standards；任何实质finding先修真实seam。
- [ ] 固定准确候选新全仓Python收据，fullscope与collected/counts验0；frontend6/registry5/各必要CI；normalPR attach、用户已有上线授权后正常merge，actualmain自身完整门禁/新快照/locked/FP13ready/strictledger/backup。
- [ ] 在真实新部署前登记新user/batch max1原题，不预写市场方向/expectedref。不重抽当前bd66。完整source/RAG、budget/model admission663、physicalattempt去重/全部nativeprefix、first/invalid/revision/carry/public/receipt分账冻结；独立同8准则整篇review。
- [ ] formatdelivery/adoption/fragmentqual/wholecontent四结论分别签，不能用parts缺席或存在直接判整题，不能把新旧不同库作严格A/B/整体胜Pi/长期记忆收益。若free仍错，第一次分叉继续根因，不以当前family默认为全文保真。
