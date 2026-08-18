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

## [kb] 结构化文件的行级三方合并

- **[2026-08-14] entity YAML 修复 PR 与历史重号 PR 对同一页 CONFLICTING，不能按旧号全局替换。**
  根因：Git 三方合并按「行」比，不管 YAML 语义。一边把重复 `log:` 收成一块，一边在悬挂的第二块里改号，两边都改同一段。旧号本身在撞号（`#1647` 对应多个新号），全局替换会改错。
  做法：结构听语义修复（单键 YAML），号按 **log 文案** 对齐重号映射，不能按旧号→新号字典替换。详见 kb #338 接替 #328。

- **[2026-08-14] 解冲突时「哪边 YAML 合法就听哪边」，把上游 writer 的丢数据固化。**
  根因：#317 的 writer 重演了同一个整行覆写 bug，长光华芯 log 9→3、长电科技 25→2——main 侧 YAML **合法但不完整**。合法性是语法判据，完整性要比条目。
  做法：解冲突前对每页比一次条目数/条目集，main 是超集才可直接听 main，否则取并集（本线时序为基序，文案匹配的号听 main，新条目追加末尾）。

- **[2026-08-14] 自写的「零丢失」校验脚本三次给出假通过。**
  根因：①用 `git diff -- "$f"` 传 git 转义引号路径，两边都匹配不到文件、双双为空被判「相同」；②只用 `re.findall(r'"([^"]*)"')` 抓条目，漏掉不带引号的块序列项（`- raw/xxx.json`），误报丢失；③`re.match(r'^---\n(.*?)\n---\n')` 匹配不上就 `continue`，于是 4 个闭合分隔符畸形的页从两轮「0 失败」里溜掉。
  做法：路径一律 `git -c core.quotePath=false`；损坏侧用文本兜底解析、干净侧用真 YAML 解析；**「解析不了」必须单列为一类失败，不能 `continue`**——这三次假通过里有两次是「跳过被当成通过」。

- **[2026-08-14] 闸门报 0 错，可能是因为它跳过了坏数据。**
  kb 4 个 entity 页的 frontmatter 闭合 `---` 紧贴在末行行尾（`...]---`），仓内所有 `split_frontmatter` 都按「独占一行的 `---`」定位，定位不到就返回「无 frontmatter」，于是 sources/log/tickers 对入库与图谱全部隐形，而 `ingest check` 一路 0 错。
  做法：闸门的「通过」要能区分「检查过且合格」和「没检查」。凡是 parser 有 early-return/skip 分支的，都要单独统计 skip 数并纳入判定。

- **[2026-08-14] rebase 到已瘦身的 #317 时，`kb-relations-union` 把旧 `evidence_index` 近 5800 条复活。**
  根因：merge driver 按 append-only 假设，以 theirs 列表为骨架不删 base 已有条目。#317 合 main 后 items 25165→19437，#335 还带着旧胖索引；并集得到 25312，而本线真实增量只有 137。
  做法：对方分支有过删除时，不要用 union 骨架。以**当前目标分支为底**，只加「源分支相对共同祖先的增量」。详见 kb #339 接替 #335。

## [kb] log 撞号与图谱口径（对抗性审查）

- **[2026-08-13] 取号只看 log 标题，看不见页面预留号，IMA #3770–#3787 与 miracle 补档撞号。**
  根因：`max(log 标题)` 扫不到只写在 frontmatter/index 的预占号；多写者共用序列时，预占未落表是经典撞号源。
  做法：取号必须计入「页面预留号」；定号前 `git fetch` 扫全部远端。详见 kb #329 / `docs/handoffs/2026-08-13-log-collision-fix.md`。

- **[2026-08-13] CI 放行 token 扫 `HEAD` 全历史，被 main 祖先的 token 污染，之后每个 PR 都误跳过守卫。**
  根因：放行口扫的是整段历史，不是本 PR 独有提交。
  做法：CI 放行 token 只扫 `base..head`（PR 独有提交）。#330 无放行 token、走守卫正常路径才算守卫工作实证。

- **[2026-08-13] 把丢数据洗成口径：页面声称写了图谱，实际丢失，却补 `cascade: none`。**
  根因：`cascade: none` 只该用于设计上不写的批次；声称写了的必须真在。
  做法：设计上不写 → 才标 `cascade: none`；页面声称 graph_only 等已写的必须补数据，不能用声明掩盖丢失。

- **[2026-08-13] 往 curated 节点补弱来源时直接调 `update_entity_exposures`，会整体覆写既有节点。**
  根因：writer 对已有节点是整节点覆写，不是追加。
  做法：补弱来源走最小增量（只追加 `sources[]`），别直接调会整体覆写的 writer。#330 按 0616 同形状补 5 条即此法。

## [kb] 卖方研报 / entity-delta 入库

- **[2026-06-28] 验证 entity-delta/concept-delta 路由时用 `writer < payload.json | grep ...` 管道，导致 writer 被重复执行、内容重复追加。**
  根因：shell 管道会**完整执行**左侧的 writer（含写盘副作用），再把 stdout 喂给 grep；以为"只是看一眼"实际又跑了一遍。叠加先前已正常跑过一次，结果 entity 页「## 高信度研究线索」多段重复、source 索引「## 已更新实体」追加两次、新建卡（甬矽电子.md）被创建多次。
  做法：delta writer **只跑一次**，stdout 重定向到文件（`writer < payload.json > /tmp/out.json 2>&1`）；验证阶段**只读已写好的 entity/concept/source 文件与 relations**，绝不再调用 writer。误跑后用 `git checkout -- wiki/concepts wiki/entities wiki/relations` 回滚 + 手动截断 source 索引追加段，再干净重跑。

- **[2026-06-28] 同日两批卖研入库，第二批险些覆盖第一批产物。**
  根因：sources/synthesis/raw 文件名按日期命名，同日第二批会与第一批同名。
  做法：batch 隔离——第二批文件名加 `晚卖研汇2_`（raw/sources）/`-batch2`（synthesis）后缀；log 用独立 `#NNN` 条目；index.md 各处并列登记不覆盖。

- **[2026-06-28] 内置 git_create_pr 对 linxiaoqi5111-del 仓返回 404 Not Found。**
  根因：内置 git 工具走会话默认账号（noah-smith439374），无该私有仓权限。
  做法：PR 用 `GITHUB_PAT_LINXIAOQI5111` 走 GitHub REST API（`POST /repos/.../pulls`）创建。

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
- [kb] 2026-08-13 用脚本往 markdown 固定小节追加一行时，三元表达式拼接漏了尾段（text[:nl]+line 忘接 text[nl:]），把「交接记录」23 条历史全删 → 根因：就地字符串手术无断言保护，diff 也没看就 commit → 正确做法：①逐行遍历插入而非切片拼接；②写后断言旧内容探针仍在（>=3 个随机旧条目）；③commit 前必看 diff --stat，插入型改动出现 deletions 即中止。push 被拒反而救了一命——远端保护是最后防线，不是第一道。
- [kb] [2026-07-02] 年报披露日锚点抽取 4/20 落空 → 部分年报无内控披露/审计报告日锚点段落 → 兜底顺位加「财务报表业经公司董事会于X年X月X日批准报出/董事会批准报送日期」；另注意「资产负债表日后事项」中的日期会造成误抽（三峡能源 2026-01-19 误判），抽取后需 sanity check 日期是否落在 3-6 月披露季。

## Agent Runtime / 预算诊断（2026-08-08）

- **[2026-08-08] 按 handoff 的诊断（"档位表按更快的 provider 标定，重标定它"）准备动手，差一步就改错了地方。**
  根因：诊断只看了 `ResearchPolicy` 档位表（quick 30 / standard 90 / deep 240），没算实际生效值。真实链路是
  `effective_timeout = min(tier_total, turn − verification_reserve) = min(tier_total, 80)`——`80` 恒为较小者，
  **档位表根本不参与首轮**。探针实测：standard 从 90 调到 180、300，首轮预算恒为 26.67s，一秒不变。
  真正的绞索在 `episode_factory.py:360` 的 `reserve = min(60, 80 × 2/3) = 53.33`，于是首轮 `min(75, 80−53.33) = 26.67s`，
  而该 provider P50=28s——**首轮预算连中位数都不到**。
  做法：改预算前先用真实常量算一遍生效值，并与观测值对账。**数字对不上任何一条预算边界（28s ≠ 25 ≠ 70 ≠ 75）就是归因错层的信号**，
  此时应停下读盘上真实 run（`continuous-episode.json` 的 `events[].payload`），而不是继续调那个看起来最像的旋钮。
  前两次修（换模型、加回合预算 120→300）都失败，因为都假定了"档位太小"。

- **[2026-08-08] 在 `ResearchDeadline` 上加新方法 `opening_stage_timeout()`，三条护栏测试立刻 `AttributeError`。**
  根因：`context.deadline` 是**鸭子类型注入点**，测试替身（`_ScriptedDeadline` / `_LateRecoveryDeadline`）只实现
  `stage_timeout` / `synthesis_timeout` / `remaining` / `expired` 四个方法。给真实类加方法，替身全炸。
  做法：改这类注入点的行为时，只用替身已有的接口；需要读可选字段走 `getattr(obj, name, default)`。
  本次最终实现放在调用方（`agent_episode._opening_planning_timeout`），一个新方法都没往 `ResearchDeadline` 上加。
  另一半教训：那条 `test_planning_turn_cannot_spend_the_reserved_finalization_budget` 断言 `calls[0]["timeout"] <= 11.0`，
  正是被改掉的语义——**没有改测试去迁就实现**，而是把"整段不扣 reserve"收窄成"只借超出合成地板（20s）的余量"，
  于是生产 26.67→60s（≥P95 50s），而该测试（reserve=4，借不到）与四种其他配置一秒未变。

- **[2026-08-08] 提交代码后读 `/api/health`，`code_matches_repo` 仍报 `True`，据此以为快照已含改动。**
  根因：`runtime_provenance.py:113-115` docstring 明写指纹 *"called once per process (`create_app`) and the result is
  reused by every health response"*——**启动时算一次，之后所有 health 复用**。仓库前进了，读数不会变。
  讽刺的是同文件 :100-111 正是在讲"版本号会在最可能出错的时刻前进"这个 bug 类，缓存让它换了个形式重现。
  做法：判断快照新旧只能靠 `scripts/deploy_workbench_runtime.sh` 里那次**现算**（它 `cd` 到快照再算，并先断言
  "加载树必须在快照内"），或直接比对两棵树的文件 hash。**长驻进程的自述字段一律视为启动时快照，不是当前状态。**

- **[2026-08-11] `check_inflight_stale.sh` 报「交接过期」，证据是 3 个 moneyflow 脏文件——而本分支 8 个提交一次都没碰过它们。**
  根因：判据是「代码路径前缀 + mtime 比文档新」，即**拿文件系统事实推断版本控制事实**。未提交改动在 git 里
  **没有分支归属**，它只属于这棵树；本仓主检出树常年多 agent 共用，这类误报是必然而非偶然。
  更隐蔽的是它这次**结论恰好是对的**（交接确实过期，因为分支在文档之后又提交了 2 次），只是理由完全不相干——
  巧合是那批脏文件的 mtime 比真正的最后一次提交只晚 2 秒。**"报警响了且事实成立" 不等于 "判据成立"，
  验证门禁必须查它引用的证据，不能只看结论对不对。**
  做法：改成两级判据——一级用 `<base>..HEAD` 的提交时间（提交自带分支归属，共树污染不进来）；
  二级把脏文件与 `git diff --name-only <base>...HEAD` 求交集后再比 mtime。基线解析不了时退回宽判据但
  **在告警里声明「本次未做归属过滤」**。误报的代价不是烦人而是失效：喊过狼来了的门禁，下次没人看。

- **[2026-08-11] 用 `grep '^## ' file | sort | uniq -c` 数交接文档的小节，6 个不同的中文小节被合并成 1 个、计数报 5。**
  根因：macOS 的 BSD `sort`/`uniq` 在 **UTF-8 locale 下按 collation 比较**，CJK 表意文字主权重相同 →
  **不同的中文行被判为相等**。`LC_ALL=C`（按字节比）才正确；`LC_ALL=en_US.UTF-8` 与不设一样错。
  做法：**任何对中文文本的 `sort`/`uniq`/去重统计一律加 `LC_ALL=C`**。这条可迁移到所有 macOS 上的中文日志/清单统计。
  元教训：当聚合结果与直接 `grep -n` 的原始行对不上时，先怀疑量具而不是数据——本轮正是靠"两个读数打架"才发现的。

- **[2026-08-11] 给注入脚本加了按小节重排的 awk，一份「没有任何 `## ` 小节」的文档注入结果为空，退出码 0、无报错。**
  根因：awk 用**未初始化变量**做数组下标时，下标是空串 `""` 而不是数字 `0`。首个 `## ` 之前的正文写进 `body[""]`，
  END 里 `for (i=0; ...)` 读的是 `body["0"]`——两个不同的格子。真实文档因此也悄悄丢了标题行和「更新：日期」行。
  做法：`BEGIN { sec = 0 }` 显式初始化。凡是「累加到 arr[var] 再按数字下标遍历」的 awk，都要先给 var 赋数字初值。
  这个坑的形状与本文件已记的另外三条一致：**失败方式是静默出空而非报错**，只有构造边界样本才能抓到。

- **[2026-08-11] 给 stale 门禁加了「本分支提交晚于交接文档就报警」的一级判据，写完交接、提交，门禁当场又报警——死循环。**
  根因：**提交交接文档这个动作本身产生了一个比文档 mtime 更新的提交**（`git commit` 不改文件 mtime）。
  于是「写交接」永远无法让门禁满意，写了也没用。这是本文件已记的「活文档先写未提交再提交 → 提交动作让文档
  当场失效」在门禁侧的重现——同一个形状，换了个位置。
  做法：一级判据用 `git log ... -- ':(exclude)<交接文档路径>'` **排除只动交接文档的提交**（那是交接行为本身，
  不是新干的活）；文档时间取 `max(工作区 mtime, 最后一次改动它的提交时间)`，让「文档与代码写在同一提交里」
  也成立。**可迁移原则：任何「产物必须跟上源」的门禁，都要把「更新产物」这个动作本身排除在「源变动」之外，
  否则门禁自噬。** 同类：lint 自动修复触发 lint、changelog 门禁、格式化 hook。
  抓到它靠的是**闭环验证**——修完不是跑一遍通过就完事，而是把门禁放回它本该静默的真实状态里再跑一次。

- **[2026-08-11] 对比分支与 main 的测试失败集合，`diff` 报「完全一致，零回归」——两个文件其实都是空的。**
  根因：把文件列表放进变量再 `$FILES` 传给 pytest，词分割没发生，整串被当成一个路径，pytest 报
  `no tests ran`（退出码 4）。`grep '^FAILED'` 于是两侧都抓到 0 行，`diff` 自然「一致」。
  **空对空的差分永远通过，且和真正的「一致」长得一模一样。**
  做法：任何 A/B 差分**先断言两侧非空**再比内容（`[ $(wc -l < a) -gt 0 ]`），并把「两侧各 N 条」
  打进结论里。同类形状：grep 管道对账、集合比对、快照 diff——**只报「无差异」而不报「比了多少条」的
  对账结果不可采信**。这条与本文件已记的「量具被自己污染的输出骗了」同族。

- **[2026-08-11] 验证「改了代码门禁会不会重新报警」时用 `touch file`，门禁静默，差点判成「门禁被修哑了」的回归。**
  根因：`touch` 只改 mtime，**不产生 git 改动**，而门禁的二级判据读的是 `git status --porcelain`。
  测试动作和被测判据读的不是同一个量——测试本身无效，不是被测物有问题。
  做法：构造反例时先确认「这个动作真的会被判据看见」（这里应当真改文件内容，改完 `git checkout --` 还原）。
  推广：**用 mtime 造脏、用 touch 模拟改动、用 sleep 模拟并发**，都属于「造的假象不在判据的观测面上」。

- **[2026-08-11] 15 条「常年失败」的测试里，11 条的根因是测试直连了真人数据——而且在**写**。**
  根因：本机为跨机同步真实设了 `FORESIGHT_USERS_DIR`（指向云同步 vault）、`FORESIGHT_USER`（真人 id）、
  `SUBCONSCIOUS_VAULT=...`，而 `userspace.users_dir()` / `resolve_user_id()` 是**运行时**读 env 的（这是对的，
  跨机同步就靠它）。不显式指定用户的测试于是落到真人目录：断言 `len(buf)==1` 实际读到 **913** 条真实会话缓冲；
  断言 judgments 文件不存在实际为 True。**更糟的是写**：实测 测试用的 `tester/`、`alice/` 两个用户目录 被测试创建，
  真人目录 mtime 被改动，而那是个云同步 vault——测试垃圾会同步到另一台机器。
  做法：conftest 加 autouse 夹具默认 `delenv` 这三个变量，让「密封」成为默认；需要的测试自己 `monkeypatch.setenv`
  设回来（`test_workbench_api.py` 20 多处早就是这个正确写法）。实测 15→0 失败，且全量跑完真实目录**指纹零变化**。
  **元教训：长期红着的测试套件不是「知道有几个坏的」，是掩体。** 这 11 条数据污染之所以活了很久，
  正因为它们混在「反正一直有 15 个红的」里没人分辨。红的数量必须归零或全部转成带理由的 skip，
  否则新出现的真回归会被同一片红淹掉。

- **[2026-08-11] `pytest.approx(30.0)` 断言一个从活时钟算出来的值，单独跑 5/5 失败、全量跑反而过。**
  根因：`pytest.approx` 默认是**相对**容差 `rel=1e-6`——对 30.0 就是 ±3e-5。而该值来自
  `ResearchDeadline.from_timeout(60)` 的实时预算，真实流逝的几十微秒会被减掉（实测 29.99995141645195，差 4.9e-5）。
  于是**机器忙闲决定红绿**：全量跑时时序恰好落进容差，单独跑就必红。测试注释明写「断言规则不是数字」，
  但默认相对容差把它悄悄变回了断言精确值。
  做法：对时钟/IO 派生的量用**绝对容差** `pytest.approx(x, abs=0.05)`，宽度按「真回归会挪多少」定
  （这里真回归是 15 vs 30 秒级，50ms 足够紧）。改后 10/10 通过，人为压满 CPU 也通过。

- **[2026-08-11] 测试 `monkeypatch.setattr(acceptance, "latest_run", ...)` 完全没生效，因为 cmd_board 早就不调它了。**
  根因：生产码重构成 `select_latest_case_runs(RUNS_DIR, ...)`（直接扫目录），**mock 点随之失效成了空操作**，
  测试于是读真实的 runs 目录——目录里运行记录从 1 份长到 20 份，断言随之漂移。
  失败信息看起来像「看板渲染坏了」，实际是测试没钉住输入。
  做法：mock 点要跟着实现走；更稳的是**走公开接口传参**（这里 `Namespace(run=...)`）而不是打补丁内部函数。
  同批还改了一条过度具体的断言：钉死整行表头 `| 题 | 组 | 运行 | 真值 | 体验 |`，板子加了七列就红，
  而它真正要守的不变量（三轴各自独立成列）完好无损。**过度具体的断言会在无关变更上报警，把真回归淹掉。**

- **[2026-08-12] 按 `git status --porcelain` 判「工作区干净」筛出 12 棵可删的 worktree，逐项复核时 7 棵被拦下。**
  根因：`git status` 的「干净」是**相对 gitignore 而言的干净**，不带 `--ignored` 时看不见被忽略的文件。
  那 7 棵各有 1~7 个忽略项（`__pycache__`、`.pytest_cache`、`.DS_Store`，以及最要紧的
  `.ingest-transactions/` ——ingest 的回滚备份，160 个里 113 个的内容在 git 对象库里根本不存在，
  是唯一副本）。若信了第一次快照直接 `git worktree remove`，这些会随目录一起消失且不可恢复。
  做法：**凡是要删目录的判据（worktree / 临时检出 / 容器卷），必须用 `git status --porcelain --ignored`**；
  判「要不要提交」才用默认。两个问题问的不是同一件事。
  **可迁移原则：判据的作用域必须匹配动作的作用域。** 删除动作影响整个目录，判据却只覆盖 git 跟踪面
  ——差一档就漏。这与 `10_knowledge/gate-assertion-granularity.md` 是同一个形状。
  另一半：**不要信几分钟前的快照**。本次是在执行循环里对每一棵重新跑三条件（已并入 / 脏 0 / 忽略 0）
  才抓到的；如果沿用先前算好的清单，复核这一步根本不会发生。

- **[2026-08-12] 「留还是删」常常是伪二选一——先把可恢复部分和唯一部分拆开量。**
  场景：3 棵已合并 worktree 共 3.3 GB，里面既有能从 git 完整恢复的检出（1.84 GB），
  也有不在 git 里的事务备份（1.49 GB）。直接删会丢唯一数据，全留则浪费。
  做法：**归档唯一部分 + 删可恢复部分**。那批备份是同几个 relation JSON 的连续快照，
  相似度极高，`tar.gz` 压到 216 MB（7 倍），于是 3.3 GB → 216 MB，一份唯一数据都没丢。
  两条配套纪律：归档后**逐文件比对内容哈希**再删源（只对文件数会漏内容损坏）；
  归档目录里放一份 README 写清「这是什么 / 为什么留 / 什么时候可以删」，
  否则三个月后它自己就变成新的谜团。

## [kb] 晨汇批量回填（2026-08-18，PR #25）

- **[2026-08-18] 长文批量生成时，U+FFFD（替换字符）是「自产」缺陷——写完必须立即扫，不能靠小心。**
  场景：回填 15 天晨汇，source/briefing 共 30 页，其中 8 页被我自己的生成过程引入
  转码残留（"不可修改"写成"不可<U+FFFD><U+FFFD>"、"协议"写成"<U+FFFD><U+FFFD>议"，单页最多 7 个）。
  根因：不是原料损坏，是**生成端**在长输出里偶发产出坏字符；写作者「更小心」无法根除，
  且肉眼 review 中文长文极易漏过。
  做法：**写完即扫，扫完即修，修完复审**——`grep -c $'\ufffd' <file>`（或 Python
  `t.count('\ufffd')`）作为每次 write 的固定后验步；批量场景下用一段脚本对整批
  `briefings/ + sources/` 汇总输出，任何一页非零就停。这次 15 天全绿靠的就是
  「每写一天验一天 + 收尾全批再扫一遍」双层闸门。
  **可迁移原则：凡是「上游可能自产垃圾字符」的生成管线（LLM 转写 / PDF 抽取 /
  编码转换），U+FFFD 扫描是必配的廉价后验，成本一行 grep，漏过的代价是污染知识库。**

- **[2026-08-18] matcher 命中 ≠ 库内有页——wikilink 的判据是「文件存在」，不是「概念被索引」。**
  场景：晨汇 matcher 的 concept_hits 里有 `AIDC`、`黄金珠宝`，据此写 `[[AIDC]]`
  生成坏链；实际 `wiki/` 下并没有同名 `.md`（概念在 relations JSON 里、但从未建页）。
  根因：matcher 对照的是关系底层数据（concept_graph 等），wikilink 解析对照的是
  页面文件系统——**两个真本源不同**，中间没有保证一致的约束。
  做法：链接候选先跑存在性校验（`Path(wiki).rglob(name + '.md')`）再写入；
  已写的批次用脚本全量重扫 missing 链接，发现即改为纯文本或换成已验证存在的页面。
  同批另一坑：matcher 的 `concept_hits` 是 **list 不是 dict**，解析脚本按 `.keys()`
  取值会直接崩——读外部 JSON 先看结构再取数。
  **可迁移原则：任何「A 系统的输出」要喂给「B 系统消费」时，以 B 的解析规则为准做校验；
  A 的命中只说明 A 认识它，不代表 B 能解析它。**

