# P1b 第一片验证：输出来源保真

## 结论与固定对象

**本片作者离线 Python 工程验证通过；不是完整 P1b、合入/发布批准、独立审查或金融回答质量证明。**

| 对象 | 固定值 |
|---|---|
| 工作树 / 分支 | `~/fwp-wt-harness-output-provenance-1003` / `feat/harness-output-provenance-1003` |
| 基线 | P1a 文档 tip `0ac1ec6e11287d769969e4e12b24e14b7ee0a10c`，继承产品/测试 pin `7513d476b` |
| 初始实现 | `0f1853774a53184a6a658beacf208617cf330af3`，全仓首轮有8项失败，不能作为全绿版本 |
| 最终代码、测试与变异 pin | **`c18d6f0fe73f1ee0c9d631ad7b302ef24727a4e6`**，补历史继承装配与材料恢复测试 |
| 证据根 | `~/.finance-runtime/reviews/harness-output-provenance-20261003/` |
| 解释器 | `/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python` |
| 环境 | Python 3.12.13、httpx 0.28.1、依赖指纹 `66726d345bf37ce5`；`FORESIGHT_LLM_KEYCHAIN=0` |

方向承接 `acc743c84` 的 model-owned-harness spec，范围以[本片计划](../superpowers/plans/2026-10-03-harness-output-provenance.md)为准。只有本地实现与验证，无 push、合并、部署或新增真实模型请求。环境未升级；正式全仓运行移除了环境中的 API key/token/secret/password，未读取模型凭据。相邻树仅作只读核对和明确基线测试，没有整枝搬入补丁。

## 实现及证据边界

| 接缝 | 实现 / 实测 | 不能据此声称 |
|---|---|---|
| 输出身份 | `output_requirement.py` 提取 `RequiredOutput`；`research_contract.py` re-export 兼容旧导入。`origin` 与 `required` 分离；`merged_origins` 保留别名来源并集；含用户来源时拒绝可选 | 自然语言解释已正确，或 origin 就是用户授权证明 |
| 可信装配 | TaskFrame 元数据须为合法唯一输出子集；模型 alignment 不能改来源。QueryEnvelope 额外、非题型/词面默认的槽标为可选 heuristic；研究程序遵循 `FactSlot.required`；自动 prior/prime/前瞻挂载保持可选；全局 advisory 名单退出必需性裁决 | 所有旧默认槽已迁移为建议，或已经开放题型/主体/时间窗在线修订 |
| 用户要求保护 | 同名已有要求不被附加建议降级；普通重基、个人回顾、材料编号装配、历史续问重建都保留已有用户要求及其描述/来源见证；历史重建同步过滤不再使用的建议元数据 | 跨所有自由文本输入自动抽取用户义务已完成 |
| 权限与 grounding | 元数据不授予工具、历史算子或无证据出口；证据资格仍由原目标执行槽及材料权限装配器控制；材料题 `answer_q*` 为 user_request，边界为 runtime | 仅凭来源字段即可证明证据支持结论 |
| 消费者 | frame→factory/别名合并/专项 owner→实际模型输入/终局恢复提示→履约报告/补写/失败投影保留来源及有效必需性；必需性合并取 OR | 原正文词面门、公开交付语义或旧身份候选的正文红例已修复 |
| 两条运行入口 | 连续 Episode 与 SDK 各用脚本模型、本地工具实跑“缺可选项可完成 / 缺用户项不可完成”；校验实际提示、工具调用、证据、终态。`build_episode_input` 与 finalizer 收同一来源 | SDK 已接 PLAN 修订、真实模型行为或完整 HTTP 新计划交付已验收 |
| 旧兼容与恢复 | 从未修改的 P1a 树导出真实 frame/授权快照夹具；新代码精确对比旧 payload/hash。legacy 默认省略新增字段；新来源进入 hash/授权比对，来源变更或见证丢失拒绝旧快照恢复 | 合同/存储版本已分离，或允许 v1 快照自动迁移/重签 |

旧实物夹具：`intelligence/tests/fixtures/output-provenance-legacy-authorization.json`，来源 revision 为 `0ac1ec6e1`，旧 frame hash 为 `36a40b44b6c34a0e2e6472ac7fc07188d4f830b975533a1f3ebaf3cf4cf539cd`。不是新代码自写自读的兼容证明。

## 最终 pin 的工程读数

| 检查 | 实际结果 | 证据根下路径 |
|---|---|---|
| 干净树全仓 Python + Ruff | **18832 passed / 0 failed / 0 error / 76 skipped / 2 xfailed / 18 warnings**，996.33s，门禁 exit 0 | `full-2-gate.log`；`full-2/gate-wOouB814/pytest.log.txt`、`pytest.json` |
| 收据适用性 | full-scope、仓根 target、revision 精确等于 c18d6f0fe、解释器/依赖一致、dirty=false、依赖门未绕过，exit 0；**collected=18910=18832+76+2** | `full-2-receipt-check.log` |
| 本片13项变异 | **13/13 捕获**，每项还原后绿；前后核心套件 **54P→54P**；还原字节哈希等于该 pin 的 Git blob | `mutations-2/results.json`、逐项 log/JUnit/diff；`mutation-audit.json` |
| 继承的P1a九项变异 | 在**同一 c18d6f0fe** 重新执行，**9/9 捕获**；前后所选五文件 **295P→295P**，不是搬用 P1a 的历史321P | `p1a-mutations-current/results.json`、逐项原件；`mutation-audit.json` |
| 注册表/台账五项 | parseability、registry、tables、views、ledger crosswalk 均 exit 0；台账反向引用仍有98条 warning，未清理 | `registry-receipt.json`、`registry-1.log` 至 `registry-5.log` |
| 本地提交检查 | 适用的密钥/大文件/冲突、Ruff、分层、路径、字段、数据集归属、工具可达性及运行目录保鲜检查通过；不适用项未算作执行 | `implementation-commit.log`、`history-fix-commit.log` |

76 skip 和2 xfail 是全仓实际输出；本片没有增加 skip/xfail 或删掉正常红例。warning 包括 Starlette/httpx 弃用、数值模型 RuntimeWarning、`datetime.utcnow` 弃用；没有为求绿修改共享依赖。全仓绿后 `run_main_gate.sh` 已清除它自己的 `full-2-basetemp`；红轮 `full-1-basetemp` 保留。三个变异临时树均由 runner 还原、核净并移除，未留下后台任务。

### 本片变异明细

定义：[output_provenance_mutations.json](../../scripts/review_probes/output_provenance_mutations.json)。复用既有隔离 runner；每项唯一锚点、可编译、实际执行非空、无收集/夹具 error、无 skip。红轮既包含目标断言，也包含元数据丢失的 KeyError 和破坏合法构造后的契约 ValueError；它们不是导入/语法失败，不统称“所有都是 AssertionError”。

| 破坏项 | 失败 / 执行 | 还原通过 |
|---|---:|---:|
| 程序可选项被提升 | 2 / 2 | 2 |
| factory 丢 frame 来源 | 5 / 5 | 5 |
| factory 全部强制必需 | 3 / 5 | 5 |
| 别名合流抹硬要求 | 1 / 1 | 1 |
| 别名来源并集丢失 | 1 / 1 | 1 |
| 未知元数据被静默接收 | 1 / 8 | 8 |
| legacy 序列化形状改变 | 1 / 1 | 1 |
| 信封建议变必需 | 1 / 1 | 1 |
| owner 回落旧默认身份 | 2 / 2 | 2 |
| 履约报告丢来源 | 5 / 5 | 5 |
| 重基丢用户元数据 | 1 / 2 | 2 |
| 历史重建丢用户义务 | 2 / 2 | 2 |
| 历史重建留下孤立元数据 | 2 / 2 | 2 |

变异是作者构造的反证，不是独立评审或产品误判率。P1a 九项同版复验仍只证明计划撤回、拒绝派发、截止和可选反馈边界，没有补上 SDK PLAN 接纳点。

## 失败与返修历程（不覆盖原件）

1. 新增测试先 **12F**，实现后 **12P**；`red*`、`iteration-1*` 保留。早期 `related-1` 指向不存在的测试文件，exit 4、零测试；不能当验收。
2. 相关回归曾 **1099P/1F/1S**：legacy 恢复提示被新增字段改变；修为省略 legacy origin/空来源集合。四个运行入口用例曾共用活根预算 ID，后来各用唯一任务 ID；本地工具 trace 也改为真实 `ProviderTrace`，没有放松终局来源核验。
3. `0f1853774` 固定相关29文件 **1436P/1S**、收据校验通过，11变异捕获且52P前后恢复。这仍漏掉全仓历史续问装配接缝。
4. 同版全仓首轮 **18819P/8F/76S/2X**，1017.29s、exit 1：材料题对象构造更早拒绝可选，落在旧测试的 `raises` 区间外；其余7项是历史续问替换输出 ID 后残留元数据导致的**本片真实回归**。基线 P1a 三个历史文件 **170P**，证明不能归咎既有失败。证据：`full-1/gate-T8I2FGFN/`、`baseline-history*`。
5. 新增历史重建两例先 **2F**（`history-provenance-red*`）。修 controller 同步迁移 ID/元数据，保留直接或合并来源中的用户义务；材料题同时保留 legacy 与新来源的构造/恢复拒绝，不弱化保护。返修相关33文件 **1675P/1S** 是提交前 dirty 读数，不移签到新 SHA。
6. 本地提交 `c18d6f0fe` 后，重新执行上述全仓、13项新变异、9项旧变异和注册表检查，才得到本报告的最终结论。旧失败、旧版收据与当前 pin 分开记录，不相加。

## 未验证范围 / 下一片

- **前端 lint/typecheck/unit/build、浏览器 E2E、GitHub Actions、本组合独立规格/代码质量审查未执行**；本树没有安装前端依赖，未借相邻树结果签字。因此不是四叶齐全的合入门禁。
- 新增运行入口用脚本模型；全仓已有 Workbench HTTP 集成回归通过，**不等于新来源/PLAN 组合从完整 HTTP 入口到自然模型公开答案的专项验收**。没有新真实金融样本。
- 代码地图开工为空且 vault 查询不可用，未将空图作为完整架构结论。锁环境可用不代表共享漂移环境已修。
- 题型/主体/时间窗在线修订、根请求锚点与解释 revision、合同/恢复版本分离、SDK PLAN 接纳、旧词面裁决退出仍属于后续 P1b；本片保留旧默认 legacy 必需性，不能宣称默认模板权力已全部退出。
- R17/R19 已封存，不补跑；R18工程工作已被R19承接，不是遗漏实验。正式完整8792×薄ReAct四格先于240；本片无权放行。

具体取舍、并行工作核对和下一片验收边界见[日期交接](../handoffs/2026-10-03-harness-output-provenance.md)，当前接手入口见[inflight](../handoffs/inflight/feat-harness-output-provenance-1003.md)。最终文档 tip 与 Memory 回写由私有证据根 `closeout.json` 记录，不能把后续 docs-only tip 冒充 pytest pin。

## Memory 回写状态

已在独立树 `~/agent-memory-wt-harness-output-provenance-1003`、本地分支 `feat/harness-output-provenance-memory-1003` 提交 **`c33b37dc6f7b4c7635b61dbac8fc20333879bd0e`**：项目看板/一行交接索引、现有能力图谱、现有闭环原则页。只改非受保护区；没有修改共享 Memory 主目录，也没有推送。**这是待整合的本地回写候选，不是共享主线已同步。** 主目录有定时双向同步，为遵守本轮禁止推送的边界，没有直接写入它。

- 同一 Memory 基线 `d6d3b943` 上，写前/写后 lint 均 exit 1、**46 error / 31 warning**；错误列表逐条相同、无新增错误。仅项目页超长 warning 的字节数随两行新增而变化，既有缺字段/死链/镜像漂移未修。证据：`memory-candidate-baseline-lint.log`、`memory-candidate-lint.log`、`memory-candidate-lint-comparison.json`。
- 图谱审计 exit 0，新增三个断言均标 **PENDING（只在候选分支）**；全表110行/335断言，其中288条在途或未校验。这个返回值不证明候选合入、部署或全图行为正确。证据：`memory-candidate-graph.log`。
- 提交记录：`memory-candidate-commit.log`。后续进入共享主线需另行授权/整合，不能把原有 `d6d3b943` 自动同步提交算成本窗动作。

## 复跑入口

固定 pin 的干净树、上述锁解释器，设置 `FORESIGHT_LLM_KEYCHAIN=0` 并移除环境凭据；新证据目录不得覆盖旧目录：

```sh
FWP_TEST_RECEIPT_DIR=<新证据根> bash scripts/run_main_gate.sh \
  --pytest-args '-q -p no:cacheprovider --basetemp=<新测试临时目录>'
"$FWP_WORKBENCH_PYTHON" scripts/check_test_receipt.py <本轮收据> \
  --require-full-scope --expect-revision c18d6f0fe73f1ee0c9d631ad7b302ef24727a4e6
"$FWP_WORKBENCH_PYTHON" scripts/review_probes/run_extraction_mutations.py \
  --revision c18d6f0fe73f1ee0c9d631ad7b302ef24727a4e6 --output <新变异目录> \
  --definitions scripts/review_probes/output_provenance_mutations.json \
  --tests intelligence/tests/test_output_provenance.py intelligence/tests/test_fulfillment_repair_round.py
```

P1a复验的逐次 pytest 命令保存在 `p1a-mutations-current/results.json.runs`，定义为 `scripts/review_probes/harness_plan_ownership_mutations.json`；基线所选测试文件与历史P1a套件不同，不得用295/321的计数差推导覆盖退化。
