# 自主研究续修：明确本地来源限制与审查输入保真

## 状态

本轮从 `feat/adaptive-research-loop@1c3a6b9a` 继续。工作树 `~/finance-worktrees/adaptive-research-loop`；主检出树有他人在途改动，未碰。

- `b6df991f`：修复明确本地来源限制漏识别，沿用原材料合同与执行授权。
- `03c08f48`：检查器保留父会话工具观察、失败和答案各阶段；可在封存包之外输出。
- 干净 `03c08f48fdf9e94acdbb3066e924637087171331` 完整 Python：12010 passed / 85 skipped / 2 xfailed，696.40 秒。
- 未 push、开 PR、合 main 或部署。`WORKBENCH_ADAPTIVE_RESEARCH` 仍默认关闭。8792 健康，仍运行 `bf662e9310ff751a4c31763815ee78fb7d6d5122`。
- **公开稿保真未修；未重跑真实研究、未证明观察后改向或质量提升。**

上一轮实验与失败事实见 [四题对照快照](2026-09-21-adaptive-research-holdouts.md)。本文件不改判旧实验。

## 按发现顺序

### 1. 原题没进入已有权限合同

直接对“只用本地已有资料，判断中际旭创最近是否存在已确认的重大风险；没有查到的部分请单独列出。”调用分类器，得到 `no_constraint_confirmed`，材料合同为 None。

仓库已经有 `MaterialContract`、`restrict_read_capabilities`、注册表实际 IO 上限、Episode 绑定和引擎 B 掉落总闸。缺的是原始用户表达进入这些合同的第一步，不是再建一份工具黑名单。

先加测试：原题允许 financial_data、news_search、market_data、web_search 到达参数解析函数，尚未进入 runner 已足以复现授权失效。测试统计调用尝试，不只依赖抛异常，避免异常被生产降级路径吞掉。

### 2. 共用识别器，只收窄不扩权

`user_task.py` 增加带来源名词的明确句式识别：只用、仅使用、只读取、仅限等，后接本地资料/数据/知识库/材料/档案及已有/现有/存量限定。切句、材料区复核、顶层指令识别和 `material_contract.py` 编译共用它。

引号与代码框中的文本仍不是授权；否定表达、“本地化语言”“本地企业”不误命中；不确定材料块/题内限制仍澄清。同句并且、礼貌前缀、显式放宽和引用内假放宽有回归。

早期测试曾把“仅根据本地资料”“只依据本地数据”改为 local_only；复核后撤回。已有材料边界可能指“本地资料中的以下片段”，不能因此授权检索整个本地库。保留原 material_only 优先级，原题则接通 local_only。

执行测试覆盖参数解析前拒绝、伪装成本标签不能授予权限、未知/混合实现不放行；原题加入临时源的 current/missing/empty/stale 四态网络/子进程计数测试，以及真实 TurnOrchestrator 无 adapter 时不掉进无合同意识的引擎 B。

这不是任意自然语言理解保证、操作系统网络沙箱或整个材料系统验收。未扩展本地工具允许集合；模型推理服务与市场数据读取的边界沿用既有合同。

### 3. 检查器补观察与交付阶段，不造质量分

`scripts/inspect_adaptive_research.py` 保留完整父会话 `tool_request/tool_result/tool_error`，包括 call_id、查询条件、空 evidence、观察正文与失败；继续保留原调用/计划指标。新增提交稿、核验稿、核验 gaps、公开稿、逐句判据、实际 answer.md。

增加 `--output`，在原封存目录之外重检；目标已存在仍拒绝覆盖。清单也覆盖实际交付、配置、结果和源协议。不把“判官 passed/repaired”或更多观察当质量分。

四题八臂全部重新提取，使用对应封存私有 Episode store。仅父会话，不代表子研究逐轮复核；未发起新模型调用，旧题仍是已消耗回归题。

### 4. 公开交付的剩余断点有了准确定位

1. **运行时判官丢查询身份。** on 臂 seq9 请求 regulation_event_daily、stock_code=300308、窗口 2026-08-01 至 09-18，seq13 返回空。`episode_semantic_verifier._semantic_tool_status_registry` 仅按 capability/status/result_count/source_trade_date 去重，丢 dataset、requested_time_range 和调用身份。监管、行情、核心股三次空查询会合为一条，判官后来却断言“没有监管查询”。`judge-status-projection.json` 是对原 verified traces 的确定性重建，不是新捕获的模型请求；这段源码与旧实验版本无差异。修复应从原始结构化事件保留条件，不能解析诊断 prose、不能给空查询伪造事实 E 卡。代码匹配和覆盖完整性尚未核验，查过为空仍不能证明无风险。
2. **删掉推理前件但留下后件。** on 原稿有营收环比降速前件；sentence_verdicts 记录 preflight 以 novel_numeric_condition 删掉整句，公开稿留下“但同季净利……”。本轮没有放宽数值门，也没有恢复被拒句。
3. **重要缺口只在内部。** 非本地财报来源、现时估值未知、专项风险缺失没有完整进入提交稿/公开稿；adapter 的 open_gaps 主要来自未满足输出槽，不等于 outcome.gaps 全部公开。不能将私有 gaps 全量拼接给用户，也不能把内部记账当公开披露。

这些与在途 `feat/research-answer-preservation` 的准入、核验、交付分账相邻，本轮只定位，不移植其代码或另建修稿循环。该分支本身仍未完成真实行为验收。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 共用识别器接入现有材料合同 | 再加工具名黑名单、提示模型自觉遵守 | 问题在合同未生成，执行层已有上限 |
| 保留旧 material_only 与受保护区域 | 见“本地”就放行本地读取，扩大“只依据” | 来源词不能消除材料片段边界 |
| 新目录重检、保留各阶段和空结果 | 覆盖旧审查或只给 E 列表 | 要能区分没查、查空、查失败、删句与漏披露 |
| 公开保真继续阻断 | 自动恢复被拒句、直接拼接私有 gaps | 两者都绕过现有核验或可能泄漏未核验内容 |

## 验证与原件

证据根：`~/.finance-runtime/adaptive-local-boundary-20260921/`，46 个文件封存；SHA256SUMS 自身哈希：

`6c8694d35b6e16069fc241c7194308330171755c430d57161d18a332ec7a9d3a`

- 原题与检查器修改前失败：`local-scope-red.log`、`inspection-red.log`。前者含已撤回的早期扩权提议，不是当前完整测试清单。
- 最终定向：`targeted-final.log`，464 passed / 4 skipped。
- 既有纯分类器探针：`e2-boundary-probe.json`，干净 03c08f48 上 46 passed / 0 failed；不代表 P2-P7。
- 完整 Python：`full-pytest-03c08f48.log`，干净收据 `20260920T171403Z-03c08f48.json`，exit_status=0；`receipt-check.log` 条件验证通过。
- 全仓 Ruff、git diff --check、提交门禁通过。17 个全量警告来自原市场阶段玩具模型数值运算及 datetime.utcnow 弃用。
- 原 395 文件封存包再次逐项验 SHA256 通过，未修改。新封存验证日志在根目录同级 `adaptive-local-boundary-20260921-verification.log`。
- 能力图审计退出 0，91 行/238 断言无漂移，187 条仍在途/未校验，不把 PENDING 当验收。

没有运行前端/E2E、完整独立 Spec/Quality、新版真实研究重复或未见题对照。所有本轮后台任务已结束；未碰其他树的测试。

## 下一步与不要做的

- 与答案保留链路协调，补运行时判官查询身份，再把删句断链和关键缺口未披露放进同会话修订/交付验收。
- 原预算和权限不增加，事实、推断、未知分开；不能恢复未经核验的阈值或拿空结果支持无风险结论。
- 另取未见题做重复对照；完整 Python 通过不代签自然改向、公开质量、前端/E2E 或合并资格。
- 合并及更新 8792 仍须用户确认和全部门禁。

工具沉淀：扩展现有 inspect，未另建审查管线；复现作为正式回归测试。方法进入共享闭环笔记，能力图和项目一行索引已更新。`harness-reference/BUILD.md` 有他人改动，未动；不再造第二份能力清单。
