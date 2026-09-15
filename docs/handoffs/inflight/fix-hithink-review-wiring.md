# fix/hithink-review-wiring · 2026-09-15

## 这个分支做什么
同花顺四步接入 local 并跑，修成员采集语义，提供新池只读验算；尚未恢复生产日报链。

## 决策与被否方案
- 允许同花顺池；否了复制复盘会名单/入选集合，公式与样本分开验。
- 当前成员按真实上海接收日；否了历史 end-date 回标。批删除/插入/目录头同事务。
- 等权/指数涨幅显式选，缺口不换算法；今前额同名单计算，不暗混分母。
- 先只读预览；否了直写 VIEW/生产旁路。production_ready 恒 false。
- 完整背景/被否方案/收据：`docs/handoffs/2026-09-15-hithink-review-wiring-preview.md`。

## 当前状态
树 `/Users/a77/fwp-wt-hithink-review-wiring`；代码提交9621128a、dcee18f2，基线1fef3d27。未push/合并/部署；未登录复盘会、取真实行情或改生产库。独立QC仍待完成，作者反向测试不替代它。

## 未验证 / 已知边界
- 前端/E2E未跑，四叶门禁不齐。单仓CI注册表通过；同级KB的7处指纹漂移仍红，未重刷他仓登记。
- local仍skip-constituents；canonical个股/新池投影、日报/队列/矩阵/snapshot当次产物未验。
- 目录仅最新单一category，成员每日最新批；计数来自响应自身，不能证明供应商完整，更不能重建历史目录。
- 请求级审计、独立完整分母、目标日字段、单位/复权/窗口和正式涨幅分类政策未完成。
- 未继承local-plan-gate-alignment、generation-stage-code-root等他枝成果/收据。

## 下一步
1. 固定dcee18f2两片组合独立复核：日期/staging/失败后skip、日历依赖、批事务、显式口径、真只读与全池缺口。
2. 隔离库先补目录/成员请求完整性与版本审计，再通用canonical投影；新池通过SectorUniverseStore发布接口接入。
3. 字段口径、四叶门禁、真实产物验收齐全后再请求合并/部署授权；生产只走daily-full暂存校验＋原子换库。

## 踩过的坑
当前成员无历史参数；repair_hithink_stock_day是单日白名单，不是通用日更。历史补数读duckdb-backfill技能。不能拿异口径篮子资金补旧面板。地图query仍vault unavailable/层missing，别当完整检索。

## 已验证
干净dcee18f2：ruff通过，全仓9684P/79S/2X、exit0；收据20260915T053650Z-dcee18f2.json。第二片日期/事务/计数/指数兜底四类变异均见红；恢复63P、树干净。单仓registry五命令exit0。图谱审计exit0但包含在途/混合树，不是运行时绿灯。原件23份及SHA256在`docs/verification/2026-09-15-hithink-review-wiring-preview/`；第一片收据与反证另列长快照。
