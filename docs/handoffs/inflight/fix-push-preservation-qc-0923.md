## 这个分支做什么
落实#63保全质检四项整改，并新增两条分叉内容的远端保全头；不是产品验收。

## 决策与被否方案
- prepare/verify工具隔离临时索引并核正式父身份/tree/归档；否了仅改笔记与提交后amend。
- 提交/推送留在显式命令侧；否了校验器自动写refs。旧/tmp脚本已退役exit2，原件保存。
- 只换名保全1/10个仍仅本地提交的两枝；否了复活其余8枝（内容已在main）。
- 归档绿只证字节；否了替代独立审查/真实Workbench验收。

## 当前状态
工具 `fdaf35251235958b34314a0df74344b0f571e4fa` 已推 `gitea/fix/push-preservation-qc-0923`，未合。cutoff交接 `4a6e18da6` 已推，3488→2601字节；原候选/独立树未动。
保全头：`salvage/grok-cli-judge-local-20260923`=a354d2651d23；`salvage/reading-rules-baseline-r2-local-20260923`=9c2fff08c76d。原远端不变。
方法记账已统一173新建+11快进+4并发推同=188；初始盘点与最终状态分开。harness编目 `7effba04` 已推独立docs枝，未合；共享记忆自动同步 `9c5aae54` 已回读。

## 已验证
规定主树.venv-workbench解释器：干净fdaf35251定向44P/0F/0E，JUnit与精确收据 `20260922T165950Z-fdaf3525-5f1010728da5.json` 对平、checker通过；五处撤保护均具名断言红。新工具真实预览/正式核cutoff181/181、完整tree相同。vault lint前后33E/17W、具名ERROR无新增；不能称全绿。

## 未验证 / 已知边界
未跑全仓Python/前端/E2E/完整registry、未做新工具独立外审，不能合main。cutoff仍 `AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED`，最近retry-01 usage limit无verdict，本轮未重试。未启模型/服务、未部署/写生产；44P不移签到后来main。

## 下一步
新工具独立复核，重查基线并完成各CI叶后再等用户合入确认。cutoff额度恢复后按原枝交接重绑准确SHA验真实两原题；salvage只保全、不自动合并/删枝。

## 踩过的坑
变量只前缀第一条命令不覆盖后续；echo失败不是非零退出。预览不锁共享工作树，失败后不自动reset/amend。Git clean不等于业务已验收。
详情 `docs/handoffs/2026-09-23-push-preservation-qc.md`；证据 `docs/verification/2026-09-23-push-preservation-qc/`；用法 `docs/workflows/evidence-archive-preview.md`。
