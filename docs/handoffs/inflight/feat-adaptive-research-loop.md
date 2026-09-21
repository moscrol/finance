# feat/adaptive-research-loop 在途

## 这个分支做什么

修研究回路取证、窗口收益计算、修订与公开保真；最近真实自然验收内容失败，但本轮已落计算与提示边界修复。

## 决策与被否方案

local_only 四只读能力、根 T900/单发帽75/核验共享窗150 不变，不开 derived_calculation，不重跑旧真实题刷成功。
`finance_query` 受限提供已观测日逐日复利摘要；不用自由文本算术解析器，也不把 `river_query` 个股首前收盘口径冒充板块日涨幅口径。
收益比较必须同窗同实际日期集合、收益差用百分点；空集/gap/失败仍不升级为否定事实。判官不可用仍 partial，但公开提示不再把结构绑定说成计算正确。
完整背景见 `docs/handoffs/2026-09-22-adaptive-return-summary.md`；自然失败见 `docs/handoffs/2026-09-22-adaptive-absence-live.md`。

## 当前状态

最新代码提交 `3ab0d3d9e`，树应保持干净；未 push/PR/合 main/部署/fetch，未操作生产8792。实现涉及 `finance_query`、写手/判官提示、超时公开投影、产品门文档及收益测试/变异套件。

## 已验证

提交后准确 SHA 回归：`984 passed, 8 skipped`，收据 `/Users/a77/.finance-runtime/test-receipts/20260921T180047Z-3ab0d3d9.json`；Ruff、diff check、pre-commit 全绿。
固定提交 `finance-return` 变异：基线49 passed；11条撤保护逐条红，还原49 passed，结果在 `/Users/a77/.finance-runtime/adaptive-return-summary-20260922/mutations/results.json`。
五组审计原件日线与冻结测试逐行一致；真实模型未重跑。

## 未验证 / 已知边界

未证明自然模型会选择新摘要或方向正确；判官超时/预算归属未定位，仍可能以 partial 交未审内容。未覆盖均值自然选择、空集/零值/历史回退自然样本、模型自报partial终局重核，以及完整前端/E2E/registry/独立Spec/Quality。

## 下一步

先基于已有脱敏收据定位判官服务与超时归属，不能重复 live 刷绿；后续样本另预注册。合入前补跑全仓等价 CI、前端门禁及独立审查。

## 踩过的坑

pytest 必须用主树 `.venv-workbench/bin/python` 并先建独占 basetemp；提交前回归不能移签提交后 SHA。`timeout_asked` 不是实际耗时，核验轮数、实际调用数、零秒拒发要分账。
