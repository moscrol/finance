# Runtime evidence 完整日期表达返修 · 2026-09-20

基线 `56d6062e4544ae40d2e91c19968f4bfe8066e60c`；仅代码提交 `11216c81585188c7f2986622f6b84ac567538b44`，改 `episode_evidence.py` 与现有日期测试参数。原代码/交接与348P、六变异证据保持，不移签最新提交。新证据独立在 `~/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-fix/dates-repair/`。

## 原因与修复

独立Spec给出三种合法完整表达：`2026-7-25`、`2026-7-25 09:30:00`、` 2026-07-25 `。registry判作future_of_cutoff，但快照直接调用fromisoformat而拒绝；原探针复制后在56d复现两模式共6F，标准ISO/紧凑日期/带时区时间共6格控制正常。

采用完整日历表达的形状检查，去外围空白、补齐月日，再严格date/datetime解析整个值。规范化仅用于future资格判断，不改快照原source_date。仍保留cutoff存在、日期确实晚于cutoff及首写原件全字段一致守卫。

否定直接复用parse_source_date：上游此函数会在正文、路径及日期前缀后接垃圾中搜索合法日期，无法用作未入账展示的完整表达准入。Python fromisoformat还支持上游不识别的week-date，本轮显式拒绝这种额外资格。Timer、v1/v2结构、账本写入、授权与生产停止行为未改。

## 本轮证据

- 未改原probe_date_forms.py分别复制到red/green；12格从6F/6控制变为12格都model_calls=2、model_finish，没有storage_failed。原Spec证据未覆盖。
- 最小相关模块 `test_episode_evidence_presentations.py` 63P，Ruff通过；含原文精确保留、恢复不得进覆盖、无cutoff/未知当前原件拒绝、完整字段与v1/v2相邻守卫。
- 单个撤保护：移除完整表达规范化/形状约束，定向6F/24P；还原30P。日志与脚本见mutation.json。不重跑原348或旧六变异矩阵。
- 最终固定SHA、clean状态与最小测试原日志绑定于本轮manifest.json；顶层旧manifest仍只签56d。

下一步由协调者安排Spec按原日期矩阵复验，再做Quality。未创建PR、合main、部署、真实模型调用或外呼；driver、跨进程恢复与自然金融质量边界仍按原交接，未新增完成声明。
