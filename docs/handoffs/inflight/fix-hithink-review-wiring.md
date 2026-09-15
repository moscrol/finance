# fix/hithink-review-wiring · 2026-09-15

## 这个分支做什么
同花顺local并跑、板块采集版本/只读验算、个股标准化预演；生产日报链尚未恢复。

## 决策与被否方案
- 允许换同花顺池，不复制复盘会集合；公式/单位/复权/窗口另验，缺口不暗换算法。
- 成员用真实上海接收时刻；指定capture只消费已验证行，不回标历史或回退最新表。
- 个股显式股票分母＋相邻计划交易日；否了最近有行日/旧canonical补值，防缺数被洗掉。
- 仅普通行情/纯现金除息；Decimal完整上下文固定半进舍入，非现金/缺前日/零成交不猜。
- 独立QC按用户指示走k3（pi/mirasim-kimi），不用codex额度；pi无OS沙箱→事前指纹+事后归因替代。

## 当前状态
作者树`/Users/a77/fwp-wt-hithink-review-wiring`。代码`40317d78`；交接归档`2ad19f35`；批次2证据（全量/变异/QC）已归档待提交。未push/合并/部署，未取真实行情或写生产库。四片作者验收+独立QC均完成，等用户裁决是否走合并。

## 已验证
- 40317d78定向277P + 全量9834P/79S/2X（干净2ad19f35，代码等同）+ 全仓Ruff，收据条件校验通过。
- 删保护变异12/12红（落盘核验、语义对应、还原后95P干净）。
- 前端lint/typecheck/build+Vitest76P；registry check-parseability 60/60、generate-views树干净。
- 独立QC（k3隔离树，本任务首份报告）：**无P0/P1/P2**，155探针+CLI/类型边界全过，QC自跑全量9836P/0F；零污染经作者对照事前指纹核验。证据 `docs/verification/2026-09-15-hithink-stock-preview/`（82文件SHA256全核验）。

## 未验证 / 已知边界
- Playwright E2E本片未跑（零前端改动；c85d0101的E2E结论不借用）。本机Node26/macOS≠CI Node22/Linux。
- 跨仓registry仍红：7处漂移全在kb侧（既存，非本片新增），finance侧零漂移。
- 真实供应商dump未碰；覆盖完整性/事件采集覆盖`unverified`；production_ready恒false；local仍skip-constituents，日报/队列/矩阵产物未验。
- QC两条P3未修：CLI失败路径fallback缺`contract_version`（sector-preview同pattern，宜两片一起补）；文档未写「休市表仅2026→仅支持2026目标日」。

## 下一步
1. 用户裁决合并：若合并，先在本机跑等价CI四叶+补QC两条P3；kb侧registry漂移在kb仓修，不在本仓绕。
2. 通用投影（行情/事件覆盖、独立分母、送转/配股/新股/停复牌、名称/换手率来源）再立新片。
3. 真实行情/补历史/产物验收另取授权；生产仍仅daily-full staging+原子换库。

## 踩过的坑
DDL按首分号截会撞注释分号（用DuckDB解析器）；localcontext继承traps须显式完整Context；地图build成功query仍stale不拿空图作结论；pi的`-p`全程缓冲输出、进度看产物目录不看stdout；收据glob按分钟段写死会漏窗口（`103[123]*`兜齐）。
