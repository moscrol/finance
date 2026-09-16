# E2：P2返修与P3a局部冻结收口

2026-09-14。开发树 `/Users/a77/fwp-wt-e2-boundary-closeout`，分支 `fix/e2-boundary-closeout`。本快照记录到应用提交 `e178bb57c751e97f9f1c231ce253221d0b892b58`；未合、未推、未部署。不是正式效果验收。

## 背景和发现顺序

D1 在 `71929260` 获得可执行独立复审通过后，P2 `85a20eb2` 将双轴、前提来源、完整题组接到 TaskFrame。独立复审发现连接词漏第二权限、state_unavailable 可恢复伪造已解轴；全仓另外暴露普通研究追问被未就绪的材料澄清闸劫持。`a3fea5d4` 修复后独立复审发现“且麻烦/烦请不要联网”仍漏，原因是切句和识别各有前缀规则。`8d1b3573` 共享前缀并扩组合测试后 P2 独立通过。

P3 检查发现 `build_episode_registry` 在组工具菜单前已调用根路径、市场日期、实体解析，返回时还会开场预取。所以授权集合清空不是唯一拦点。P3a `e178bb57` 增加：
- `ResearchTaskContract.material_contract` 持久化；material_only 不允许非空授权、任何 requirements（包括 optional）、输出工具 evidence_types。
- 工厂在 mandatory 回补后收窄；按连续原题号生成 answer_q{i}，仅范围槽用 user_premise，其余事实槽仍 evidence。
- 跳过静态知识库预检；清掉未分型会话/视角/stance/阶段背景。
- 注册表在任何根/日期/实体/开场预取前返回空注册表；直接调用开场预取也短路。
- 复用既有 dispatch 和 EpisodeScope 拒绝强塞工具并记授权拒绝事件，不新造执行器。

## 方案取舍

| 采用 | 否决 | 原因 |
|---|---|---|
| 双轴独立、显式范围另记 declared | 虚构自动 evidence-free | hypothetical×full 仍需要真实事实证据 |
| 切句与句首识别共用前缀 | 每遇漏词在两处各补 | 两张词表会在礼貌词组合上再次漂移 |
| 坏状态拒绝反序列化 | 丢坏字段后默认 full | 恢复失败不能变授权扩大 |
| 暂不把未就绪材料状态接全局路由 | 所有“继续”一律材料澄清 | 普通研究追问发生实际回归；P3/P5须可信地分流 |
| 冻结三元组+装配前短路 | 清工具菜单后假定零读 | 预取/日期/实体读取早于菜单 |
| 新answer槽仍 evidence | 所有题都 user_premise | 范围声明不能替事实锚定；P6未完成不能求假绿 |
| 明示P3a局部结论 | 工程局部绿升级安全实跑 | controller前缀、旁路、恢复等还未覆盖 |

## 验证与证据

证据目录 `docs/verification/e2-boundary-closeout/`：
- `qc-85a20eb2-findings.md`、`qc-a3fea5d4-findings.md` 保留退修。
- `qc-8d1b3573-pass.md`：P2独立332 passed/4 skipped；原46针46/46；独立35组合35/35。
- `full-8d1b3573-tests.txt`：原始全仓9731 passed/1 failed/83 skipped/2 xfailed；失败是本地旧图未召回daily-full正式入口。main同版脚本在同图复现，按官方build刷新后单针通过。未改测试、未删图求skip，不把复测拼成全仓绿。
- `qc-e178bb57-pass.md`：P3a独立222 passed（六文件180+协议42）；九种复制/恢复重加权限拒绝、三种强塞工具拒绝且trace、短路替身通过。
- `frozen-e178bb57-tests.txt`：干净版本定向446 passed/4 skipped/1 xfailed。
- `full-e178bb57-tests.txt`：干净版本完整pytest 9743 passed/83 skipped/2 xfailed，exit0；收据 `~/.finance-runtime/test-receipts/20260914T113853Z-e178bb57.json`。
- 全仓Ruff、unread-fields、diff、提交钩子通过。未调真实金融模型或金融API；测试替身与临时用户根不是真人效果证据。

独立探针两处适用前提错误已保留：17/29不连续号上游只留q29，v10仅保证“序号连续成组”，不是本次P3a新增回归；原T3单轮是state_unavailable，不能按明确material_only期望八槽。原文本/评分/46针不改，不以探针适用前提修正宣称消灭上游限制。

## 后续与禁止事项

P3b：审实际IO而非cost/freshness；追 `market_data` 估值东财、前瞻隔夜美股，`financial_data` 实时补取，`evidence_search` 判官，`kb_rag` 子进程/模型加载等混合路径。已证明的本地能力保留，未证明/混合不默认放行。

P3其余：controller调用前的旧摘要、stance、project prior、视角读取，adapter确定性旁路、legacy回落、agent_episode开场账本播种/压缩/恢复/子研究、系统默认事实前缀；工厂清理不足以证明整链。

P4逐题三态交付、P5可信逐轴继承与旧答来源身份、P6材料锚点纯度、P7全新原始T2→T3尚未完成；T3不得重贴禁令。先冻结候选与实际模型调用策略再做Knevo比较。RE06 I14另线，不扩大为纯材料题比较前置。

工具沉淀：本轮新增的权限绕过、optional计划、IO短路变异已成为仓内 `test_e2_material_freeze.py`，不把重复手工排查仅留/tmp。未新增跨项目脚本；共享harness-reference树脏，不动它，也不另造能力清单。
