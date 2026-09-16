# 2026-09-15 · E2 P3 注入面收口核查——四组九类逐条对账

分支 `fix/e2-boundary-closeout`。P3h（`50687c0b`）之后对 D4「四组九类注入路径」做的收口核查，附判定依据与钉测试。**这是作者核查，不是独立 QC；「收口」指读取权限/事实注入面，不含答案质量（P4/P6）。**

## 对账矩阵（D4 §3.4 四组九类）

| 组 | 注入路径 | 状态 | 依据 |
|---|---|---|---|
| ①预取 | opening_prefetch | 收口（P3a） | material_only 短路、零播种；`test_original_t2_t3` 断言空证据计划 |
| ②前缀 | prime/知识前缀 | 收口（P3a 派生） | prime_quote/news/memory、prior_recall 全部能力门控（`_with_residual_prime`/`_with_prior_recall` 按 capabilities 挂槽），空授权不挂；钉测试断言 output_ids 无 prime_* |
| ②前缀 | 视角注入 | 收口（P3d） | material_only 时 perspective_context 空串 |
| ②前缀 | 系统级默认市场摘要 | 收口（P3a 派生） | 探针实测 material_only 装配 payload 的 `today=None`、`latest_data_date=None`（市场日期解析在装配前短路）；`market_summary` 只是输出槽描述模板，material_only 输出槽被题组替换 |
| ③历史 | 历史摘要 | 收口（P3f1） | material_only 时 legacy conversation_context 清空、typed 投影替代 |
| ③历史 | episode 压缩上下文 | 低风险豁免 | `_compact_history_for_model` 是对本 episode 已过滤工具观察的折叠（减法），缺省关；material_only episode 的工具观察本就受收窄注册表约束 |
| ③历史 | 恢复读 | 收口（P3c/P3g） | `restore_episode` 只结算+给计划不注入模型输入；重放判定看 replay 声明+当前 registry；controller 层澄清挂起恢复 P3g |
| ④研究 | 子研究上下文 | 收口（P3a 派生） | sub_research 是门控工具（需授权+runner），空授权不装配（tool-reachability 审计） |
| ④研究 | 非工具路径 provider 事实 | 收口（P3c/P3d） | 消费预取升档在收窄后判定；四生产者（旧答/stance/项目先验/视角）P3d 停读 |
| — | dispatch 兜底 | 既有（P3a） | 被禁工具请求拒绝+留痕 |
| — | 确定性旁路 | 收口（P3h） | adapter 不让路 + orchestrator 掉落总闸，两防线正交变异承重 |
| — | 歧义（非缺失）预取前澄清 | 收口（P3f2） | boundary_uncertain 走 clarify，clarify 轮不装配 Episode（`test_real_run_turn_clarifies[uncertain]` 钉：resolver/模型零调用） |

## 需要留痕的定性判断（可推翻）

**reading_baseline（判读基线）与 question_type_rules 留在 material_only payload 里，定性为「方法文案」不越 P3 红线。** 探针发现 payload 含「成交额」字样，溯源是判读基线的方法规则（「supporting_evidence 须写出成交额及环比等具体数值」「CR-01 先阶段再板块」）——纯 how-to-read 文本，无任何市场数值、无 IO。P3 的红线是事实注入与读取权限；方法约束对材料提纯题可能是噪音（诱导盘面框架），但那是答案质量问题，归 P4/P6 再议。若后续 P6 判定它污染材料题，收口点在 `build_episode_input` 的 reading_baseline 组装处按合同过滤。

## 钉测试

`test_material_only_payload_carries_no_market_metadata_or_tools`（test_e2_material_turn_delivery.py）：material_only 装配 payload 的 today/latest_data_date 为 None、available_tools 空、无 prime 槽、方法文案之外无市场数值残留。这是防回归钉（预期恒绿），不是抓虫反例；任何人把市场元数据/prime 槽加回 material_only 都会被它抓住。

## 结论与边界

P3（D4 冻结点 + 同源过滤 + dispatch 兜底）的注入面在本分支实现上核查完毕。仍然不安全的（原样保留，非本核查范围）：注入式 registry_factory 内部已发生的读取（P3c 声明）；引擎 B 内部无合同意识（P3h 声明，两道门外不得直调）；fictional×full 的前提标注送达（P4/P6）；D7 跨轮继承五格的全链版（P5，`test_axes_update_independently` 只盖编译器层）。
