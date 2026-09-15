# 2026-09-15 · 同花顺目录/成员采集版本收口

## 背景与固定范围

用户允许同花顺自己的板块和成员，不要求复制复盘会名单或双红入选集合；公式、参数、单位、复权和窗口仍须明确。先并跑、再只读验算、后生产投影，不能把换池授权放大为切源或改算法授权。

作者树 `/Users/a77/fwp-wt-hithink-review-wiring`，分支 `fix/hithink-review-wiring`，基线 `1fef3d27`。前两片 `9621128a` / `dcee18f2` 与归档 `fdbe5dad` 的历史结论见 [前一快照](2026-09-15-hithink-review-wiring-preview.md)，本次没有重命名或借用其收据。

第三片固定代码 `c85d01017fa239aa3b2101b1585e8f5c07e005b3`，提交14文件（1187增/67删），包含合同、写者/审计读者、schema、同步/CLI/预览接线、测试、ledger、术语和 [ADR-0004](../adr/0004-hithink-capture-is-not-publication.md)。之后只归档文档/证据，**全量结论仍绑定c85d0101，不把文档提交称为另一次全量**。

未push、合并或部署；没登录复盘会、取行情供应商key、请求真实行情或改生产库。生产写入仍只允许既有daily-full暂存校验＋原子换库；历史补数另按duckdb-backfill技能取得授权。

## 按发现顺序

1. 每日最新目录/名单可事务替换，但无法保留同日旧批和多标签原件。因此新增 `ops_hithink_sector_capture` / `ops_hithink_sector_request`，由既有同步器调用 `SectorCapture`，先登记唯一台账写者，不另开发布入口。
2. 仅保存成功项会让执行覆盖率天然100%。先落四类目录计划，目录全成功后按代码并集冻结全部成员计划；重叠标签保留，但成员每代码只请求一次，limit未选中也记skipped/limit。resume不能借旧批响应。
3. 请求前把requesting提交；慢IO期间不持写事务。每次写入短事务争用同一批次头，只接受running，避免检查后被其他写者封存。终态不可经该写者覆盖，重跑生成新ID。
4. 只存白名单规范化行、计数、真实带时区时间、合同版本、行指纹和封存清单。目录/成员共享合同模块，审计不反向依赖外呼同步器；业务码要求真正int的0，空/坏/歧义列表拒绝，不过滤坏行后缩池。
5. 审计重新核对计划、合同、原件、计数、指纹、时间、终态。消费直接用此次读取已验证的行；指定批次缺失/partial/损坏不得回退最新每日表。未传ID保留legacy，但明确无请求审计资格。
6. 边界测试先复现缺合同列和CLI未报告范围/partial返回0；修复后不限量审计失败抛错、显式limit partial返回2。同步首错不能被审计封存的第二个错误遮盖；进程打断可诚实留下running/requesting。
7. 补齐ADR后先提交代码，再在干净固定SHA上全量、前端、E2E、六类作者变异，最后归档。独立QC启动失败单独记，不以作者验证代签。

## 关键取舍

| 方案 | 评价 | 决定 |
|---|---|---|
| 只保每日最新表 | 简单，但同日覆盖/标签覆盖后无法回答当次名单 | 保留兼容投影，另存显式capture版本 |
| 行数相等即供应商完整 | 合法截短响应也自洽，没有独立全集分母 | request_complete与provider_completeness分列，后者unverified |
| 保存完整供应商原始响应 | 可还原更多调试细节，也会带入未知字段/错误正文 | 白名单JSON＋指纹；不是逐HTTP尝试审计 |
| 网络全程一个大事务 | 锁占用长，中断前请求状态对其他读者不可见 | 计划/占位先提交，写入短事务竞争批次头 |
| 检查complete一列或验证后再查原件 | 损坏、并发换行可能逃过校验 | 校验完整清单并消费已验证行，不二次读取响应 |
| 指定批失败回退最新名单 | 能多产出数字，但丢掉用户选定版本及审计语义 | 明确拒绝，CLI结构化缺口＋非零退出 |
| 把capture当SectorUniverseStore已发布身份 | 请求齐不等于canonical行情/名单可用 | 不发布、不写公开VIEW，production_ready恒false |
| 用当前名单回标历史K线日期 | 制造未来信息 | 真实上海接收时间；跨午夜不能硬拼单日 |
| 新建测试运行器/发布器 | 增加平行入口与维护面 | 复用pytest/现有CLI/Playwright/registry工具，不扩功能 |

版本只冻结目录和成员；行情仍从当次canonical读，不能称完整时点回测。终态保护是写者层的不可覆盖＋损坏核对，不是管理员无法修改的物理WORM或外部签名。失败批在实际库内保留，staging被丢弃后不承诺永久留存。固定宽基指数、K线请求/字段覆盖和客户端逐HTTP重试不在本次逐请求审计范围。

## 验证与收据

所有原件在 [证据目录](../verification/2026-09-15-hithink-sector-capture-audit/README.md)，含环境、命令输出、退出码、补丁及16份测试收据；`SHA256SUMS`核对文件，`*.output.json`按lines无损还原。SHA256不是业务正确性证明。

### 正向验证

| 项目 | 实际结果 | 适用条件 |
|---|---|---|
| 全仓Ruff | All checks passed，exit0 | 干净c85d0101 |
| 全量pytest | **9739P / 79S / 2X / 17warnings**，342.77s，exit0 | 收据`20260915T072124Z-c85d0101.json`，dirty=false，error/failed=0 |
| 收据检查 | revision/解释器/Python/依赖/clean/无绕过全部通过，exit0 | Python3.12.13，依赖指纹3328bed61f3e21ea；没有把旧SHA收据套给新提交 |
| 前端 | 离线frozen-lockfile安装；lint/typecheck/build exit0；Vitest **76P** | 本机Node26.0.0、pnpm10.12.1 |
| 浏览器端到端 | Playwright桌面/平板/手机 **15P**，47.8s，exit0 | 临时18975服务，真实浏览器与合成夹具；不是生产数据/真模型验收 |
| 提交hooks | 代码提交全部适用hooks通过 | dataset归属51张表/2个VIEW；没提供可读DB，空表内容检查跳过 |

Python使用主树 `.venv-workbench/bin/python -m …`，验收壳清环境和umask022，不绕依赖门。E2E通过env-i、`FORESIGHT_LLM_KEYCHAIN=0`禁读取凭证；数据/wiki/users根为测试夹具，部署台账覆盖到 `/tmp/hithink-capture-e2e-c85d0101/deploy-ledger.jsonl`，没污染生产台账；服务已退出。模型设置测试里的key是合成占位，不访问供应商。

**环境限定**：工作流声明Ubuntu/Node22，本机只有Node26且未安装Node22。本次执行相同前端检查命令，但不是相同操作系统/Node版本，不能写成CI环境已完全复现。三视口测试覆盖既有Workbench交互，不验证同花顺真实日报、研究队列、矩阵或市场快照。

### 作者变异验证

隔离树 `/Users/a77/fwp-wt-hithink-capture-mutation-c85d0101`，固定父SHA同上。每轮只修改一种保护，跑两个capture测试文件（55项），保存git diff，再恢复；不是独立审查者。

| 变异 | 实际结果 | 收据 |
|---|---|---|
| 计划仅落selected，删掉limit未执行项 | 3F/52P，exit1 | `20260915T074610Z-c85d0101.json` |
| 不核对封存清单指纹 | 1F/54P，exit1 | `20260915T074730Z-c85d0101.json` |
| 写者去掉running终态条件 | 2F/53P，exit1 | `20260915T075352Z-c85d0101.json` |
| 删响应时间先后/完成边界校验 | 2F/53P，exit1 | `20260915T075918Z-c85d0101.json` |
| 同步CLI对partial也return0 | 1F/54P，exit1 | `20260915T080612Z-c85d0101.json` |
| 批次读取ValueError后回退legacy预览 | 6F/49P，exit1 | `20260915T080729Z-c85d0101.json` |

均非语法/收集失败。回退变异既有缺最新表的CatalogException，也有未抛预期错误和request_complete从false丢成null的行为断言；不把6F都说成“错误地产出完整候选”。行指纹/合同/占位/并发/中断等有正向和损坏反例，但没有宣称每条保护都独立变异覆盖。

恢复后六个定向文件（capture单元/集成、kline、preview、local wiring、registry）**141P**，4.87s、exit0；收据`20260915T080851Z-c85d0101.json`，dirty=false，收据检查exit0，最终树干净。六份变异收据刻意dirty=true，不是固定干净提交失败。

开发期收据也保留：父fdbe5dad下27F→27P→104P→104P，补边界2F/48P→127P→132P→141P；全都dirty=true，不是fdbe5dad干净结果，更不是第三片全量。

### 注册表、图谱与检索

- 跨仓五命令逐一执行：parseability60个SKILL可解析；check因KB七个技能指纹漂移exit1；文档表、视图、ledger crosswalk均exit0。没有代重扫KB指纹；七个名称及新旧hash在原日志。
- 单仓固定c85d0101树（本次QC目录下 `finance-workspace-private`，在启动QC前跑）：五命令exit0，38个SKILL可解析，按现合同跳过缺仓23个技能。两种布局的crosswalk均保留96条反向warning。**单仓绿不覆盖跨仓红**。
- 图谱回写SectorCapture/audit_capture/capture_inputs三条分支断言；前/后audit均exit0，64节点行、127→130断言、74→77在途/未校验。后一次对象是agent-memory@056ce80e clean、主检出b4a35fa2 dirty、KB6431e6b8a dirty，只证明这些对象下的路径/符号检查，不是合流运行验证。
- code-map build/query exit0，但vault unavailable、structure missing、recall untested；以直接源码/测试定位，不从ready推完整检索。

## 独立QC实际状态

| 固定范围 | 启动结果 | 可采信的结论 |
|---|---|---|
| 前两片dcee18f2 | Codex exit1、额度失败 | 未产生审查推理/探针/报告 |
| 前两片dcee18f2 | Claude exit1、HTTP503无可用账户；input/output tokens均0 | JSON虽subtype=success，但is_error=true、terminal_reason=api_error；不是成功 |
| c85d0101第三片优先＋前两片组合 | 新Codex会话exit1、额度失败；另有模型刷新/配置warning | 新固定范围也未实际审查，不能说“未发现问题” |

请求和原始输出均归档，`report.md`未产生。当前QC目录 `/Users/a77/.finance-runtime/reviews/hithink-c85d0101-qc-20260915/` 可供下一审查者复用。没有自动重试风暴、借作者变异代签或把其他任务取消QC的决定继承到本任务。

## 当前边界与下一步

1. 本片代码和作者验收已经固定；后续先处理独立复核可用性、当前跨仓registry漂移及Node22/Linux环境差异，不以这些未决项阻止离线设计，但不宣称merge-ready。
2. 再做通用canonical投影前先明确元→亿元、股→手、复权/窗口/涨幅分类与目标日关键值覆盖。新池经SectorUniverseStore候选/发布接口，不强制旧`.FP`映射；单日白名单repair不是通用日更器。
3. local仍skip-constituents，只能拿catalog-only请求完成度；没有自动采新池成员、没有投影新池、没有恢复日报/队列/矩阵/snapshot。真实数据和历史补数另要授权，不为赶报表用异口径篮子资金补旧面板。
4. 合并/部署另需用户确认，生产只走已有暂存验证/原子换库。未继承local-plan-gate-alignment、generation-stage-code-root等他枝成果或测试收据。

## 工具与记忆归位

能力更新进入既有图谱行，稳定方法补入 `source-switch-coverage-must-be-reconciled-first.md`；项目MOC仅留任务行/索引。真正的自动保护在合同/审计/CLI及pytest内，执行复用现有测试/收据/registry/graph工具，未建第二套测试运行器。归档JSON只做原件无损包装，不是运行门禁。`~/harness-reference/BUILD.md`已有他人修改，未触碰，也未为本轮复制第二份工具清单。
