# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；只动fwp-wt-e2-boundary-closeout，主树不动。

## 决策与被否方案
- P3g恢复分支判定用合同状态（needs_clarification），否文案常量等值（文案会改，漏登记就是本片bug重演）。
- 恢复轴值只出自D1/D2编译器（显式声明=编译出的新合同，D7.2）；否恢复分支自解析/手搓合同（第二套解析必漂移）、否把unavailable合同当inherited传回（编译器122行永远解不开）。
- 范围未声明：材料并入+合同如实保留待澄清+装配层按最严收窄执行；否二次采访（预算一轮）、否翻转成confirmed（谎报）。
- 材料类澄清挂起时顶部material分支让路；否恢复逻辑写两份、否把pending恢复整体提前（动到P3f1已验证顺序）。
- 装配与提示统一_material_restricted（material_only或needs_clarification）；否只改执行层（提示鼓励调工具再被拒，白烧轮次）、否改写冻结合同（破坏可审计）。
- 展开：`docs/handoffs/2026-09-15-e2-p3g-pending-clarification-recovery.md`；P3f2/P3f1见同日快照。

## 当前状态
P3g已提交f05d0681（turn_controller/task_frame/episode_factory+测试）。P3f2=e1fc53a7、文档=a20935f5。树干净。未推送/合并/部署，不跑正式T2→T3/Knevo。

## 已验证
P3g反例先红（6用例红因逐一对上探针）后绿；文件×10=290/290；e2+改动模块选集689P/4S（=683基线+6，零破坏，收据20260915T101544Z-a20935f5）；Ruff通过；变异验证三层各有独立承重针（撤pending挂载6/6红、撤恢复分支3/6红、撤装配收窄3/6红），还原后54P复绿。

## 未验证 / 已知边界
作者自验非独立QC（用户已关闭该可选步骤）。旧类型澄清（entity tristate、主体归一）走原路径未动。未盖：歧义（非缺失）预取前澄清、②组prime/知识前缀/系统级默认市场摘要注入、静态路由配置旁路（P3e未关）、D7跨轮权限继承、P4/P6、全仓pytest/前端/E2E合入门禁。

## 下一步
1. 更新门页P3g段（已在树上未提交时一并提交）。
2. 余下P3：②提示前缀组注入路径或静态路由旁路，仍按真实入口反例先红后绿。
3. P4–P7；合并回main前全仓等价CI+用户确认。

## 踩过的坑
装配层收窄条件读data_scope时，axes=None的待澄清合同被当无约束放行——合同docstring写了「未确认不能当full」但执行层没接（fail-open藏在None语义里）。变异验证部分红=邻近层吸收（B/C互兜），报「对它那类反例承重」。探针先证伪再写反例，红因要逐一对上。shell显式cd；pytest/ruff用主树venv。
