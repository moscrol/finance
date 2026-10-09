## 这个分支做什么
隔离修复复盘指纹、断板误判、D10/D4材料饥饿与阅读顺序；工程回归过，尚非发布批准。

## 决策与被否方案
| 选用 | 否决 / 理由 |
|---|---|
| 指纹绑定窗外比较归档；无效报价待核 | 只改文案/凭名单消失确认，不能证明同版或断板 |
| 完整D10推断+每事实来源最低席位，提纲/校验用送达子集 | 不抬12K/48KB、不截表或升事实；全集提纲会引用省略ID |
| 读数前移，读法折叠 | 不删除合同；前移不等于首屏/视觉通过 |
展开：[决策与证据](../2026-10-09-river-dashboard-evidence-fix.md)。

## 当前状态
树`~/fwp-wt-river-dashboard-fix-1009`。实现`b4062d55b927`基于main6c1d9f5d4+Dashboard028590984+联合5509ecef3；文档tip另计。未推送/合main/部署/写生产，新模型0。证据根`~/.finance-runtime/reviews/river-dashboard-fix-20261009/`，读REPORT.md及completion.json。预览18897和自建页已停，其他树未动。

## 已验证
干净实现全仓21703P/78S/2X/0F0E，收集21783；Ruff、收据full-scope/同SHA/依赖及基座校验过。前端25文件241P、lint/typecheck/build及静态一致性过；registry五项0。定向红→绿保留。Chrome局部交互：缺日固定、折叠、矩阵/导出一致、草稿恢复、无模型拒收且保留附件。

## 未验证 / 已知边界
联合实际接口替身11967字符：D10完整，D4三条只送一条+counter:1，15条省略明示；悬空提纲ID=0，不是全集覆盖。grounded既有D4 query_basis/strict_double_red通道未修；Episode owned不改。新金融全文0，旧GLM未过保留。
完整Playwright、移动/平板视觉、远端Actions未跑；1280×625读数顶y≈693，仍在首屏外。真实20日仅10日可读、24K卡片送9日，10-08缺daily-review。

## 下一步
先核HEAD/脏路径；补E2E/视觉及D4元数据合同，获授权再验真实模型首发与金融解释；归档覆盖另收口。推送/合main/配套部署待用户确认；文档tip不移签实现全量收据。

## 踩过的坑
Python用本树.venv-workbench；Node26测试加`NODE_OPTIONS=--no-experimental-webstorage`，勿删storage异常测试。12K字符/48KB字节/24K开场卡是不同预算。CDP局部抽查不是完整E2E；自然时钟协议测试本次过但截止日夹具未修。旧指纹须刷新。
