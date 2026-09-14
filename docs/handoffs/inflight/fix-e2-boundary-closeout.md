# fix/e2-boundary-closeout

## 这个分支做什么
从main=1fef3d27收口E2 D1/P1旧独立QC六类反例，代码1a7363c4；不越阶段接P2。

## 当前状态
代码已提交，未合未推未部署。独立树fwp-wt-e2-closeout-qc固定1a7363c4，QC四次尝试未完成：前两次连接故障，后两次命令宿主缺失/禁用导致未执行代码检查。**P2仍不放行**，没有有效独立findings。

## 决策与被否方案
- 原46探针/原题/判据保留；否了改尺求绿。
- 引用外层屏障、长材料先复核再认题、掩码只识别而原文保留；否了编号抢题与掩码裁正文。
- 作者自验不替代独立QC；详见 `docs/handoffs/2026-09-14-e2-boundary-closeout.md`。

## 未验证 / 已知边界
split_user_message仍旧抽取只附regions；P2–P7载体/权限/逐题/跨轮/纯度未实现。未全新原始T2→T3、未Knevo配对/迁移题、未冻结生产主备模型。不是全链材料题已修，也不是全量pytest结论。

## 下一步
1. 恢复能执行命令的独立审查入口，审1a7363c4（不可绕安全边界）；提示/tmp/e2-closeout-qc-prompt.txt。
2. 过D1才按v10做P2–P7；报告反例先修P1。
3. P7全新会话原始T2→T3，T3不重新贴禁令；旧题和评分不改。
4. 材料账本6c7bea6e/降级413b7a07有重叠，集成明确接替。
5. 06在fwp-wt-re06-closeout-check分支fix/re06-visibility-timing@a4ace074：会话计时部分工程绿，I14任务配对未结案，见其交接。

## 已验证
原探针29/46→46/46；干净1a7363c4六文件 **234 passed/4skip/1xfail**，全仓Ruff/提交钩子/diff绿。4skip为同类引号参数组合不适用，有独立嵌套针。
收据 `~/.finance-runtime/test-receipts/20260914T082049Z-1a7363c4.json`；原始证据 `docs/verification/e2-boundary-closeout/`，含QC第三/四次未完成报告。

## 踩过的坑
每条shell显式cd；pytest主树.venv-workbench解释器。主检出脏不要碰。Codex缺code-mode-host，单次关开关仍没命令工具；别把模型能回复当作能做审查，也不要反复空跑消耗。
