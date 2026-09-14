# fix/e2-boundary-closeout

## 这个分支做什么
按v10分阶段收口E2材料题边界；主树不动，开发树fwp-wt-e2-boundary-closeout。

## 当前状态
代码e178bb57已提交，未合/未推/未部署。D1@71929260、P2@8d1b3573、P3a@e178bb57均独立通过；P3a仅明确material_only的Episode装配，不是P3全链。QC与测试见docs/verification/e2-boundary-closeout/。

## 决策与被否方案
- 双轴独立：虚构不等于禁检索；显式fictional×full事实槽仍需证据。
- 冻结点最后收窄授权+requirements+原题号槽，否了只清菜单/只改prompt；注册前已有日期/实体/预取读取。
- 坏合同拒恢复；未分型历史/视角背景不注入，否了从助手旧答猜权限。
- 撤回未就绪state_unavailable全局澄清闸，否了劫持所有研究“继续”；可信基底与入口分流仍须接。
- 原题/评分/46针不改；17/29不连续编号上游只留q29，v10只保证连续组，保留为已知边界不改尺。
- 展开见docs/handoffs/2026-09-14-e2-p2-p3a-closeout.md。

## 未验证 / 已知边界
P3仍缺local_only实际IO、预取前歧义澄清、全部输入路径过滤、确定性旁路与失败回落。controller旧摘要、stance、project prior在工厂前已发生；工厂清理不代表入口零读。
P4最终逐题三态、P5可信继承/旧答身份、P6材料锚点纯度、P7全新原始T2→T3均未完成。未冻主备模型、未Knevo正式配对。RE06独立在fix/re06-visibility-timing@a4ace074，I14未闭环，不扩为纯材料比较前置。

## 下一步
1. P3b按实际runner审IO；混合/未知不借cost或freshness放行，保留已证明的本地读取。
2. 依v10收口剩余P3–P7；T3不得重贴禁令。6c7bea6e/413b7a07重叠补丁集成时注明接替。
3. 每阶段独立复核、冻结收据；合并/部署另放行。

## 已验证
干净e178bb57全仓pytest：9743 passed/83 skipped/2 xfailed，exit0；定向446 passed/4skip/1xfail；全仓Ruff、提交钩子通过。独立P3a：222 passed+复制恢复/旁路反例。8d1b3573全仓曾1红为旧图召回，刷新图后单针绿，原红收据保留，不拼接成全绿；e178bb57才完整全仓绿。

## 踩过的坑
每shell显式cd；pytest用主树.venv-workbench/bin/python。Codex重连多但现可执行，最终报告未出不算通过。识别与切句共用前缀，否则“且麻烦不要联网”会漏权限。纯度/锚点没接完前不得实跑宣称安全。
