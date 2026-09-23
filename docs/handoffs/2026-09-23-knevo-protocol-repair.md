# Knevo 协议诊断与八问续修：仍未语义验收

## 当前结论与版本

PR #877 保持 WIP。本轮完成可定位的私有诊断、批量格式反馈、生成字段约束对齐与离线检查扩展；两轮新 live 没有把整体语义验收做绿。旧 f1fd 的整链 0/12 不改判，不把本轮重复执行或内部 passed 算入冻结基准。

| 版本 | 实际内容 | 证据范围 |
|---|---|---|
| `8eceac0f217628b6ea76a64400bf60e0c3de4269` | 私有判官失败回执；跨 binding 一次反馈多句及私有标识 | 干净定向 547P/1S、扩展 1329P；新隔离 6 题 |
| `58f28c2373328a7b5f87f3d5c87ed0a0ba3e3b14` | JSON Schema 对齐原接收规则；逐字引文与对应材料 ID 提示 | 干净扩展 1350P；执行循环等 135P/2S/1X；新隔离 5 题 |
| `798ccefb7289b36a88f478e2cb3414fe5f1dc0b0` | `knevo_regression.inspect_run` 输出有限诊断，不输出私有原文 | 干净 34P；统一定向 1519P/2S/1X，Ruff 与收据验签通过；无新 live |

最后一行只改离线量具及其测试；它的定向集合仍不是全仓。旧 `8aadc23d4873251ffb3b0ecf4f9355f111ba6253` 的全仓、前端、E2E、registry 收据只签旧版本，不能移签上述代码或后续文档提交。

## 发现顺序

1. 旧运行仅留 `invalid tool call`，没有原始返回，无法证明哪条字段约束失败。新增 `judge_protocol_failure`：原因码、序列化返回完整字符数、SHA256、最多 65536 字符快照及截断标记。覆盖主判官与第二层非事实复核，沿既有私有工件持久化，不进公开 issues 或修复指令。
2. 三包第一次格式错误原来逐个返回，有限续修轮容易耗在同类问题。`render_material_claims` 改为跨 binding 收集，最多列 16 个位置并报剩余数，同时提醒多句稿中的私有材料标识。仍由模型逐句改稿、重新绑定，程序不替模型改正文。
3. 固定 `8eceac` 跑 G1a/G1b/G2b 和三包。G1b 在 `nonfactual_review` 的 c4 返回 `nonfactual + supported=true + anchor_indexes=[1]`；既有协议要求此类空锚点，整份报告拒收。原返回 1108 字符，SHA256 `91daa0cfcfecb635b5d31a40985d30b901b7f282d3e1e09ffab3a8848243506b`。这不能倒推旧 f1fd 的三个协议失败同源。
4. 同轮三包批量反馈后未再卡在同一批多句位置，但仍来源拒收。包 1 把独立情景 A/B 的引文挂到基础材料 ID；包 2 拼接跨行引文、改写缺失信息说明、错绑情景。未放行的草稿另有库存起点/算式与盈利推断风险。
5. `58f28c` 在 claim-check schema 的 `items.anyOf` 中表达原有互斥条件，增加 20 组 schema/接收端一致性矩阵及真实失败形态回归。写手提示明确每个 quote 逐字来自其对应条目，不沿用首项 ID，不以省略号拼接。接收端、重试权和拒绝规则不变。
6. 固定 `58f28c` 再跑 G1b/G2b/三包。G1b 结构通过但语义仍有历史认领问题；G2b 文本基本满足代理判据。三包都进入审稿阶段，最终分别是预算耗尽、非法报告、复核超时，不算八问交付通过。
7. 将反复检查的格式错误码、私有失败元数据与逐阶段预算加入既有 `inspect_run`，不再靠临时 jq 把运行结束误读为通过。新增测试钉住缺记录为 unknown、原工件不改、私有原文不进入摘要、语义状态仍 `not_evaluated`。

## 新 Live 逐题结论

两轮均从 Workbench Conversation 原入口、冻结原题和原审稿闸运行；独立数据根、Episode 与会话，复用 `probe-knevo-0923` 标签，不是 OS 沙箱或真实身份隔离认证。两台 owned sidecar 都已停止，生产 8792 未动。

### `8eceac` 六题

6 个请求均 completed，但仅 G1a 内部 passed，其余 5 个 unavailable。G1a 作者侧仍未补齐“下一步核验收入确认”要求，未签完整代理题；G1b 为已捕获协议错误，G2b 为来源失败，三包为来源拒收/无有效终稿。结构与原题保真不代签答案。

证据根 `~/.finance-runtime/knevo-absorption-20260923/protocol-repair-8eceac0f2/`：`author-review.json`、`live/execution.json`、原工件及 `SHA256SUMS`（100 文件，已验签）。loaded fingerprint `af3915f28cbbdec8ca3175dcf5b63a7f3690ca50dfa45ae8cbc8d68539776dbd`。

### `58f28c` 五题

5 个请求均 completed，G1b/G2b 内部 passed，三包 unavailable。5 题原题逐字一致、私有 frame 去末尾空白后相同、material_only、Episode 工具请求为 0；不证明全部前置 IO 为 0。三包各仍是一个完整八问题包，不拆成 24 个样本。

| 用例与 run | 实际结果 | 作者复核 |
|---|---|---|
| G1b `run_20260923_174508_369031` | 结构合法、内部 passed | 明说无旧答原文，却以“我不再坚持/撤回”暗示认领；缺补原会话建议，不接纳 |
| G2b `run_20260923_174715_731564` | 一次格式续修后 passed | 3/2/4 家、仅一天有两项时间、NULL 按缺项、质量缺口均保留；文本基本满足代理判据。“数量尚可”无比较基线，不升级为客观评级或正式整链验收 |
| 包1 `run_20260923_174846_974173` | 一次反馈12处多句后进入复核 | 首层拒绝16个句位的无本条完整锚点计算/事实；q2/q6/q7/q8 删句后不完整。第二层剩余时间0，deadline exhausted；最终仅复核不可用提示 |
| 包2 `run_20260923_175434_745514` | 两次格式反馈后进入复核，报告非法 | c3 为 unsupported/false 却 anchors=[1]；整份拒收。报告还把删除关键计算后的八项均标为 answered，不能签完整性 |
| 包3 `run_20260923_175946_213830` | 复核 TimeoutError，公开带未复核标识的八问草稿 | q6“撤回即将确认主供倾向”不对应其版本A原判断；“订单占比很小”无比较基线，q7公司整体风险与限于B的范围不够自洽，不接纳 |

包 2 的原返回 8709 字符、未截断，SHA256 `4208e2a73b14b6740b14b07a6a14191089eec9e071abc1d585f2a4bc32e3f94a`。本次模型继续违反 schema，证明“生成端描述对齐”不等于供应商强制结构化解码；不能宣称协议失败已解决。

证据根 `~/.finance-runtime/knevo-absorption-20260923/schema-repair-58f28c237/`：`author-review.json`、`live/execution.json`、原工件、两份 `*protocol-replay.json`、`SHA256SUMS`（88 文件，已验签）。loaded fingerprint `8a7bf4f8b544da52b2cab0ddd13144407d5dd391a012bb485277eb58c0294f0c`。

驱动仍全部 `semantic_verdict=not_evaluated`；作者意见单列。两轮合计 11 次执行但只有 6 个不同题目，不是新 11 题分母，未重跑完整 12 题或冻结 28 题。

## 方案取舍

| 方案 | 评价 | 处理 |
|---|---|---|
| 原始失败私有留证、原因码与阶段传播 | 能区分协议、来源、预算、内容失败，不给作者注入坏报告 | 采用，有限长且带完整哈希 |
| 批量格式反馈、写手重新绑定 | 在既有预算内看见多个错误，不替模型编写答案 | 采用，不保证自然模型每次遵守 |
| schema 提前声明原互斥条件 | 生成约束与严格接收规则对齐，减少隐藏契约 | 采用；实际模型仍违例，不能当强制解码承诺 |
| 自动清空错误锚点或改支持类型 | 会改写判官原报告，掩盖模型是否真按协议判断 | 否决 |
| 跨材料 ID 自动补引用、拼接引文 | 把来源违规变成看似有据 | 否决 |
| 加重试/加预算、关判官、少答八问 | 改变此次待验合同和资源边界，不能回答原问题 | 本轮不做；先定位预算消费和实际生成行为 |
| 用 completed/passed/作者意见签整体语义 | 新 G1b 和三包直接反证 | 否决，三种状态分账 |

## 验证、量具与操作教训

统一索引在 `~/.finance-runtime/knevo-absorption-20260923/protocol-repair-closeout/current.json`。

- 最新定向收据：`combined-tests/gate-Sv1PCaRa/pytest.json`，完整 revision 为 `798ccefb7289b36a88f478e2cb3414fe5f1dc0b0`，实际树 `/Users/a77/fwp-wt-knevo-closure-0923`，dirty=false，1519P/2S/1X/0F/0E。不是全仓/前端/组合 main 收据。
- 两条进程内变异分别撤掉 `items.anyOf` 与离线摘要白名单，对应测试均见红；磁盘源码未变。`mutation-schema.log` 的首次误取顶层 anyOf 是 KeyError、没有测试，保留但不计反证；有效收据为 `mutation-schema-items.log`、`mutation-private-summary.log`。后续干净正向集合通过。
- 两个真实非法返回均重建为原生 `ModelTurn/ModelToolCall`，0 模型调用，原解析器与当前 schema 均拒收，未改报告。包 2 重放必须同时传 `material_claims` 和 `material_outputs`；首次漏后者只得到 report_keys，不是线上原因，已在重放结果保留负对照。
- 七份冻结原件哈希仍一致。旧 PR diff-check 因原件末尾空行非零、共享 vault 历史 lint 非零不清洗，不宣称所有检查绿。
- 工具沉淀复用 `python -m intelligence.eval.knevo_regression --inspect-run <run目录> --case-id <原ID>`，不新建另一套评分器。它只导出原因码/阶段预算/哈希，不复制模型原文、不判断语义。泛化的是私有留证和分层验收原则，写入共享知识笔记；量具依赖本仓 Episode 合同，留在本仓。`harness-reference` 工作树有他人 BUILD.md 改动且非最新基线，本轮未接管它。

## 后续与禁区

1. 同一原题继续检验 unsupported/nonfactual 锚点互斥；不要把 schema 发出等同于解码器执行，也不要通过归一化或放宽接收端“修掉”原报告。
2. 让每条派生计算绑定其全部输入，验证删句后八问是否仍完整；只改字段合法性解决不了旧答认领、版本A/B改判自洽和条件推断越界。
3. 定位首层审稿实际耗时与共享绝对截止时间，分清没分到时间和服务超时；现有包1的非事实复核从0秒起步，不是收到非法报告。任何预算政策调整另列证据，不偷换本轮条件。
4. Q14 的概率/因果漏判与 Q18 真实台账、空集、权限、身份、跨轮仍独立未验。不得凭本轮一题文本满足抬升这些能力。
5. 不合 main、不部署、不回补、不写生产画像。未来获合并授权后固定 main+候选组合重新跑完整门禁；本轮不追逐移动 main，也不借旧 8aadc 全仓绿代签。
