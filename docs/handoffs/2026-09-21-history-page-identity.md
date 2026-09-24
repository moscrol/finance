# 2026-09-21 历史查询分页的原件行身份修复

## 背景
真实 8857 run 的 `find_analogues` 原件包含 225 行候选，首次查询只向模型展示前 25 行。后续 `read_history_result` 虽然按 offset 切片，但 `_model_projection()` 用 `enumerate(preview)`，每一页都从 `sample=0` 编号；结果是同一个 `result_ref` 内，第二页的第一个样本看起来又是 sample 0。查询结果没有把 offset/下一页指针投影给模型，且旧 `truncated=len(rows)>limit` 在 `offset>0` 时不能表示“本页之后还有数据”。

这属于“原件存在，但展示身份不稳定”的证据可追溯性缺口。它会增加模型跨页比较时把候选行混淆的机会，但不能据此断言旧答案的未绑定数字已经解决；旧答案仍未自然引用/绑定那些行。

## 发现顺序与选择
1. 先读 `_model_projection()`、`read_history_result()` 和 `FinanceResearchHarness.project_tool_result()`，确认完整 JSON 原件保留、模型视图才是缺口，权限和 evidence hash 体系不需改。
2. 在代码前先加回归，冻结绝对 sample、`offset/next_offset`、空页/末页、重叠页和 compare_cases reference 的预期；修前新增 6 项全部失败。
3. 采用最小修复：分页读取把 `preview` 切片后传给 `_result(..., offset=offset)`；`_result` 统一计算 `next_offset`；`_model_projection` 从 payload offset 开始 enumerate，并把分页元数据送进模型可见的历史范围卡；观察文字明确 sample 是原件行号。
4. 否决把每页重编号、把 `truncated` 继续当下一页导航、或直接给模型全部 raw rows：前者损坏身份，第二种语义不完整，第三种会破坏既有上下文预算和原件/模型视图分层。

## 验证与证据
- 修前红例：`history-paging/before.log`，新增分页用例 6 项全失败。
- 修后选集：`history-paging/related.log`，相关历史、投影、权限和 verifier 共 364 passed。
- 真实原件离线遍历：`history-paging/replay-after.json`。输入 SHA256 `98b3746f5cc71027c3a5756ada1057f433a84acb98b65f3106b8c5c95e42d933`；9 页 offset 0..200，每页 25；225/225 唯一行号，特征值逐行等于原件，保存原件不变，模型调用 0。初次用 9 月 18 日截止日运行被现有 `knowledge_cutoff=2026-09-21` 权限门拒绝，`replay-after.stderr` 之外的首错见同目录保留日志。
- 变异证伪：`mutation-sample.log`、`mutation-next.log`、`mutation-partial.log`，分别验证行号重置、缺 next_offset、旧 partial 判据都会使目标回归失败。
- 代码提交 `3765af67b70bf4b39c3c7cb7e22920b808c30d5c`；全仓收据 `/Users/a77/.finance-runtime/test-receipts/20260920T212038Z-3765af67.json`：11986P/85S/2X/17 warnings，严格 receipt check 通过，Ruff 通过。已推 PR #809 WIP。

## 适用边界
此修复只保证同一历史原件跨页的行坐标和导航稳定，不生成新金融事实、不提高完整分母、不把 case 草稿升级成 evidence、不自动补 output binding。`content_hash` 的跨工具稳定性、模型自然引用行为和自然金融质量仍需单独验收；#793 比较合同/#794 证据身份继续推进，不能用本次工程绿代签。未合 main、未部署 8792、未新开付费外审。