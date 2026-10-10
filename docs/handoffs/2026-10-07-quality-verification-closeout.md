# 2026-10-07 上线与内容核验收尾

> 2026-10-11 收口注：下述生产状态与未修缺口属于 10-07 历史时点；缺值零化、修订丢弃与反方标签截断已由 [PR #74](https://github.com/moscrol/finance/pull/74)（`82de3fb730a4175170b4e6ba472e130e5ef87ab7`）承接。后续代码修复不改签本页首次答卷的 `NOT_PASSED`，当前发布与保留事项见 [合集记录](2026-10-11-release-wave2-integration.md)。

用户希望先优化上线，再以 8792 与 Pi 的同题原件检验知识、数据、工具消费，以及时间长河、个人记忆的实际价值；回答应更全面、有有效视角和反证，同时减少重复干预。本快照只收口已经发生的部署与只读诊断，不将工程绿转换为金融内容绿，不补抽更好的答卷。简版见[树外总报告](/Users/a77/.finance-runtime/knevo-coverage-release-1007/final-quality-report.md)。原始资料均留在 `/Users/a77/.finance-runtime/knevo-coverage-release-1007`，本分支只提交两份交接 Markdown，不复制用户台账、模型原始请求或大数据进 Git。

## 发现与处置顺序

1. [PR68](https://github.com/moscrol/finance/pull/68) 合入 `c8b87ee5bd222b35adc12ee1b76b16b9bc3bddef` 并部署：市场总览、主线、风险成为内部可选维度；目标来自原问题，跨轮当前明确要求优先于继承与默认，Frame 与 intent 保持一致。
2. 01 长电原题在作者菜单之前被休市短答截住，公司研究没有完成。保留 STOP 原件；[PR69](https://github.com/moscrol/finance/pull/69) 合入 `582b9d55cd1f6e6f69469eb996f144203b3c7d20`，按现有证据政策限制日历的终结权，保留日期披露，非行情公司/题材问题继续原负责人，未知政策交负责人处理。legacy general 的碰撞残余未宣称全部解决。[首次消费审计](/Users/a77/.finance-runtime/knevo-coverage-release-1007/consumption-results.md)、[发布状态](/Users/a77/.finance-runtime/knevo-coverage-release-1007/calendar-release-state.json)。
3. 实际 trace 的普通人类进度文字被准入检查误当 JSON。修复区分进度文字与模型身份载荷，Unicode 空白和 BOM 后的身份 JSON 继续严格检查；[PR70](https://github.com/moscrol/finance/pull/70) 合入 `6b8269bcdcb293cf2ccf0879430531ab1a62be8a`。当前 8792 已切该版，加载指纹等于仓库指纹、源码干净、13 项就绪全部 true、部署台账与 health 一致。它在 Pi05 完成后部署，没有把新审计代码冒充旧测量作者。[准入与发布状态](/Users/a77/.finance-runtime/knevo-coverage-release-1007/auditor-progress-state.json)、[部署核对](/Users/a77/.finance-runtime/knevo-coverage-release-1007/deploy-6b8269bcdcb2-check-verified.txt)。
4. 02 准备漏生产数据环境，未调用模型；03 长电作者完成但全 run 两次模型身份未报告，Pi 0 请求；04 的 P 有效、Pi 四次 HTTP400 无答。这些批次已封存，不能充作配对或择优重跑。05 复用 04 原 P `run_20261007_190131_407451`，P 新请求 0；Pi 首次有效新答卷 4 次真实请求，均报告 `glm-5.3-flash`，8 次工具调用，COMPLETE/退出 0，桥已停。源码、冻结数据库、题面及工具包哈希经独立核对；唯一有效配对为市场首问。[05 执行收据](/Users/a77/.finance-runtime/knevo-coverage-release-1007/post-deploy-pi-only-05/execution-receipt.json)、[执行上下文审查](/Users/a77/.finance-runtime/knevo-coverage-release-1007/reviews/pi05-first-pair-execution-context.md)。
5. 05 内容结论为 `BOTH_NOT_PASSED`，本题相对偏好 Pi。Pi 排序后读到新能源车 12 家并披露题材重叠；P 将无排序的 50 组切片当全集，误称 AI 7 家最高。Pi 也传播缺值零化、历史日期漂移及无资金/换手证据的推断。真实全文与资格限定已送达，错误不能全归截断或公开稿控制。[独立比较](/Users/a77/.finance-runtime/knevo-coverage-release-1007/reviews/pi05-first-pair-content-comparison.md)、[04 P 原件诊断](/Users/a77/.finance-runtime/knevo-coverage-release-1007/reviews/pairs04-market-content-and-consumption.md)。
6. 03 长电证明知识消费发生：10 次工具、77 张去重卡实际送达；预算/拟投被升级成兑现，旧 PE 被用作当前估值。另核定观察文本 6,179→4,000 字确丢 E76/E77 反方标签，详情仍在；关键预算、五月日期和来源缺口未丢，不能强归截断。记忆实验仅核近期纠偏的首作者阶段，不认证完整问答或长期收益。[长电诊断](/Users/a77/.finance-runtime/knevo-coverage-release-1007/reviews/pairs03-stock-content-and-consumption.md)、[记忆首稿](/Users/a77/.finance-runtime/knevo-coverage-release-1007/reviews/memory-first-author-c8-live-02-spec.md)。

## 决策与被否方案

| 决策 | 方案 | 评价 | 结果 |
| --- | --- | --- | --- |
| 回答目标 | 原问题定目标，默认维度可选 | 当前问题和跨轮缩小范围可保真 | PR68 已上线 |
| 回答目标 | 强制默认章节和维度 | 会将内部研究框架转换成用户义务 | 未采用 |
| 日历权限 | 按已有证据政策决定能否提前终结 | 可保留真实日期披露并继续公司研究 | PR69 已上线 |
| 日历权限 | 加词面豁免或沿用所有休市短答 | 首次原件已证明会越过公司研究负责人；词面补丁不能解决权限边界 | 未采用，不签 general 残余全解 |
| 身份检查 | 普通进度文字与身份 JSON 分开识别 | 修误拒收，同时保留缺身份、错误 JSON 的严格边界 | PR70 已上线 |
| 身份检查 | 忽略解析异常或补造模型身份 | 会把观测缺失转成错误准入 | 未采用 |
| 有效配对 | 保留全部 STOP 与原 P，只补首次有效 Pi | 保住首尝试来源和有限预算，不因先前 Pi 无答判输 | 05 唯一一题有效 |
| 有效配对 | 重跑 P 选较好稿、将 03/04 凑成多题 | 身份/答卷不闭合，且改变比较对象 | 未采用 |
| 质量判断 | 分开查授权、返回、模型可见、最终使用与收益 | 可以定位资料丰富但使用错误的首次位置 | 已完成有界诊断 |
| 质量判断 | 用 completed、证据卡数或 13 项就绪代签内容 | 与两份真实未通过答卷冲突 | 未采用 |
| 记忆首稿 | 保留证据资格底线，观察现有循环回灌边界 | E6 是召回缺口，不是用户先验；源码允许继续不等于实际成功 | 首稿拒收；完整循环未跑 |
| 记忆首稿 | 放松底线以让首稿通过 | 会改变来源身份，无法证明长期价值 | 未采用 |

## 验证收据与适用范围

本切片没有新增模型请求、金融 API 请求、产品变更、部署或用户状态写入。只读原件、核验收据与本机文档检查；GitHub 查询和文档 PR 使用 `gh`，联网前按仓外 web-access 流程检查，不启动浏览器。

| 对象 | 已核证据 | 不能据此断言 |
| --- | --- | --- |
| 当前生产 `6b8269bcdcb2` | [health](/Users/a77/.finance-runtime/knevo-coverage-release-1007/switch-6b8269bcdcb2/health-after.json)、[readiness](/Users/a77/.finance-runtime/knevo-coverage-release-1007/switch-6b8269bcdcb2/readiness-after.json)；锁定解释器前缀为 `workbench-locked-20261007`，HTTPX 0.28.1 | 金融全文质量通过或 general 碰撞全部修好 |
| PR70 head 与 merged main | 各自全仓 20,753P/76S/2X、收集 20,831、无收窄、无失败/错误；主干[原收据](/Users/a77/.finance-runtime/knevo-coverage-release-1007/auditor-main-gate-6b8269bcd/gate-ZAa2LGuX/pytest.json)、[前端六项](/Users/a77/.finance-runtime/knevo-coverage-release-1007/auditor-main-frontend-6b8269bcd/frontend.json)。本切片分别在相应 revision 重核 `--require-full-scope` 通过 | head 收据转签 main，或旧测量作者已经是 6b 版 |
| 05 市场配对 | 作者 `582b9d55cd1f`、检查器 `663bf04f1fe2`，P 原件复用；Pi 93 卡送达、4 次请求/响应配对、执行和身份闭合 | 五题完成、一般胜率/速度/成本优势、单个删减的因果收益 |
| 05 用量 | P durable 与根账同六次作者调用，267,647 输入/4,624 输出；Pi 153,230 输入内含 103,104 缓存，1,987 输出内含 71 推理 | 六次加六次；四次旧导出代替完整成本；缓存和推理重复加总；SDK 零金额等于免费 |
| 知识根 | [实际绑定](/Users/a77/.finance-runtime/knevo-coverage-release-1007/actual-rag-bindings.md)为 managed v4 `readiness-20260927-43430ddd`，manifest `597487f23fb102894ad78627cbb8390e3a4ac977f552995602e9ecb329fe604e`；standard 168,920 块/14,439 文件，full 269,019/17,831；目标长电 51、先进封装 75 块，当前源与冻结源目标字节一致；13 页冲突隔离 | 目录名陈旧；存储芯片主概念页 0 块等于全主题没资料；本题未调用 RAG 却称已受益；完整索引逐字节首尾冻结 |
| 长河与记忆 | [长河准备与来源核对](/Users/a77/.finance-runtime/knevo-coverage-release-1007/consumption-plan.md)：六轨及专门入口存在，本轮通用研究未见直接投影；记忆台账状态覆盖后 217 条、读取窗 200、送达 5，省略 195 条仅指窗内，另有窗外 17 条；ON 首稿真实使用、E6 误绑被拒，默认循环[允许预算内回灌](/Users/a77/.finance-runtime/knevo-coverage-release-1007/reviews/memory-first-author-c8-live-02-continuation-boundary.md) | 同底层 facts 等于六轨消费；首稿实验等于自然路由/完整 QA；首次拒收等于整循环必败；长期金融收益 |

03 公司问答不能算配对：五个作者调用身份匹配，但整个 run 账八条含两条未报告身份。记忆 02 的两臂各一真实调用，仅开启开场消息不同，`classifier_fixture=true`；OFF 请求记忆工具未执行，ON 使用五条近期纠偏但原稿拒收，未跑后续。加上 01 记录器故障的一次实际请求，总计三次，不能称零成本或重新开批次择优。

两臂截止配置也未完全等价：P 是 10/07 默认信息上界、Frame 要求 9/30，Pi 为明确 9/30；本题实际目标来源截至 9/30，未发现具体未来行情消费，但不认证普遍时点权限等价。P 菜单 16 项、Pi 14 项，差出的子研究/派生计算本题未调用。RAG 开始绑定一致且结束后元数据复读一致，本批没有独立结束采样；不认证完整索引首尾冻结。

文档树从最新 `origin/main@6b8269bcdcb2` 创建；锁定 venv 软链可用，workspace doctor 无错误。代码地图为空，不依据它签全局架构或生产覆盖。首次在主干树核 head 收据因 revision 不同被拒采信，回精确 head 树校验通过；这不是测试失败，也不转签主干。

## 后续与收尾边界

已确认缺口在[质量台账](/Users/a77/.finance-runtime/knevo-coverage-release-1007/verified-quality-backlog.json)，负责人 `current_root`。本分支只交文档，不把诊断写成已修产品；建议 root 下一步沿三个结构接缝收敛：

| 接缝 | 已确认事实 | 待设计和验证 |
| --- | --- | --- |
| 数据来源 | 主线表 `NULL` 被 `or 0` 渲染成真实零；同日同代码热度表有非零值 | 保留缺值语义、交代来源差异，核作者不再把未知当零 |
| 修订到公开稿 | 33→37 句触发 backfill 放弃修订；修订改善引用但仍有中心错句 | 用事实、引用与目标符合度决定是否保留，不能把句数或旧稿保留签成修好 |
| 来源资格与模型上下文 | 预算/拟投、旧日期、集合范围仍在请求却被升级；反方立场标签另有截断损失 | 在现有卡片和投影中保存紧凑资格字段，核原件→可见文本→最终使用；区分作者误用与真实送达丢失 |

不要把下一步做成固定措辞、硬章节或不带失败原件的新闸门：本题已表明真实来源语义和作者资格判断比形式完成更早决定质量。保留首次红灯与失败身份；任何新采样须有新有限清单和授权，不补抽旧批次。时间长河和记忆收益尚缺完整研究路径证据，不能靠注册菜单或单次首稿代签。

工具沉淀盘点：本切片没有新增脚本或两次以上的同一手工排查；已有审计脚本与原件均树外保留。产品缺口已由 root 承接，本切片不越权补产品；没有把仍需语义判断、仅一题的观察升成通用工具。共享 agent-memory 和 harness-reference 不改，由 root 按最小权威字段回写。此文档 PR 只供复核，不合并、不部署。
