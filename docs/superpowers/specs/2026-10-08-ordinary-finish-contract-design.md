# 普通 Episode 的真实成稿合同

本轮补全已获授权的结果文字所有权消费接口；用户持续要求根因优化、上线后真实验收。原PR80/唯一首答均保留。设计比较原件在本轮外部 `finish-contract-design/`，没有把设计或schema能力签成已实现。

## 已证问题与有限目标

bd66首答的26 refs确实在seq12及四个后续原生前缀交付；seq24/29/37均只提交旧draft。真正system一直教material格式缺席就旧draft JSON，普通新格式只有tool提示。producer和projection正确，实际作者合同仍有两处知识来源；非采用的因果尚未证明。整篇NOT_PASSED中的历史、集合去重、指数贡献和反证错误不因格式统一自动获证。

目标：格式选择、closed schema、wire template、模型说明和作者编译由同一纯计算module持有。新普通会话首个system就使用该合同；修订、诊断和finalizer不再发第二套draft-only终局。

## 方案与选择

| 方案 | 选择理由 |
|---|---|
| 两入口纯module，parts默认、legacy兼容 | 采用；收拢真实已有三种作者形状，少interface，数据owner仍各归其主 |
| 会话句柄协商多个偏好 | 不采用；新增柄与偏好状态不是当前问题必需 |
| prepare绑定完整模型请求 | 借用“所有真实caller复用同合同”的原则，不包住完整研究请求或增加格式账本 |
| 只加提醒/有refs强制至少选一个 | 不采用；前者继续多处终局知识，后者给无关事实新增使用义务且不保证free正确 |

## Interface与所有者

新增services内 `finish_authoring.py`，两个纯入口：`finish_author_contract(context)` 生成不可变作者合同（closed json_schema与model_payload），`compile_finish_authoring(envelope, context=...)` 生成唯一正文、既有claim origins及可选owned receipt。返回的编译产物不是FinishAdmission，不授权限、证据floor或completed。原完整准入和harness binding仍在程序编译后运行，错误分类/优先级保留。

普通真实model_payload使用 `ordinary_answer_parts_v1`：reply仍只有已有status/draft/answer_parts/gaps/bindings及兼容字段，不让作者另填format/value/truth/receipt。默认draft空、parts为自由字符串或封闭result_ref对象；不预填虚构ref、市场真值、章节或预算。没有目录可纯自由块，refs选择数量与顺序由作者决定。legacy draft/None及claims-rendering仍合法兼容；不同时启用两正文生成者。

材料复用现有claim_finish_format/material schema/compiler，来源与历史材料边界、错误、prior evidence例外不移交给普通格式。D4事实重算与source/ref/current permission仍由owned_results负责；无反向import、runtime不得成为services依赖。现有finish_json_schema无context调用作为兼容adapter，不静默升级为新grant。

## 真实输入、恢复与兼容

新live ordinary初始system的终局与正文规则有意改变，使用统一finish_format描述，不再以材料格式缺席教唯一旧draft。长度/Markdown/数字绑定都描述最终正文，不额外限制章节或增加字段族。声明格式不表示已有合法refs。

实际prompt_assembled、model_input、derive_messages/provider转换、修订开场、invalid/unsupported回灌、finalizer必须消费同owner；不能只schema helper绿、mock预硬编码ref或在工具多塞一句话。

旧持久化system/events、档案前缀、原88/118冻结件逐字节不变。未终态旧Episode沿已落盘旧合同继续，不给旧context默认现代格式；必要版本身份仅用既有原生prompt/input payload记录，不另建账本或system-override事件。旧draft/None准入、序列化、public字节和材料消息保持；**不声称新普通system也逐字节旧值**。

恢复先过现有exact授权与entry identity，从合法native source重建，不补EvidenceLedger/floor。新格式本身不重授权限；编译refs始终用当前context，缺ACK、撤能力、收窄cutoff、换owner/删源/源冲突按原规则拒绝。carry只携带被采用稿匹配的receipt，不能把新格式描述当新稿或套旧证据。

## 必须通过的验收与边界

1. 实际harness/registry/ContinuousAgentEpisode/本地JsonlEpisodeStore；模型替身仅从实际messages读取格式与refs，不硬编码评审真值。初始普通system、工具后、repair与finalizer模板一致，生成parts通过原准入/native receipt/semantic/public；derive_messages精确等于捕获请求。
2. 目录空、refs部分/零选择、legacyNone、双正文、未知/坏ref、自造receipt、材料混用正负控；claims来源角色、全部原binding/floor/date规则未弱化。
3. 新旧未终态恢复各自合同、证据checkpoint旧而tool已durable、有效修订、invalid/deadline carry、finalizer；旧事件前缀不变，当前权限收窄不能借兼容格式通过。
4. 新system contractdiff与旧payload/public/material不变矩阵；撤真实开场/修订/finalizer接线分别失效的负控。适用session_projection出口政策与邻域真实caller核验，不堆只镜像模板helper的测试。
5. fixed clean新head独立Spec→Standards，按实际范围收据；准确head/main各完整Python/前端/registry/CI，正常合入后新快照/8792 health/ledger/备份。只有该新部署后另注册单次原题，不重抽bd66。

本案不新judge/模型/预算/权限/工具/SQL，不扩大programme predicate families、不改ask_synthesis或Pi的history生产树。新格式送达、实际采用、片段保真和全文质量分别验；不能承诺四类free错误已解决，也不把更多上下文或更少calls当总体胜Pi/长期收益。
