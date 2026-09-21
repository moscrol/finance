## 这个分支做什么
离线修复研究清单丢失、非公司排序误触模板与公开E号错位；不重跑三题首答、不动8792。

## 决策与被否方案
- 复用MaterialContract.questions，不造第二套要求身份；送达不等于语义完成。
- 清单须研究引导+要求标题+连续编号；否决泛认编号材料，读取权限不放宽。
- 排名按子句剥离非公司目标，不全文借公司名单、不整句误杀混合排序。
- 完整账本定E号，过滤不重排；旧无ID不补造。内部hash不公开。
- 背景/被否方案详见 `docs/handoffs/2026-09-21-research-contract-citations.md`。

## 当前状态
代码/测试/复验脚本已提交 `8a892290d`，基线028a251a1，独立树 `~/fwp-wt-research-contract-citations-0921`。未push/合main/部署。日期快照与本交接单独归档，不改变代码身份。

## 未验证 / 已知边界
- explicit_requirements只保完整送达；公司集合/2+2+1、信号数量、正反/第三解释、分母和无来源阈值尚无逐项语义门。
- 无新模型调用、独立审查、全仓pytest、前端/E2E或跨仓registry结论；定向绿不代表可合入/上线。
- 生产adcda与本枝基线不同；8792和冻结首答未改，Knevo原答仍待用户提供。
- 旧Run未知maintenance_launch字段兼容、别名误缺数及金融推断问题未修。

## 下一步
先补逐项语义验收和零证据修复边界，再跑完整合入检查。真实模型/新样本另获授权；不得重跑原首答或自动写研究规则/视角/经验卡。

## 踩过的坑
不要全文件格式化大旧模块；AST对照须忽略TypeIgnore行号。API面板走现有_run_context，无需重复helper。AgentOutcome夹具须带usage和首个task事件。解释器用主树.venv-workbench。harness-reference有他人在途，本轮不改。

## 已验证
固定8a892290d干净树：1504P/4S，收据 `~/.finance-runtime/test-receipts/20260921T151228Z-8a892290.json`；4S是既有嵌套用例。全仓Ruff、diff检查及提交门禁通过。五组变异各1/3/2/1/1断言红，正常版前后29P，源码不变；脚本 `scripts/review_probes/check_research_contract_boundaries.py`。证据 `~/.finance-runtime/reviews/research-contract-citations-0921/fixed-8a892290d-mutations/`。定向进程拒socket.connect，未调用模型或生产API。
