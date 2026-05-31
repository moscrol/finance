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
