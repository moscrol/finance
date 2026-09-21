# 2026-09-22 严格截止与本地快照续修

## 背景与范围

上轮两题真实 Workbench conversations 验收未过：当前题误称本地无09-21行情，实际日快照存在；历史题模型本次自然守住09-11，但合同仍是09-21/runtime_default，只读探针可取得09-18事实。不能把模型一次选对当成系统强制，也不能用某次查询空结果证明整个本地没有数据。

本轮修复提交 `b41c8d4755ae1a6735828b911197f3b62407f58e`，追加边界及测试修复 `b1e04452bfd45ae2fa4e9177847cb299293ca859`，固定源码树 `e104eb0fcbf4f11dd74326ce411f568019c3a10b`。证据提交 `f7d417238753ea0035ebd31fc134a916a2020643` 只加文档。工作树 `~/fwp-wt-market-date-advisory-0921`，分支 `fix/market-date-advisory-0921`。

结论 **AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED**，不是完成工程门禁、独立验收或真实金融质量验收。无push/PR/合main/部署/补采/生产库写入。

## 按发现顺序

1. `honesty_gates.requested_information_cutoff` 识别明确截止、截至及排除未来数据等有限句式，排除引用/代码/已识别材料。factory将用户与调用方上界取较早值，仍保留requested严格语义。
2. 新增只读 `local_market_snapshot`，仅为已有市场读取授权的local_only回合补入。最初无条件扩全局模型读取名单的方案已撤销；综合market_data仍不能进入local_only。material_only在路径发现/读取前返回空注册表。
3. 日文件加载器只打开截止内文件，核文件日、trade_date及显式served/source日期。新坏文件可以退到旧有效文件并披露，不读latest/meta为历史补齐。封存未显式配置根时不回落生产目录。
4. 证据保真实日期、质量、NULL/0、原JSON下标和结构化数值。快照阶段、行业涨停池不冒充复盘阶段或主线全集。题材过滤后的locator重编号问题已修。
5. requested严格截止隔离未来证据之外，也处理整块观察文本、原始gaps和trace.detail；query ledger的variant含strict_cutoff，防同日先宽后严复用。runtime-default旧行为暂保留。
6. b41变异22项捕获21项，future_snapshot_allowed漏检。原因是测试替身在read_text内抛AssertionError，被加载器异常处理吞掉。改成记录读取路径，在返回后断言；不是为通过测试放宽生产逻辑。
7. 作者复查补“站在较早日”与“截至较晚日”并存、重复无年份日期跨年两个边界，所有已识别上界取最早。形成b1新候选，旧检查不移签。
8. b1完成固定定向/变异/前端/注册表；完整Python因磁盘不足未开跑，独立Spec/Quality旧候选尝试因容量错误无结论。未启动新K3真实入口。上轮未通过结论继续有效。

## 决策比较

| 问题 | 被否方案 | 采用与理由 |
| --- | --- | --- |
| 历史截止 | 只提示模型不要越界 | 进入既有InformationCutoff，调用方只能收紧 |
| 严格隔离 | 只删EvidenceItem | 同时隔离可能携带未来事实的文本/诊断和缓存复用 |
| 快照可见性 | 放开可能联网的market_data | 新增窄只读工具，仅local_only且已有市场授权时补入 |
| 历史快照 | 借当前latest/meta补质量 | 截止内日文件自身身份与质量决定，不伪造当时状态 |
| 封存路径 | 缺根时默认生产目录 | 返回局部缺口，不调用loader |
| 读取禁止测试 | 替身抛错等于未读 | 累计读取尝试，返回后断言；变异必须使断言失败 |
| 全量资源 | 降准入线/删他人数据 | 保8GiB准入及3GiB运行底线，未开跑明确blocked |
| 真实复验 | 用定向绿或旧K3稿签通过 | 工程完整准入后重跑两原题，判官与公开稿另验 |

有限日期句式不等于通用自然语言理解；日文件时间标签也不是所有内容在当时已公开的PIT证明。日期不同不撤真实事实，但期间、单位和比较口径仍需独立核验。

## 验证与精确收据

固定b1首尾干净，主树 `.venv-workbench/bin/python`，Python3.12.13，依赖指纹 `3328bed61f3e21ea`：

- 11文件定向326P、全仓Ruff exit0；JUnit326与精确收据一致。
- 收据 `~/.finance-runtime/test-receipts/20260921T165015Z-b1e04452.json`，SHA256 `2f18cb54e7fb62cb72f828d583a86e5d2e7f0a78dcaca48ee7e0121bd33a8194`，归档内有逐字节副本。
- 24/24进程内变异被捕获；正常臂通过、错误臂为断言失败且无collection/setup error，不改候选源码和生产数据。
- 前端安装/lint/typecheck/test/build/E2E全部exit0，110单测、34 E2E通过/2跳过。
- 注册表parse/check/tables/views与ledger crosswalk五项exit0；不是跨仓图谱全能力认证。
- 完整Python未开跑：b41等待器pid13134检查列表为空，资源持续低于8GiB后只停自有等待器。b1没有新的全量进程；检查后空闲约3.2GiB，未删他人目录或降低安全线。
- Spec/Quality仅旧b41尝试，host/CLI/模型不支持/容量错误均保留，最终无结论；只读smoke不是审查。b1独立审查尚未执行。

b41前端/注册表通过、21/22变异与开发脏树323P/22P/68P单列；不得移签b1或将后者定向绿写成全量绿。旧c57完整工程收据仍只签旧版本。

## 封存与勘误

证据 `docs/verification/2026-09-22-market-cutoff-snapshot/`：247原件、1,313,993字节；250内容文件加SHA清单自身共251文件。原件均字节相等；`check_evidence_archive.py`对f7d417238核新250/250、旧K3 68/68、旧工程200/200通过。

最终SecretScanner扫描249个文本，19文件/模式组、238次命中、32唯一值，均精确核为源码模块/属性/配置键，未分类0；不是零命中认证。初次扫描245文件、191次/32唯一值、60待核命中原样保留，分母变化来自新增收尾材料。

进度曾误说“八项新增捕获”和“变异未完成准备停止”，机器结果证实终止尝试前已完成22项，21捕获/1漏检。保留closure-notes及closure-errata，不改原结果。外部run_checks有E702格式警告；临时格式改动未执行并恢复受测字节，不能称全部外部脚本Ruff通过。最终归档器另有Ruff0。曾尝试过宽标识符分类但未执行并已恢复，最终使用精确复核集合。

首次Git归档校验误用本工作树不存在的 `.venv-workbench/bin/python`，exit127、未执行；随后用主树规定解释器才取得上述三包通过。

## 接手与边界

先恢复足够磁盘并核当前main、分支身份与授权，再在干净固定版本跑完整Python及独立Spec/Quality。资源检查不是宿主空间预留；不得清理未认领数据。如果改源码，所有必要验收重新绑定新版本。

之后仅两道原题通过真实 `/api/conversations` 与messages复验，K3写手/GLM判官、隔离用户/存储/端口、凭据只内存；按run_id终态与assistant_message_id取公开稿，核合同截止、实际证据日期、快照可见性、引用和判官。保留完整可用prompt/事件证据，不能把completed当质量通过或N=1当改善率。

本轮未起新sidecar；19651/19654/19276收尾无监听，检查/审查进程已结束。没有本轮生产健康认证。外部 `market-cutoff-snapshot-k3-20260922/run_live.py` 只是旧驱动副本，仍含旧身份，禁止未改直接运行。市场题误路由company/stock_deep_dive仍单列未修。未验后来main组合、自然夜跑、浏览器真实业务或生产效果，不接管其他在途分支。

## 工具沉淀盘点

机械保障落正式日期/快照pytest测试；复用既有收据、前端门禁、SecretScanner及Git归档检查器。候选专用驱动冻结为.py.txt，只是可复核实验，不晋升新通用入口。读取禁止测试方法追加到已有 `denied-io-tests-must-count-attempts`，能力更新回唯一图谱；本轮不新增驾驭层通用组件，不动harness-reference。

共享记忆回写后图谱审计94节点/276断言无漂移，225条在途/未校验仍明确保留。脚本MERGED标签只证明同名符号存在，不证明本候选实现已合入，故候选分支标记不移除。vault全库修改前后同为26 errors/17 warnings，只有项目笔记字节数提示变化；不签全库通过、不清理他人存量。原始报告留 `~/.finance-runtime/reviews/market-cutoff-snapshot-20260922-closure/{vault-before.log,vault-after.log,graph-audit.log}`；这些收尾报告在证据包提交后生成，不属于已封存250文件。
