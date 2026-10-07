## 这个分支做什么
审 vidio 20 连交付，修边界并安全迁回 finance；停在草稿 PR，不合并、不部署、不写生产。

## 决策与被否方案
| 选了什么 | 否了什么 | 为什么 |
|---|---|---|
| 补丁树审实现、干净 main 对照 | 只搜 main 判缺失 | 新能力尚未合入 |
| 从 main 重建公开净差异 | 推原历史再删私人候选 | 删除不能清除历史材料 |
| 剧本是探索诊断；字段投影待人工审阅 | 过闸即预测有效、白名单即披露许可 | 时序独立与散文内容未被证明 |
展开：`docs/handoffs/2026-10-08-vidio-finance-transfer-public.md`。

## 当前状态
代码 `31fc76f957412ee7f53ea709e4cff5eba8b878e2` 已推 GitHub 草稿 PR #75。基线 `82de3fb73`。本树 `~/fwp-wt-vidio-finance-public` 承接所有后期修复；接手先核 HEAD/status。后续文档提交与代码收据分账。2026-10-08 03:43 CST 观察该代码的 Actions：frontend/e2e/registry 通过，python 仍运行；不是最终全绿。

## 已验证
本树 `.venv-workbench/bin/python` → locked-20261007，Python3.12.13。干净代码定向1093P/44S/19888未选，同范围main912P/44S；全仓Ruff通过。收据 `20261007T192253Z-31fc76f9-b43b863edf49.json` 经revision/依赖/净树/漂移0校验，非全仓。证据根 `~/.finance-runtime/reviews/vidio-transfer-20261008/`；质量报告在 `docs/verification/2026-10-08-vidio-finance-transfer-qc.md`。

## 未验证 / 已知边界
本机完整pytest/前端/E2E/registry组合门未跑，真实行情与用户题效果未验。问答仍用旧 `regime_block_for_llm`；新镜头有CLI、剧本是纯函数，未接日常消费。窗口不同ID不证日期/后续区间独立，标准化拟合/PIT/自相关仍需合同。地图structure ready，但vault unavailable、doors/narrative missing、召回未验。

## 下一步
回读 #75 最新head的Actions；完成完整工程验收后请求合并确认。另验只读行情和真实入口，先补剧本时间合同，允许“不命名”。本单不自动扩大到生产或付费模型。

## 踩过的坑
只推此公开分支。`feat/vidio-finance-transfer-qc` 和 `local/vidio-transfer-pre-public-scrub` 仅本地，不推全分支/标签。回完整导入树会漏后期修复。导出嵌套白名单也不保证正文无隐私；还原不覆盖已有库。`first_known_at` 不是版本库；两套标签集合不同义。旧dirty-tree/435e4收据不可移签；关键词回归不是全仓验收。
