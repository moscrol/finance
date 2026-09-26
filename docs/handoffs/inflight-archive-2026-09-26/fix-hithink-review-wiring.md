# fix/hithink-review-wiring · 2026-09-15

## 这个分支做什么
同花顺local并跑、板块采集版本/只读验算、个股标准化预演；生产日报链尚未恢复。

## 决策与被否方案
- 允许换同花顺池，不复制复盘会集合；公式/单位/复权/窗口另验，缺口不暗换算法。
- 个股显式股票分母＋相邻计划交易日；否了最近有行日/旧canonical补值，防缺数被洗掉。
- 仅普通行情/纯现金除息；Decimal完整上下文固定半进舍入，非现金/缺前日/零成交不猜。
- 独立QC按用户指示走k3（pi/mirasim-kimi），不用codex；pi无OS沙箱→事前指纹+事后归因。
- P3修复：失败fallback带contract_version但**不带**范围/输入指纹——失败时范围未验证、输入未读到，补指纹=伪造「验证过」；否了「成功失败字段全对齐」。sector片借机新增`hithink-sector-preview-v1`（原先连成功报告都无版本）。

## 当前状态
作者树`/Users/a77/fwp-wt-hithink-review-wiring`。代码`728ecf82`（QC两条P3+观察项2已修）、归档`cee4d9f2`。**已push gitea，未合并/部署**，未取真实行情或写生产库。四片作者验收+k3独立QC（无P0/P1/P2）+P3修复闭环全部完成，只等用户裁决合并。

## 已验证
- 728ecf82干净树全量9834P/79S/2X exit0（698s，与2ad19f35基线计数一致=零回归）+全仓Ruff；收据七项条件「可采信」。
- P3修复3/3删保护变异见红（stock/sector CLI fallback、sector成功报告各删contract_version，红的是语义对应测试）；QC复现命令字面重放现输出契约版本，exit2且不建库。
- 批次2遗产：12/12变异红、前端四叶绿（Vitest76P）、k3 QC 155探针全过。证据`docs/verification/2026-09-15-hithink-stock-preview/`（100文件SHA256全核验）。

## 未验证 / 已知边界
- Playwright E2E未跑（零前端改动）；本机Node26/macOS≠CI Node22/Linux。
- 跨仓registry红：7处漂移全在kb侧（既存非本片新增），在kb仓修，不在本仓绕。
- 真实供应商dump未碰；覆盖完整性`unverified`；production_ready恒false；local仍skip-constituents；日历仅登记2026（已写进文档，扩年先补休市表）。
- QC两条观察项之一（全零事件行标cash_dividend_reference）未改：无数值后果，属供应商数据洁癖。

## 下一步
1. 用户确认后合并gitea/main（等价CI已在本树跑过：全量+Ruff绿；前端四叶批次2绿）。
2. 通用投影（行情/事件覆盖、独立分母、送转/配股/新股/停复牌、名称/换手率来源）再立新片。

## 踩过的坑
- 收据目录混着并发会话的revision（50b44a0e等），按revision挑自己的，别信latest.json。
- pytest传了不存在的测试文件名→整次collection中止「no tests ran」，那份0/0收据不作证据。
