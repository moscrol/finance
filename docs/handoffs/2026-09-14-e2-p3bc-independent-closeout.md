# E2 P3b / P3c + 返修独立审查收口

## 背景与身份

2026-09-14，续接服务并发错误中断的会话。开发树 `fwp-wt-e2-boundary-closeout` 与独立树 `/tmp/e2-qc-301dcd9e` 均固定 `301dcd9e1eef5095424027ffa703bfeab2472cc6`，开工均 clean；主检出树的他人改动未动。

既有 inflight / 产品门 / 能力图仍停留在 b4ba6fb5 的“独立审查工具前受阻”。本次读取最终报告发现审查已实际完成，故先收口证据与状态，再推进下一片；不继续等待已经结束的进程，也不把 harness exit 0 当 pytest 通过。

## 按发生顺序

1. 前轮独立发现 batch / repair 同名 runner 替换后，实际菜单及执行拒绝，但 Scope 授权仍引用旧实现，reason 为空。返修 `301dcd9e` 在执行时重绑 Scope，保留更严上限和累积诊断。
2. 返修独立探针 36 绿 1 红，晚结果的 runner 计数为零。最终审查跟踪原探针，发现 slow 回调放行后调用 `base.runner`，再次进入 deadline 适配器；过期检查先于 fixture 结果生成。原针没有产生其声称要观察的“晚结果”。
3. 原失败脚本/日志原封不动保留，另存单层慢回调版本，直接产生相同临时结果。原 7 个 assert 全保留，新增顺序、事件、结果身份与账本丢弃断言，仍用 .08s deadline，不加 sleep，不调应用。
4. 独立报告裁定 P3b、P3c+返修均通过，仅限本片。修正版37P、重复10P、重点38P、相关106P，禁止 IO 0；原跟踪针1F/exit1保留。
5. 本接续宿主校验46个原件哈希及三段git diff；复制报告、两份prompt与全部证据到仓内，再逐项校验归档字节，核对日志及真实pytest exit。未重跑已判清的测试，未伪称再一次独立QC。

完整证据：[归档说明](../verification/e2-boundary-closeout/qc-301dcd9e/README.md)、[独立报告](../verification/e2-boundary-closeout/qc-301dcd9e/report.md)。历史 b4ba6fb5 的阻塞/首轮RAG失败收据不改写。

## 方案与取舍

| 方案 | 决定 | 原因 |
|---|---|---|
| 红针改应用或放宽超时 | 否 | 红来自二次进入适配器；改产品不证明迟到结果归属 |
| 删除失败 / xfail | 否 | 失去最初反证和修正因果 |
| 原件 + 修正版 + 执行顺序 + 断言保留收据 | 采用 | 可证明测试变的是刺激方式，不是判据 |
| 历史测试直接放 pytest 收集路径 | 否 | 故意失败的探针不是产品回归，且有固定临时根 |
| 全部证据逐字节归档，py/log追加.txt | 采用 | 避免误收集与日志忽略；manifest可还原原名并校验 |
| 因局部QC绿而宣告完整P3 / 合并 | 否 | 入口提前读取、来源过滤、恢复及确定性旁路仍未验 |

## 下一片定位（仅源码定位，尚未实施/验收）

地图刷新到301dcd9e后 query 为ready，但结构检索无命中，未拿空结果作架构依据。精确定位 `TurnOrchestrator` 在 `intelligence/runtime/conversation_orchestrator.py`，不是同名文件。

- `_run_turn_ledgered` 在 TaskFrame 确立之前把 `context.to_prompt_block()` 送给 controller（约1905行）；controller 的 QueryResolver 又先于物料边界编译。此链需要完整前置语义与可信基底方案，不能临时把所有“继续”拦成材料澄清。
- TaskFrame 已有后仍读取 inherited answer spec（约1977行）、stance pack（2051）、project prior（2068）、active perspective（2117），然后才到 Episode 工厂。下游丢弃字段不能撤销这些读取。
- 可先单独压“明确 material_only 的未分型外部事实先验读取”，与普通/full/local_only正例成对；保留未覆盖controller历史/可信续轮的诚实边界。下一实现必须使用真实 `run_turn`，不只测工厂清字段。

## 不得外推

未覆盖：controller早读、全部四组九类来源过滤、预取前歧义/基底不可恢复澄清、可信逐轴继承、registry_factory内部IO、压缩/崩溃恢复/子研究/非工具事实/确定性旁路，local_only原题号槽与更多认证runner、P4–P7。内存repair不等于崩溃恢复，合同from_dict不等于恢复纯度。

本轮未运行全仓/前端/E2E/金融模型/原始T2→T3；未推、未合、未部署。RE06 I14另线，不扩大为E2比较前置；6c7bea6e/413b7a07重叠仍待集成接替声明。

## 工具沉淀

本轮新增的是历史审查原件归档，不是新运行工具；原探针已有正式运行期回归测试，独立增强版及重放说明在归档，不包装为自动产品门禁。跨项目原则“晚完成≠超时后再发起调用”补入已有 evidence-hygiene 笔记；事件/断言脚本保留可复现性。harness-reference 开工树脏，本轮无通用搭建件改动，不碰共享脏树。
