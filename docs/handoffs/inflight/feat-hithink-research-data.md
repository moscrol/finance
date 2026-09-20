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
- 当前分支HEAD：定向相关测试250P/8S，Ruff及收据校验通过；最终收据放在`~/.finance-runtime/hithink-independent-20260921-fNTsHb/targeted-final/targeted-receipt.json`，须与HEAD同SHA校验。
- 新增断言覆盖异动文本/关键词/request_id证据链、NULL不转0且不生成observations、重采历史热度不回放旧版本；三次内存变异均被捕获。探针日志在`~/.finance-runtime/hithink-independent-20260921-fNTsHb/`，不是生产证据。
- `eebf4e895`收据是历史原件；旧固定`164b02e4`全量11964P/85S/2X、前端门禁及48份清单不移签到本提交。

## 未验证 / 已知边界
- 最近额度预检仍为100%、credits=0、ordinaryUsageAllowed=false；预计北京时间09-27 01:06恢复。零模型请求，Spec/Quality未执行。
- 真实非空异动、自然Workbench回答、盘后staging发布、生产恢复未验；样本异动为空，测试正文合成。
- 生产仍是旧同步根`finance-workspace-sync@6382c13b`、local且缺同花顺步骤；六表停09-08，旧exit0/配置声明不等于新源执行。
- 财务/基金/商品语义未扩展；候选tip发布前须重跑完整测试及前端门禁。

## 下一步
1. 等额度恢复或获非付费环境，从`164b02e4`固定树分别执行Spec/Quality，不读对方结论。
2. 合入/部署前，对候选tip重跑完整Python、前端、Ruff、注册/台账、收据校验及生产只读审计；当前仅定向收据。
3. 保持WIP/open；不得live sync、切生产根、重载launchd或删生产数据。

## 踩过的坑
- 旧任务exit0不证明同花顺步骤运行；生产停更根因已通过loaded环境、旧部署HEAD和计划源码只读核对。
- latest-only不可用于历史恢复；事实表是最后观察值，不是历史版本库。收据必须绑定实际运行SHA/终端输出；零执行、错误测试路径和超时原件不能洗绿。
- 地图query已ready但结构/叙事missing、vault unavailable，不作全仓架构断言。原失败见`docs/handoffs/2026-09-21-hithink-research-review.md`；本轮见`docs/handoffs/2026-09-21-hithink-offline-followup.md`。
