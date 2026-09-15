# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；只动fwp-wt-e2-boundary-closeout，主树不动。

## 决策与被否方案
- 已知缺失基底送达默认controller、在resolver/模型前澄清；否运行时回落普通解析器（不可恢复态被静默降级）、否运行时自产澄清文案（澄清逻辑两份）。
- 旧签名controller用签名探测兼容，新参数只传声明者；否加必需参数（注入式旧controller全破）。
- 材料链只在「带新材料或不指代材料的新问题」时重置，material_only留链内；否任何新问题都重置（指代式续问丢链）、否永不重置（换题污染）。
- flaky修在测试侧（每用例唯一task_id）；否把WeakValueDictionary换强引用（改掉的是「活跃期禁撞号」设计不是bug）。
- 独立审查已由用户关闭（纠正04834c55d72b），收口标准=作者自验；不再启动审查者或等服务恢复。
- 展开与D4同源过滤细节：`docs/handoffs/2026-09-15-e2-p3f2-frame-delivery-and-material-chain.md`；P3f1见`2026-09-15-e2-p3f1-source-binding.md`。

## 当前状态
P3f2已提交e1fc53a7（8文件：orchestrator/materials/episode_factory/material_contract/task_frame/turn_controller+两测试）。树干净。未推送/合并/部署，不跑正式T2→T3/Knevo。门页P3f2段落待更新（接手本轮做）。

## 已验证
e1fc53a7提交前：Ruff八文件通过；两测试文件48P；e2+改动模块选集683P/4S/0F（收据20260915T095034Z-6278caea）；11道pre-commit全过（层级ERROR 0）。上一session：聚焦三文件×10连跑50/50稳定；审计启动器50P禁止尝试0。683与446是不同-k口径，不跨口径比数。

## 未验证 / 已知边界
作者自验非独立QC（该可选步骤用户已关闭）。未盖：最终答案质量（P4/P6）、正式T2→T3/Knevo、全仓pytest/前端/E2E合入门禁。余P3未做：静态路由/日历/未知基底/旁路，local_only更多runner与原题号槽。

## 下一步
1. 更新`docs/agent-product-door.md`P3f2段落（同分支提交）。
2. 余下P3旁路小片，仍按真实入口反例（run_turn→真实decide_turn→Episode装配）先红后绿。
3. P4–P7；合并回main前全仓等价CI+用户确认。

## 踩过的坑
弱引用注册表+测试固定id+traceback滞留=GC时机依赖的flaky，排查入口是先让被吞异常带traceback（已沉淀10_knowledge）。shell显式cd；pytest/ruff用主树venv。真实入口反例才抓得到装配层丢态，mock层全绿不算数。
