# fix/e2-boundary-closeout

## 这个分支做什么
按v10分阶段收口E2材料题边界；开发树fwp-wt-e2-boundary-closeout，主树不动。

## 当前状态
应用8ea6c5c1已提交，未推/未合/未部署。D1、P2、P3a此前独立通过。P3b作者测试绿，独立Codex在执行前503，无报告，不算通过。证据docs/verification/e2-boundary-closeout/，独立树/tmp/e2-p3b-qc-8ea6c5c1干净。

## 决策与被否方案
- 双轴独立；虚构不等于禁检索，范围声明不能替事实背书。
- 最终冻结授权/requirements/输出证据类型，否了仅清菜单；读取可早于注册。
- local_only保留已审定DuckDB/主线/JSON索引/身份明确的记忆；未知/混合runner拒绝，否了按cost/freshness猜IO。
- registry构造器清预取/calc_loader，副本只收窄；EpisodeScope与dispatch共用IO判据。认证是可信装配声明，不是OS沙箱。
- 跳过未分类静态KB预检、不为禁用工具解析全局实体；历史附加工具不挂，finance_query历史窗口约束保留。
- 展开见docs/handoffs/2026-09-14-e2-p3b-local-ceiling.md；P2/P3a背景见同日e2-p2-p3a-closeout快照。

## 未验证 / 已知边界
P3b独立复核受阻：qc-8ea6c5c1-blocked.md。未覆盖全部本地runner。local_only原题号槽未接；普通context未来源分型。controller旧摘要/stance/project prior/视角在工厂前已发生，注册表原始预取消费者/压缩/恢复/子研究、确定性旁路与回落仍待P3全链接线，局部零外呼不代表入口零读。
P4逐题三态、P5可信继承/旧答身份、P6材料锚点纯度、P7全新原始T2→T3均未完成。未冻主备模型、未Knevo正式配对。RE06 I14另线未闭环，不扩大为纯材料比较前置。

## 下一步
1. 固定8ea6c5c1补独立P3b复核，报告出前不升阶段通过。
2. 按v10收剩余P3–P7；T3不得重贴禁令；6c7bea6e/413b7a07重叠补丁集成须写接替。
3. 每阶段独立复核+冻结收据。前端/E2E本轮未跑；合并与部署另放行。

## 已验证
干净8ea6c5c1全仓pytest：9762 passed/83 skipped/2 xfailed/17warnings，exit0；定向286 passed（含新19针）。Ruff、字段门禁、diff、提交钩子通过。full-8ea6c5c1-tests.txt/frozen-8ea6c5c1-tests.txt为原输出；不是独立QC。

## 踩过的坑
每shell显式cd；pytest用主树.venv-workbench/bin/python。socket/子进程探针须同时计数尝试，防错误被吞。mainline工具无参；缺库沿既有IOException，不联网补取。root_budget失败栈会保活，测试task_id要独立。不改原题/评分/46针求绿。
