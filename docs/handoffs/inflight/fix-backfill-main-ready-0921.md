# 302132 当前main离线整合

## 这个分支做什么
把无人持续推进的302132验收修复前向整合到main基准728f3271，只交代码候选，不执行生产回填。

## 决策与被否方案
- 从原1fd34dc7（修复be3f2930）无冲突merge-tree取4个源码/测试文件；否决整枝重放旧交接或覆盖main CLI。
- 固定新代码400d02dd重新验；否决把原枝104P或旧全量移签。
- 背景/取舍：`docs/handoffs/2026-09-21-backfill-main-ready.md`。

## 当前状态
代码400d02dd已推；此后仅补交接与证据，代码身份不变。原两条来源分支/工作树保留。新树`/Users/a77/fwp-wt-backfill-main-ready-0921`；解释器用主树`.venv-workbench/bin/python`。
main未合、8792未切、生产库未写。分支名main-ready不是验收结论。

## 已验证
400d02dd clean：全仓Ruff，Python12017P/85S/2X；前端110P、E2E34P/2S，lint/typecheck/build均过；finance-only registry五项0。收据精确SHA、dirty=false、worktree_dirty_total=0、base-drift0校验通过。原件在`docs/verification/2026-09-21-backfill-main-ready/`。
首轮包装脚本rc1，不伪装绿：conftest未采用自定义收据目录。找到真实收据后显式--receipt读回及身份校验均0；不覆盖原失败。

## 未验证 / 已知边界
本轮没有独立Spec/Quality裁决、真实冻结输入/生产数据验收或发布。旧来源审查不能代新合流签字。全量收据只签400d02dd，不移签后来文档提交；最终尖定向复验见PR。

## 下一步
独立复核目标绑定、超大数结构化拒绝、staging/备份/原子发布与第三方切片不变；然后在届时最新main候选跑完整合流门禁。合main及生产执行各需确认。

## 踩过的坑
显式从git解析完整SHA，别手填；前端首次错误SHA被rc2拒绝，保留原件。不要读共享latest.json代替带时间和SHA的收据。包装脚本收据目录与conftest不一致仍待单独修复。
