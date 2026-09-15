# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；只动fwp-wt-e2-boundary-closeout，主树不动。

## 决策与被否方案
- P3h两道正交防线共用一个谓词：adapter对约束轮不让确定性owner路（留Episode收窄执行）+orchestrator掉落总闸（mode=off是env缺省，兜所有掉落）；否只修一侧（另一口仍裸）、否给引擎B内部加合同意识（工程量数倍，legacy面，列入可选后续）。
- state_unavailable分界：仅带材料语境（题组/材料/可信历史）才算禁区；「继续检索」类日常追问=基底未知≠受限边界，保持引擎B行为。否needs_clarification一律拦（实测误伤两个既有测试）、否改D1/D2编译器（unavailable语义本身是对的）。
- 材料语境frame级单点推导`frame_blocks_contract_blind_pipelines`（task_frame.py），两调用面共用；否各拼条件（会漂）。
- 总闸降级=诚实文案+degrade+trace走_complete_lane_turn；否静默吞、否总闸里长第二套按材料作答逻辑（那是Episode职责）。
- 展开：`docs/handoffs/2026-09-15-e2-p3h-contract-blind-pipeline-gate.md`；P3g/P3f2见同日快照。

## 当前状态
P3h=50687c0b、P3g=f05d0681、P3f2=e1fc53a7。P3注入面（D4四组九类）已逐条对账收口，矩阵+reading_baseline定性留痕`docs/handoffs/2026-09-15-e2-p3-injection-surface-audit.md`，payload卫生钉测试锁现状。未推送/合并/部署，不跑正式T2→T3/Knevo。

## 已验证
P3h反例先红（adapter20用例=4合同×5确定性题型；run_turn3用例，probe用构造参数answer_query_fn/route_skills_fn注入——那俩是实例属性，monkeypatch类会AttributeError）后绿；813P/4S零破坏（805基线+新用例，含误伤复绿，收据20260915T104611Z）；Ruff通过；engine_b×10+adapter集×5稳定；变异（还原点50687c0b）撤防线1→20/20红、撤防线2→2/2红，完全正交，还原后151P复绿。

## 未验证 / 已知边界
作者自验非独立QC（注入面核查同样是作者对账）。引擎B内部仍无合同意识（被门挡住≠免疫，不得绕两道门直调）；注入式registry_factory内部读取不可撤销。fictional×full前提标注送达属P4/P6。未盖：D7跨轮继承五格全链版（P5）、P4–P7、全仓合入门禁。

## 下一步
1. P3注入面已收口，转P4（D5逐题终态answered/legal_gap/missing+完成状态口径completed/partial）或P5（D7逐轴继承五格全链版，编译器层已有test_axes_update_independently）。
2. P6纯度/锚点时复议reading_baseline是否污染材料题（收口点build_episode_input）。
3. 合并回main前全仓等价CI+用户确认。

## 踩过的坑
`compile_material_contract`把一切「继续/接着」开头（无inherited）编成state_unavailable——写引擎门禁前先探普通词面会不会撞上材料合同语义，全量回归是抓误伤的唯一网。TurnOrchestrator的answer_query/route_skills是构造注入的实例属性。adapter的_run_episode会把context_factory异常吞成failed结果——「必须进装配」断言用calls列表不用pytest.raises。shell显式cd；pytest/ruff用主树venv。
