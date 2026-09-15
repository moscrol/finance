# fix/hithink-review-wiring · 2026-09-15

## 这个分支做什么
同花顺local并跑＋新池只读验算＋目录/成员请求版本；尚未恢复生产日报链。

## 决策与被否方案
- 允许同花顺池；不复制复盘会集合，公式与样本分开验，缺口不暗换算法。
- 当前成员用真实上海接收时刻；否了历史end-date回标、跨日硬拼名单。
- 先落请求分母；limit也留缺口。版本读只消费已验证行，否了失败后回退最新表。
- 请求完成≠供应商全集≠发布；白名单/指纹不冒充外部签名，production_ready恒false。
- 背景/被否方案/证据：`docs/handoffs/2026-09-15-hithink-sector-capture-audit.md`；前两片另见同日preview快照。

## 当前状态
作者树`/Users/a77/fwp-wt-hithink-review-wiring`；代码9621128a/dcee18f2/c85d0101，基线1fef3d27。第三片已提交、作者验证已归档；归档只改文档/证据，不把其SHA称作新全量。未push/合并/部署，未取行情key/真实行情或改生产库。

## 未验证 / 已知边界
- 独立QC未完成：前两片Codex额度/Claude503，本片新Codex也额度失败，无审查报告。作者变异不代签。
- 跨仓registry仍KB七指纹漂移；单仓五命令绿不覆盖它。前端/E2E本机Node26；工作流Node22/Linux同环境未复现，不称merge-ready。
- local仍skip-constituents，仅catalog-only；未接通canonical日更/新池投影，日报/队列/矩阵/snapshot当次产物未验。
- provider_completeness=unverified；只冻结名单不冻结行情，不审K线覆盖/逐HTTP重试。失败staging丢弃后审计不保永久。
- 未继承local-plan-gate-alignment、generation-stage-code-root等他枝代码/收据。

## 下一步
1. 固定c85d0101续独立复核；任务在`~/.finance-runtime/reviews/hithink-c85d0101-qc-20260915/request.md`，不自动无限重试。
2. 处理跨仓登记与环境差异；再明确单位/复权/窗口/涨幅分类和目标日关键字段，做通用canonical投影，经SectorUniverseStore发布接口。
3. 真实数据/历史补数/产物验收另取授权；合并部署须用户确认，生产只走daily-full暂存＋原子换库。

## 踩过的坑
旧每日表仍最新单category；仅显式capture-id有多标签版本语义。repair_hithink_stock_day是单日白名单非通用日更。禁异口径资金补旧面板。地图仍vault unavailable/structure missing。

## 已验证
干净c85d0101：Ruff过，全仓9739P/79S/2X、exit0；收据072124Z。六类作者变异均exit1，恢复141P/exit0、树干净（080851Z）。前端lint/typecheck/build过、76P，浏览器三视口15P。收据校验通过。证据与SHA256在`docs/verification/2026-09-15-hithink-sector-capture-audit/`；图谱audit过但含他仓混合树，不是运行绿灯。
