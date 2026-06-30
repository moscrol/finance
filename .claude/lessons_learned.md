# 错误与教训

> 格式：`[日期] 错误 → 根因 → 正确做法`

## CDP / Web 抓取

- **[2026-05-08] CDP eval 用 `--data-urlencode` 导致 "Uncaught" 错误。**
  根因：CDP 代理的 `/eval` 端点不对 body 做 URL decode，`--data-urlencode` 把表达式编码后代理无法解析。
  做法：用 `-X POST -d "expr=<原始JS>"`，不要用 `--data-urlencode`。Python 中直接拼 `f"expr={expr}".encode()`，不调 `urllib.parse.quote`。

- **[2026-05-08] fupanhui market data 页面 JS 环境损坏，eval 持续报 Uncaught。**
  根因：页面加载后某脚本抛未捕获异常，破坏全局执行上下文。即使是 `'hello'` 也报错。
  做法：新开标签页（`/new`）比 `navigate` 可靠；所有 eval 用 IIFE `(function(){...})()` 包裹 + try/catch。

- **[2026-05-08] Python f-string 中写 JS 代码，大括号 `{}` 冲突。**
  根因：JS 代码块和 JSON 对象花括号与 Python f-string 语法冲突。
  做法：复杂 JS 用字符串拼接或 `.format()`，不用 f-string。

## 飞书写入

- **[2026-05-08] 写入后不检查空字段，导致 45/140 条记录缺行业占比数据。**
  根因：早期抓取只解析了页面部分数据，行业3/占比3 被遗漏但未发现。
  做法：写入后立即运行 `verify_and_patch.py` 检查关键字段，白名单字段为空则定向重抓。

- **[2026-05-08] `均线上方家数占比` 字段不在飞书表中，但被加入了检查白名单。**
  根因：表结构和代码中的字段列表不同步。
  做法：检查白名单中的字段必须在飞书表中实际存在，写入前验证字段名。

## [kb] 年报 baseline 入库

- **[2026-06-23] 批量年报入库共用 batch source note 导致追溯断裂。**
  根因：`entity_baseline_writer.py` 的 `write_updates()` 对整批使用同一个 `source_name`（如 "年报 baseline batch 2026-06-23"），所有公司的 evidence 都指向这个 batch note，但 batch note 的 `company` 字段只记录了最后一家。
  做法：新增 `per_company_source_name()` 函数，年报类型时自动拆为 `<公司> <报告名> baseline <日期>` 独立 source note。batch note 只作批次清单，不作 evidence source。

- **[2026-06-23] entity 页 key_data 和一句话定位留空，baseline 对后续分析帮助弱。**
  根因：writer 不自动从 raw JSON 提取营收/净利润等财务数据，也不从 industry+main_business 生成定位。
  做法：新增 `extract_key_data_from_raw()` 自动抽取营收+归属净利润；新增 `generate_one_liner()` 从 main_business+industry 生成朴素定位。

- **[2026-06-23] 完成闸门缺少 source 追溯审计步骤。**
  根因：`check_relations_integrity.py` 只检查 JSON 格式完整性，不验证 source note 的公司归属和 raw_traces 指向。
  做法：新增 `scripts/audit_missing_evidence_sources.py` 作为第 7 步闸门，检查每个 entity 的 source note 存在性、company 字段一致性、raw_traces 可达性。

- **[2026-06-23] 年报 batch 4-5：Rule 6 双层保护 + 语义 QA + manifest 格式。**
  错误：①Rule 6 只保护 entity 正文，relations 里 `ima_stock_logic` 等高价值记录被 baseline 覆盖降级（盘江股份→煤炭）；②子串验证通过但语义错误（环保政策当主营、目录碎片当产品、保荐机构文本挂黄金概念）；③manifest 顶层 list 导致 writer `--preflight` 报 AttributeError；④重建时旧 entity 文件的脏 baseline section 被 Rule 6 "保护"。
  根因：Rule 6 只做了 entity markdown 单层保护；缺少 relations 层的 update_type 检查；语义验证完全依赖子串匹配无人工 QA；manifest 格式未标准化。
  做法：`knowledge_graph.py` 扩展保护为"任何非 baseline update_type 都不覆盖"；SKILL.md 从 8 条扩展到 11+S4+O2（新增 Rule 6 双层保护/Rule 8 manifest 格式/Rule 9 语义 QA/Rule 10 回归检查/S1-S4 应该规则/O1-O2 可选规则）；重建前必须删除新 entity 文件再重跑 writer。

- **[2026-06-23] 年报 batch 2 质量修复：5 类问题沉淀初始 8 条防护规则。**
  错误：①已有 F10 baseline 被低质量年报 OCR 覆盖（宁德时代主营变成表格噪声）；②正则扫全文误抽财务数据（宁波银行营收 7.20万元）；③`source_date` 从 PDF 误抽出未来日期；④修页面忘了同步修 relations JSON 导致 agent 结构化召回脏数据；⑤文件名冒号/下划线不一致导致 source 断链。
  根因：`extract_key_data_from_raw` 用正则扫全文无验证；`entity_baseline_writer` 无条件覆盖已有高质量 baseline；修复流程只看页面不看 relations。
  做法：`extract_key_data_from_raw` 默认关闭（`AUTO_KEY_DATA=1` 才启用）；SKILL.md 新增"年报 baseline 质量防护规则"8 条（relations 同步修 / 安全文件名 / source_date 分离 / OCR 噪声词过滤 / 已有 baseline 不覆盖 / 验收看内容不只看退出码 / 批量抽样）。

## 批量操作

- **[2026-05-08] 日历选择器月份导航最大迭代次数不够。**
  根因：历史日期可能跨多年，nav_to_month 的 max retries 不够。
  做法：至少 20 次迭代（覆盖 2 年范围），从当前月份计算差值，选择正确方向。

- **[2026-05-08] 批量脚本中第一次日期切换失败后，所有后续均失败。**
  根因：失败后的恢复逻辑不足，页面可能卡在中间状态。
  做法：每次切换失败后关闭并新开标签页，重置状态。

## 复盘流程

- **[2026-05-08] 周均线和偏离度临时获取失败，但之后某步补全了。**
  根因：market data 页面间歇性 JS 错误，部分时候能成功但也可能静默失败。
  做法：Step 3.5 必须验证返回值非空，空则重试或新开标签页重试，不能无声跳过。

- **[2026-05-11] verify_and_patch.py 只检查周均线/偏离度，行业聚散字段空缺被漏检。**
  根因：`PATCHABLE_FIELDS` 硬编码只有 `周均线` 和 `偏离度`，缺少 `前三占比`、`集中度`、`行业1-3`、`占比1-3`。
  做法：verify 脚本的 PATCHABLE_FIELDS 应覆盖所有关键业务字段；写入后人工抽查飞书表全字段，不能只信脚本报绿。

- **[2026-05-12] 飞书日期年份前缀写错（25-05-12 应为 26-05-12）。**
  根因：从页面看到 `05-12` 后直接拼了 `25-` 前缀，没有确认实际年份。
  做法：从页面日历/日期面板/URL 确认完整年份，用 `str(year)[-2:]` 截取前缀。不能假设年份等于当前年份——用户可能抓历史数据。

## 概念入库

- **[2026-05-24] YAML frontmatter 中 wikilink 和中文不加引号导致 Obsidian 渲染异常。**
  根因：`sources: [[研报名]]` 中的 `[[` 被 YAML 解析为数组嵌套语法，`tags: [中文tag]` 中的中文无引号也可能解析失败。frontmatter 解析失败后 Obsidian 回退渲染整个文件。
  做法：所有 YAML 字符串值统一用双引号包裹——`title: "中文标题"`、`tags: ["中文tag"]`、`sources: ["[[wikilink]]"]`。concept_writer.py 输出已自动处理，手动编辑时需注意。

## Skill 结构

- **[2026-05-11] up-line skill 只有 README.md 没有 SKILL.md，不会被自动发现。**
  根因：Claude Code skill 系统只识别 `SKILL.md`，`README.md` 不算。
  做法：每个 skill 目录必须有 `SKILL.md`（含 YAML frontmatter），README 可作为补充文档保留。

## fupanhui API

- **[2026-05-13] fupanhui.com 有内部 REST API，可替代页面 DOM 抓取。**
  发现：通过 `performance.getEntriesByType('resource')` 发现前端调用的 API 端点。用浏览器内 XHR 调用自动携带 session cookie，无需 API key。
  适用：limit-advance（已改造）、market-overview（待改造）、研报入库。
  关键端点：`/api/v1/client/reviews/market`、`/api/v1/client/limit/ladder`、`/api/v1/client/calendar/month`、`/api/v1/client/reports/list`。

- **[2026-05-13] fupanhui API 字段名不等于直觉猜测。**
  根因：latest-date API 返回 `latest_date` 非 `trade_date`；calendar API 返回 `trade_date` 非 `date`。
  做法：先用小数据量打印 API 响应的 keys，确认字段名后再写逻辑。

- **[2026-05-13] 均线上方家数占比不需要抓取。**
  根因：用户确认复盘流程中不需要此字段。
  做法：verify_and_patch.py 和复盘流程均跳过此字段。

## UP 线计算

- **[2026-05-20] IFIND_DIR 路径因 symlink 错误解析。**
  根因：`shared/` 在 5月12日变为指向 `~/.claude/shared` 的符号链接。`Path(__file__).resolve()` 跟随 symlink 后，`IFIND_DIR` 变成 `/Users/lbq/.claude/skills/ifind`（不存在），iFinD 调用静默失败。
  做法：去掉 `.resolve()`，用 `Path(__file__).parent` 即可。其他引用 `shared/` 的脚本也要检查是否有同样问题。

- **[2026-05-20] iFinD `get_stock_info` 不再返回 MA/STD 数据。**
  根因：iFinD MCP 服务端工具分配变更，MA/STD 等技术指标现在走 `get_stock_performance`。
  做法：`feishu_utils.py` 的 `ifind_query()` 已改为 `get_stock_performance`。其他 skill 如需技术指标数据，确认工具名是否匹配。

- **[2026-05-20] UP 线偏离度算错（26.91% vs 预期 32.5%）。**
  根因：MA 和 STD 分开查询，iFinD 返回不同日期的数据（MA 取 5/19、STD 取 5/20），`parse_md_table` 保留每个查询的最后出现值导致日期不一致。另外用户公式用 `H`（最高价），最终确认用户决定用收盘价。
  做法：MA+STD 合并为单次查询（`"XX的MA简单移动平均和STD标准差，周期26日"`），用 `_parse_combined()` 解析双列表格，确保同日期。用当天数据（非上一交易日）计算 UP。

- **[2026-05-20] 飞书日期前缀再次写错（05-19 应为 26-05-19）。**
  根因：与 5/12 同一 bug，复盘子 agent 写入时直接用了 API 返回的 `2026-05-19` 格式转 `05-19`，丢失了 `26-` 前缀。
  做法：复盘流程写入前必须统一转换 `YYYY-MM-DD` → `YY-MM-DD`，用 `str(year)[-2:]` 截取。写入前打印日期值确认。

- **[2026-05-20] 每日指标表格式不一致（"亿"后缀、缺失%和+号）。**
  根因：不同 session 写入时格式不统一——有的写了"亿"后缀，有的百分数字段漏了 `%`，正数缺 `+` 号。148 条记录中有 6 条格式异常。
  做法：写入每日指标时，所有百分比字段统一带 `%`，正数带 `+`，成交额和 20 日均不带"亿"。格式规范见 `market-overview/references/feishu_write.md`。

## 板块边际量

- **[2026-05-21] 电子表格插入列导致数据混乱，用户反馈不要移位。**
  根因：sector-data 写电子表格时，试图把新日期插入 B 列并把现有列右移，打乱了用户的列序。
  做法：始终写到最后一列（最右侧空列），列排序由用户手动完成，不要自动插入移位。

- **[2026-05-22] sector-data 条件格式公式引用用 `$A1` 不是 `$A2`。**
  根因：飞书电子表格条件格式中，即使应用范围从第 2 行开始，公式引用也从 `$A1` 开始。
  做法：条件格式公式统一用 `$A1` 引用板块名。

- **[2026-05-21] fupanhui sector-cycle kline API 偶尔返回 502 Bad Gateway。**
  根因：后端临时过载，同一请求稍后重试即可正常返回。
  做法：遇到 502 时 sleep 2s 重试（最多 3 次），通常第二次即可恢复。不要因此放弃改用 sectors/search 的 strength 字段（不是成交额）。

## 飞书 bot 召回（dream-loop 提炼）

> 以下条目由 dream-loop 推理半从 transcript digest 自动提炼，标注「待人工复核」者为候选。

- **[2026-06-17] 同一题材「液冷」当晚连续 6 次查询返回 `召回=FAIL`（图谱命中 0 概念 / 0 公司暴露），约一小时后同一查询无任何改动地变为 `召回=PASS`（图谱命中 5 概念 / 12 公司暴露）。** _(候选，待人工复核)_
  根因（从 transcript 推断，待人工确认）：FAIL 时不只是「当日盘面候选未命中」，连声称「仅基于知识图谱」的回退也返回 0 概念——说明此刻盘面/图谱索引尚未就绪（盘面=—）；待 2026-06-16 盘面候选就绪后（盘面=2026-06-16）召回立即恢复。即「数据/索引未加载」被对外呈现成了「题材无命中」。
  做法：① 对液冷这类已知有图谱覆盖的题材，若出现 `召回=FAIL 且 图谱命中 0`，应优先判为「盘面/索引未就绪」而非「题材无价值」，待当日盘面候选 ingest 完成后再重查；② bot 侧把「盘面候选未就绪 / 图谱索引为空」与「题材确无命中」区分为不同状态（如 `召回=NOT_READY` vs `FAIL`），避免把数据时效问题误报成无命中，误导判断。
  依据：`raw/transcripts/digest-2026-06-17.md` 22:18–22:58（液冷 FAIL×6）→ 23:08（液冷 PASS）；对照 23:28「光模块」为 `召回=WARN`（盘面在、题材未触发但图谱命中 6 概念 / 12 公司 / 证据 8 条），与液冷 FAIL 的 0 命中形成反差，进一步指向「索引未就绪」而非题材本身无内容。

## Agent 执行纪律 / 确定性脚本执行

> 适用：拿到含完整真值表/字段口径/writer 行为的 handoff 或 spec 后的 ingest、回填、批量入库类任务。与 `AGENTS.md`「Agent Token Discipline」红线一致。

- **[2026-06-19] 拿到确定性 handoff（已含完整路由真值表 + writer/校验逻辑 + log_id 处置）后，仍把 `entity_delta_writer.py`/`check_relations_integrity.py`/`knowledge_graph.py` 整文件重新通读一遍。**
  根因：把「确定性脚本执行」误判成「探索/理解项目」。handoff 已把所有路由规则、字段枚举、writer 行为、log_id 优先级写死，无需再读源码建立理解；但默认行为习惯性「先把基础设施读懂再动手」。
  做法：handoff/spec 已是确定性真值表时，直接按步执行；只有当某行字段判断或某条分支即将被用到时，才用一行 `rg`/`grep -n -A` 点查那一处，绝不预读整文件。能用 frontmatter/manifest/精确命中解决就不读正文。

- **[2026-06-19] 为「验证早已知道的状态」写了一堆临时探查脚本（`recon.py`…`recon9.py`、`probe_*.py`）。**
  根因：用「写脚本求证」代替「按 handoff 既定结论执行」，把 handoff 已给定的事实（next log_id、已建的 7 个实体、待补字段缺口）又用脚本重新跑一遍。
  做法：不写探查脚本验证 handoff 已给的结论。需确认单点事实时用一条 shell（`ls`/精确 `rg`/`python3 -c`），用完即弃，绝不在仓库/家目录留 `recon*/probe*` 垃圾文件。

- **[2026-06-19] 「先把所有东西读完再动手」，迟迟未入库，被用户两次点名「为什么处理那么慢 / 没按脚本执行」。**
  根因：把「理解」和「执行」串行化——先求 100% 读懂再开始第一步，而非边执行边按需点查。确定性任务下这是纯浪费、且拖慢首步交付。
  做法：确定性流程一律「立即执行 + 按需点查」。不依赖任何源码理解就能起步的步骤（如先建 source 页）先做掉；后续每步只在真正用到某机制时点查该机制那几行。首步交付优先于全局理解。
