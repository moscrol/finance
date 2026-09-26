# 同花顺研究观察值候选

## 这个分支做什么
`feat/hithink-research-data`：接入异动、热度、当前估值；诊断旧同步停更。

## 决策与被否方案
- 复用官方客户端、DuckDB、staging、finance_query；否第二写入链/Agent外呼。
- 历史恢复skip latest-only并留收据；否放宽日期门、伪造历史或自动扩热度回补。
- 按文件身份拒绝生产库，硬/软链接及身份读取异常均拒绝；独立副本可作staging，不防检查后并发替换。
- 热度是自然日样本，异动是供应商解读，估值是当前值；NULL不补零，行数/ok不代表字段完整。

## 当前状态
PR #810仍WIP/open；当前分支HEAD为候选tip，运行时代码与164b02e4相同。合main/部署/生产写入/live sync/付费审查暂停。

## 已验证
- 当前分支HEAD：定向相关测试250P/8S，Ruff及收据校验通过；收据在`~/.finance-runtime/hithink-independent-20260921-fNTsHb/targeted-final-<HEAD短SHA>/targeted-receipt.json`，每次文档提交后用同目录`run_targeted.py`重跑重绑，只认revision与HEAD相同、dirty=false的那份；不带SHA后缀的`targeted-final/`绑定的是36f76e76a，不要再引。
- 真实非空异动已验（09-21盘中，tip树CLI写隔离库`~/.finance-runtime/hithink-anomaly-sample-20260921T1020/`）：10:21异动191行与独立原始探针逐条一致；10:39第二轮4请求全ok（异动214/估值2/热度5+5）；三数据集经FinanceQuery读回并受采集日截止门控（默认limit 50，全榜要过滤或显式limit）。细节见`docs/data-sources/hithink-research-data.md`验证记录与该目录`receipt*.json`。不是盘后发布、不是独立审查。
- 新增断言覆盖异动文本/关键词/request_id证据链、NULL不转0且不生成observations、重采历史热度不回放旧版本；三次内存变异均被捕获。探针日志在`~/.finance-runtime/hithink-independent-20260921-fNTsHb/`，不是生产证据。
- `eebf4e895`收据是历史原件；旧固定`164b02e4`全量11964P/85S/2X、前端门禁及48份清单不移签到本提交。

## 未验证 / 已知边界
- 最近额度预检仍为100%、credits=0、ordinaryUsageAllowed=false；预计北京时间09-27 01:06恢复。零模型请求，Spec/Quality未执行。
- 自然Workbench回答、盘后staging发布、生产恢复未验。
- 盘中429：10:21估值起三端点HTTP 429 `Global request rate limit exceeded`（无Retry-After），约7–9分钟后恢复。`get_json`只重试`code==4001`，429立即中止整轮（第一轮valuation失败、热度未发出、exit 2）。18:30夜跑是否命中未验（02:05四请求曾全成功）。是否改客户端（429同4001退避、尊重Retry-After、耗尽仍fail closed）待用户决定；一改运行时代码，164b02e4全量收据即失效。
- 生产仍是旧同步根`finance-workspace-sync@6382c13b`、local且缺同花顺步骤；六表停09-08，旧exit0/配置声明不等于新源执行。
- 财务/基金/商品语义未扩展；候选tip发布前须重跑完整测试及前端门禁。

## 下一步
1. 用户决定429处置。若改客户端：先加两针（429→退避→成功；退避耗尽→失败且请求收据为failed），再重跑完整门，收据重新绑定新SHA。
2. 等额度恢复或获非付费环境，从固定树分别执行Spec/Quality，不读对方结论。
3. 合入/部署前，对候选tip重跑完整Python、前端、Ruff、注册/台账、收据校验及生产只读审计；当前仅定向收据。一次盘后（18:30后）隔离库全轮采样仍欠，用来验429是否波及夜跑时段。
4. 保持WIP/open；不得live sync、切生产根、重载launchd或删生产数据。

## 踩过的坑
- 旧任务exit0不证明同花顺步骤运行；生产停更根因已通过loaded环境、旧部署HEAD和计划源码只读核对。
- latest-only不可用于历史恢复；事实表是最后观察值，不是历史版本库。收据必须绑定实际运行SHA/终端输出；零执行、错误测试路径和超时原件不能洗绿。
- 地图query已ready但结构/叙事missing、vault unavailable，不作全仓架构断言。原失败见`docs/handoffs/2026-09-21-hithink-research-review.md`；本轮见`docs/handoffs/2026-09-21-hithink-offline-followup.md`。
