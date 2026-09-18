# A 股研究数据链候选 · 2026-09-18

## 这个分支做什么
复用既有行情/财报/估值/公告/资金链，修空错混淆与Episode证据消费，不造事实写链。

## 当前状态
树 `~/fwp-wt-research-data-readiness`；业务a93b→a9a7→**d77383ac**已提交；量具另`778679b3`。工程通过，**整体回答质量未过**；未push/PR/合main/部署。8907七run终态，PID33891已停；8792未动。
正文：`docs/handoffs/2026-09-18-research-data-readiness.md`；manifest：`docs/verification/2026-09-18-research-data-readiness/manifest.json`。
原件：`~/.finance-runtime/research-data-readiness-20260918/`（OUT）。

## 决策与被否方案
- 旧ask/Episode共用capital_bundle；否第二取数链，状态/截止/预算只有一份。
- 历史解禁无披露时点即留缺口；否当前日程回填历史。
- 固定枚举公开缺口，否抄异常/草稿；标签避菜单分隔符，不放宽过滤。
- 财报同批真行+指标词典，否表头占额度/模型猜列；保留报告期、限定语、哈希链。

## 未验证 / 已知边界
- 公告源仍cninfo403/互动易字段错。a93b真实`run_20260918_121115_094979`进度诚实，但成功终稿仍把不完整查询推成“无新增官方信息差”：未通过。
- a9a7财报`run_20260918_124033_015953`四次脚本错后产物exit0，JSON比率1.588却答1.587；嵌套summary被渲染器忽略、表格为空。文件存在不等于可用产物；模型抄数字而非读series。
- a9a7 ISO历史run `run_20260918_123911_710065`原因正确，不外呼滚动解禁；仍夹带“大概率无重大解禁”弱先验，非严格核事实通过。
- 最终d773只补报告期名，未新跑模型会话；无真人视觉/独立QC/全股覆盖/稳定日更结论。
- 相对历史题路由多余研究未修。08-12已定位为event_daily筛选子集日期，非读错根；股票仍09-17，笼统过期提示未改。

## 下一步
1. 对齐并行`fix/8792-financial-contracts-r5@dfd7b4ff`后修计算交付；只读量具`scripts/review_probes/inspect_calculation_delivery.py`，不重取原件。
2. 公告成功答卷也约束负面推断，保留部分可信结果；不因单源故障删整答。
3. 再固定版本复验真实题集/独立检查，用户确认后才合并与上线。

## 已验证
d773 clean全量**11522P/83S/2x**，Ruff/前端lint/typecheck/build全过，组件107P、E2E34P/2S、registry四项+crosswalk绿。收据`20260918T072734Z-d77383ac.json`；OUT/candidate-d77383ac/result.json。
撤保护5F/1F/1F，正常115P。最终真财报12行、6期现金流进沙箱，六比率独立复算一致；served08-15非抓取日。量具另6P，不累加。

## 踩过的坑
主树.venv-workbench；净环境/umask022。旧调用溯源偶发红根因未定，后续未重现。a9a7全量4F保留，恢复期名才全绿。日历子集/表/全库日期分开；取到/可算/展示/答对分开。
