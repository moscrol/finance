# 追问输出身份窄修复：结构回归通过，正文校验仍阻塞

## 裁决与身份

- 作者自验，不是独立复核；**产品验收 BLOCKED，未授权发布**。
- 独占树 `/Users/a77/fwp-wt-owner-output-contract-1002`，分支 `fix/owner-output-contract-1002`。
- 基座 `2aea7c27ed469530bc73fb232e65830acc754647`；代码/测试冻结提交 **`4cba44a63950a5671e4be8d2d40f71e5ef3c2e50`**。
- 后续报告/交接提交不移签代码提交的收据；最终身份与原件清单见仓外 `closeout.json`。
- 证据根：`~/.finance-runtime/reviews/owner-output-contract-20261002T100000Z/`。`evidence-manifest.json` 固定753份原件，SHA256 `7bf77365cf0cae67c52150fdc3c506a287ec5049e87427c201d7bfa4d27eee10`；文档提交/closeout为后续收尾文件，不倒填进该清单。
- 本线新增真实模型请求 **0**；未推送、合并、部署、切 8792、改生产库或读取/修改原 Keychain。

此次修正“已有直接判断槽位却额外要求旧 direct_answer”的输出身份冲突，**没有解决答案内容真正覆盖追问的全部问题**。相关 Python 套件真实结果为 **632P / 1F**，不是全绿。失败用例正常收集执行，没有 skip/xfail。

## 实现范围

`intelligence/services/task_frame.py` 的 `_clean_outputs` 保持原去空、去重、保序行为，仅在同一集合已有 `direct_assessment` 时，去除旧 `direct_answer`。首次编译与继承重算都在 frame 哈希和最终投影之前归一。

纯身份别名由 `DIRECT_OUTPUT_ALIASES` 单处定义，`conversation_orchestrator.py::_LEGACY_OUTPUT_ALIASES` 复用这一项；runtime 其余较宽的执行槽位映射不反向灌入 TaskFrame。

保护边界：

- 目标不存在时保留旧要求，不创造 `direct_assessment` 或内容。
- 保留 `evidence_boundary`、反证、定义、失效条件、验证要求等独立输出。
- `TaskFrame.from_dict` 不静默改写历史输出集合或哈希；只归一新编译/重算的 frame。
- 显式本轮要求仍优先；转公司、转财报、主体/owner 继承仍按原路径执行。
- 与基座相比，`query_understanding.py`、`turn_controller.py`、`research_contract.py`、`research_owner.py`、`task_fulfillment.py` **零差异**。没有新增公司/问法特判，没有改工具授权、预算、分类或终稿判据。
- 中间 `build_turn_intent` 可先产生含重复 ID 的继承意图；随后 rebase 及 attach 才形成最终合同。不能把中间值误报为最终持久化不一致。

## 验证与环境

| 检查 | 实际结果 | 原件及范围 |
|---|---|---|
| 修改产品前，初版新增测试 | 10P / 10F；基座 + 未提交测试 | `identity-red.*`；20例的早期版本，不与最终25例混算 |
| 初次修改后相关测试 | 443P / 1X | `identity-green-initial.*`；dirty，中间版本曾临时 strict xfail，后来已删除，不作当前绿收据 |
| 扩展新增文件 | 24P / 1F | `identity-expanded.*`；dirty，独立语义反例正常失败 |
| 固定 4cba，锁环境相关 Python | **632P / 1F / 0E / 0S / 0X，13.28s** | `related-committed.*`；13文件、collected=633，无选择器过滤；不是全仓测试 |
| 收据适用性 | exit0，明确保留1F | `related-receipt-check.log`；revision/解释器/指纹/clean匹配，不等于测试通过 |
| 五项身份变异 | **5/5 捕获**，逐项还原通过 | `mutations/`；身份子集24例；语义红例未参与变异定位，但保留在正常套件 |
| 原基座复验独立语义红例 | **1F / 0E / 0S** | `baseline-semantic-red/`；只复制已提交测试文件，产品未改；不可称整树clean |
| 四次离线 HTTP/ASGI 回放 | 三问锁环境 + 自然问法共享环境，最终合同complete | `committed-{exact,natural,short,shared-natural}/`；应用收到实际原判决，不返回诊断旁路 |
| 前端 lint/typecheck/test/build | 全 exit0；单测 **125P** | `frontend/frontend-{0,1,2,3}.log.txt` |
| Playwright 本地真浏览器 | **40P / 2S**，42收集 | `frontend/frontend-4.log.txt`；桌面/平板/手机，原句3次与新增两问6次均通过；2S为既有研究绑定的平板/手机跳过 |
| Ruff、diff | 全仓 Ruff 与 diff check 通过 | `ruff-committed.log`；代码提交hooks也通过 |
| 原件连接复核 | 输出集合/哈希/保存正文及日志哈希匹配 | `artifact-audit.json`、`artifact-audit.log`，仍输出 BLOCKED |

Python：

- 锁环境 `/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `66726d345bf37ce5`，httpx 0.28.1；用于固定提交相关633例、旧基座红例和主要回放。已有锁环境只读使用，未升级共享环境。
- 变异使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；共享环境指纹 `e1c50cb821a30f00`、httpx 0.25.2 偏离 lock。变异结论限这些无真实 HTTP 的身份测试，不冒充锁环境全量门禁。
- 锁环境 doctor ready、drift={}，但该份 doctor 是早期dirty快照，不是新候选测试收据。代码地图 empty，不据此认证完整架构。

前端：Node 22.23.3、pnpm 10.12.1。复用发布树的依赖，`/bin/cp -cR` 克隆到本树独立 `node_modules`；**未执行 pnpm frozen install**。调用既有 `run_frontend_gate.run_gate` 的五命令组合；`complete=true` 只对所列五步成立，不冒充默认六步流程。收据首尾同 SHA、clean；环境/lock指纹另见 `frontend-environment.json`。

服务仅使用独立端口19071/19074、fixture、用户态与 Episode 根。禁 provider/Keychain，Python 网络 guard 只允许loopback；无外网拒绝记录。此 guard 不是 OS/浏览器级网络沙箱。外层既有进程组超时量具记录退出0、进程组已消失；收尾两端口无监听，fixture产物冻结在 `frontend-test-results/`，含测试现造数据库，未使用/改写生产库。

## 三问回放与合同链

沿用旧 PR16 分支已提交量具 `scripts/review_probes/probe_owner_followup_contract.py`，SHA256 `178d49193c636159662fba501a2658f94c8ffccf418bfbdb27d71364cefb52b4`，明确 `--repo-root` 指新树。量具没有复制进产品分支。

首轮均为“请个股深挖英维克的液冷业务”，manual `stock-deep-dive`：

| 追问 | 初始题型（未修分类） | 最终要求 | 实际判决 / 公开正文SHA前缀 |
|---|---|---|---|
| 那它的主要风险和下一步验证是什么？ | concept_definition | direct_assessment, supporting_evidence, counterpoint, direct_definition, evidence_boundary | complete / `7ae8358f`（原基座该问已通过） |
| 那它有哪些主要风险，下一步该怎么验证？ | general_finance_qa | direct_assessment, supporting_evidence, counterpoint, evidence_boundary | complete / `2ba20050` |
| 那它的风险呢？接下来怎么验证？ | general_finance_qa | 同上一行 | complete / `2ba20050` |

两种同义问法原基座都因重复旧 ID 返回缺口稿 `32ce5600…`；此次恢复专项正文。自然问法在共享/锁环境的源码与正文SHA一致，不能把效果归因于httpx漂移。

`audit_evidence.py` 将真实持久化 `messages.jsonl` 的最后一条同ID记录、run `report.json`、owner投影、实际verdict及`answer.md`逐项对齐：最终 required_outputs 和 task_frame_hash 一致，主体为英维克，owner为stock-deep-dive，继承的turn指向首轮assistant。API消息DTO未暴露turn_intent，`result.json`中的null不是“未持久化”的证据。

浏览器与回放证明“原误拒已解除、正文/栏目可见”，**不等于主要风险及验证内容质量通过**。完整正文仍含重复公司/财务/反证小节、模板式验证建议；同一 `ONTOLOGY` 范围摘要仍可满足 direct_assessment 与 supporting_evidence。其证据角色不是公司风险事实。此处是作者检查，不是独立全文评分，更不是自然模型收益或泛化结论。

## 独立阻塞：正文词元重合并不证明直接回答出现

正常红测试：

`intelligence/tests/test_owner_output_identity.py::test_boundary_only_prose_must_not_stand_in_for_the_direct_answer`

- 注册直接判断：`测试公司的交付风险取决于客户验收进度。`，有G1来源。
- 公开正文仅：`证据边界：尚未取得客户验收结果，不能确认交付兑现。`
- `_claim_text_present` 在完整claim未出现时，两个token重合仍可判为出现。
- 实际direct_assessment为fulfilled；`answer_spans`写回未显示的claim全文。它不是实际正文坐标/片段证明。
- 空正文、缺claim、缺来源、缺boundary负例能抓住，不说明boundary-only重合负例也能抓住。
- 在2aea独占detached树复制同一测试后复现同一1F；`task_fulfillment.py`与4cba逐字一致，SHA256 `a1bbe80f225fe82e28e18a0776c5af46e9880e9f41a04f8f3f28ae97f9a2eafd`。测试复制文件已删除，树还原干净后移除。**旧缺陷不是本次引入，也不是可豁免的理由**。

后续应单独设计公开正文的真实见证与claim绑定，覆盖主体/否定/条件/指标身份，同时允许正确改写。简单提高词元阈值、加问法词表、要求整句逐字复制、删除/xfail此测试，都不能作为本轮交付变绿的方法。本轮终稿校验未改；候选保持红，禁止带红合入。

## 变异明细

使用仓内既有 `run_extraction_mutations.py` 与已提交 `owner_output_identity_mutations.json`，没有新增评测框架：

| 故意撤除/破坏 | 执行 / 红数 |
|---|---|
| 保留重复 direct_answer | 4 / 4 |
| 无目标也删除 direct_answer | 3 / 3 |
| 把独立 evidence_boundary 合并到 counterpoint | 4 / 4 |
| 继承重算绕过归一 | 7 / 5 |
| owner以自己的要求覆盖frame | 1 / 1 |

每项均真实断言失败，0 collection error、0 skip；每项源码字节/哈希还原后对应目标绿，最后所选身份集合24P。runner的`restored-full`名称指**传入的24例集合**，不是新增文件25例、更不是全仓绿。临时变异树已经移除。

## 后续与协作

1. 独立 reviewer 审 `2aea → 4cba` 的窄修复和本报告；作者自验不能冒称原发布候选的独立验收。
2. 为正文覆盖反例另立受控修复，保留正常红测试与正反例；可与此分支堆叠，但需新SHA重跑组合测试。
3. 真红解除后，在最终组合revision执行完整Python/前端默认流程、registry及新远端CI，再做独立全文验收。当前没有全仓Python、新远端CI或模型质量验收。
4. 发布owner树仍2aea，本分支没有替它更新发布候选。旧PR16比较器补丁栈不整枝搬来。
5. R17四格已结案，不重跑。规划预算R18由另一owner在 `fix/planning-budget-handoff-1002` 处理；读到其 `db2671b06` 交接的1505P/7变异属于owner自述，本线未重新签字、不移用为本修复证据。

取舍、发现顺序及工具盘点见 [日期快照](../handoffs/2026-10-02-owner-output-identity.md)；接续入口见 [在途交接](../handoffs/inflight/fix-owner-output-contract-1002.md)。
