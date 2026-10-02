# PR16 个股深挖二轮追问：后端根因定位，不是 E2E 修复

范围：原 PR HEAD `75af45fc064ec83ae03f8573634f9c5b4a236f84` 的专项 owner 路径。
比较器返修另见 `2026-10-02-pr16-qc-fix.md`；本片只新增诊断脚本和文档，
未改产品 runtime、Controller、完成度校验器或浏览器断言。真实模型请求 0。

## 1. 结论

不是公司指代丢失，也不是仅仅 UI 没刷新。第二轮仍是 `英维克 / stock_deep_dive`，
owner 收到的任务指纹与编排器一致；**输出合同继承后带上重复旧名 `direct_answer`，
专项路径没有做已有别名去重，而完成度校验器不认识这个旧名**。
其余四项均通过，唯独此项没有候选 claim（可核对的主张），触发 fail-closed：
宁可交付缺口提示，不把未完成草稿当成完整回答。缺口提示没有公司名，故 E2E 断言失败。

这是当前确定性门禁的直接成因，不是“回答质量已经足够”的证明。

## 2. 实际观测链

入口使用真实 `POST /api/conversations` 及 `POST /api/conversations/{id}/messages`，
通过 ASGI TestClient 在进程内调用服务，不启动浏览器、不连接生产服务。
请求固定为手动选择 `stock-deep-dive`：

1. `请个股深挖英维克的液冷业务`
2. `那它的主要风险和下一步验证是什么？`

| 阶段 | 真实观测 | 源码定位 |
|---|---|---|
| 首轮 TaskFrame（任务要求） | `stock_deep_dive`，要求 `direct_assessment / supporting_evidence / counterpoint` | `task_frame.build_task_frame`、`derive_required_outputs` |
| 第二轮初始 TaskFrame | 主体已是英维克，但初始题型为 `general_finance_qa`，默认要求 `direct_answer / evidence_boundary` | `turn_controller.decide_turn` |
| 追问继承 | 继承 stock owner 和首轮三项，并与当前两项合并，形成五项 | `research_contract.build_turn_intent` |
| 重定题型 | `rebase_task_frame` 虽排除了原 frame 的旧类型默认项，但 `required_outputs` 参数已经带着五项，又把它们带回来 | `task_frame.rebase_task_frame` |
| 专项合同投影 | owner 与 frame 的指纹相等；五项原样转为校验要求，未走 `_merge_frame_outputs` 的别名去重 | `conversation_orchestrator._specialized_owner_required_outputs` |
| 候选主张查找 | `direct_assessment` 有三条候选，`direct_answer` 为零；后者既无精确匹配，也无命名空间规则 | `task_fulfillment._claim_candidates` |
| 最终门禁 | 其余四项 fulfilled；仅 `direct_answer=missing/no_candidate_claim`，总体 missing | `evaluate_answer_spec_fulfillment`、`evaluate_task_fulfillment` |
| 发布正文 | 原草稿被缺口投影替换；消息 completed 不等于任务 complete | `fail_closed_answer_spec` 及编排器交付分支 |

最终第二答 SHA256：
`32ce560097813cddf6569e61e4ee60c3b0ec376b11535b10996330bda45e8e7c`，
与原审查的基座/HEAD 回放逐字相同。原审查已经在 `19c820824` 复现同一失败形状；
本轮没有另跑基座浏览器，不能据此豁免 PR 的 CI 红灯。

## 3. 单因素诊断：只消除一个重复名称

新增 `scripts/review_probes/probe_owner_followup_contract.py` 包装实际调用，记录输入输出，
**总是把原校验结果返回产品**。另在旁路用完全相同的正文和 AnswerSpec 重算一次：
仅在已有 `direct_assessment` 且现有别名表确认映射时，移除重复 `direct_answer`。
`supporting_evidence / counterpoint / evidence_boundary` 全保留。

| 同一份正文、同一份证据 | 结构校验结果 |
|---|---|
| 原五项合同 | missing，唯一原因 `direct_answer/no_candidate_claim` |
| 只去掉重复旧名后的四项 | complete |
| 产品真正收到的结果 | **仍为 missing**，公开正文仍是原失败提示 |

最初探索还去掉了 `evidence_boundary→counterpoint` 的重复，结果也为 complete；
随后另起证据目录做上述更窄对照，以免两处变动混淆原因。两次原件均保留。
这不是将旁路结果接进产品，更不是浏览器 E2E 已通过。

## 4. 为什么不能只补映射就宣布解决

门禁把 `direct_assessment` 判过所用的文本是“英维克的研究范围是……”，
绑定 `ONTOLOGY`（研究框架），并不是一份已经独立验收的“主要风险和下一步验证”分析。
门禁前草稿确有“反证与缺口”“下一步如何验证”栏目，但内容偏通用，且有重复公司段落。
栏目存在和合同名称自洽，只能证明结构，不证明主体专属、依据充分或回答切题。

后续独立产品修复应同时：

1. 收敛继承/专项投影的输出身份，复用已有语义规则，避免无条件丢弃真正的新要求。
2. 钉住风险与验证诉求的任务输出及正文覆盖，不能拿公司定位摘要代替追问答案。
3. 加正反回归：相同含义去重；目标槽位不存在时不去重；真正缺风险/验证仍拒收；
   更换主体、不同续问和无 provider 的降级仍正确。
4. 保留现有 desktop/tablet/mobile 浏览器断言，在隔离依赖环境重跑，并重新取得 CI。

本轮不实施以上产品修复，也不加公司名特判、不删用例、不放宽门禁。

## 5. 证据与复现

私有证据根：`~/.finance-runtime/reviews/pr16-fix-20261002T062241Z/`。

- `owner-followup-probe/`：首次探索（去重两处），不作为单因素结论。
- `owner-followup-single-alias/`：上述单因素诊断；`contract-trace.json` 记录继承，
  `gate-evaluations.json` 保存门禁前正文/证据及两份判决，`result.json` 记录代码哈希。
- 原独立审查：`~/.finance-runtime/reviews/pr16-quality-20261002T055855Z/` 的
  `replay-{base,head}/`、`replay-comparison.json`、`pr16.json`。

```bash
# 用仓库指定的 workbench Python，output 必须是新的目录。
python scripts/review_probes/probe_owner_followup_contract.py --output <新证据目录>
```

探针独立复制小型测试 fixture，用户态与 Episode 目录均隔离；清除 API key，禁 Keychain，
断言无 provider。Python audit hook 拦截连接、DNS 和数据报发送，子进程通过
`sitecustomize.py` 继承；实测两次诊断的网络尝试均为零。它不是 OS 网络沙箱，
也没有替代 Playwright 浏览器、干净 lock 环境或自然模型金融质量验收。
共享 httpx `0.25.2` 与 lock `0.28.1` 的差异仍未修改。

原 HEAD `75af45fc0` 的已核 CI（run `36965829455`）：Python/frontend 成功，
E2E **31 passed / 3 failed / 2 skipped**，聚合 workbench-check 失败；registry-check
在 run `36965829397` 成功。此处引用原审查快照，不声称本修订已跑远端 CI。
