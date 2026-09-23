# Knevo 材料吸收续修

## 这个分支做什么
PR #877 WIP：沿原题和原审稿闸修材料出稿/判官，不合main、不部署8792、不回补、不写生产画像。

## 决策与被否方案
- 私有原返回+哈希+原因码定位失败；不猜旧故障、不向公开稿或修复提示泄漏原返回。
- 批量格式反馈与schema对齐；不自动改判官报告、跨ID补引用、放宽接收端或增加重试权。
- 完成、内部passed、作者意见分账；不减八问义务，不改冻结题/原件凑绿。
- 展开：`docs/handoffs/2026-09-23-knevo-protocol-repair.md`。

## 当前状态
已提交：8eceac0f2诊断/批量反馈；58f28c237字段组合/引文规则；798ccefb7离线量具。两轮隔离live已停，原件100/88文件hash封存。
第一轮6题：G1b捕获nonfactual+[1]非法；三包来源拒收。第二轮5题：G1b内部passed仍认领未核实旧答；G2b代理文本基本满足但未正式签收；三包进审稿后分别预算耗尽、unsupported+[1]非法、复核超时。包3公开草稿仍有A/B改判不自洽，整体未通过。
索引：`~/.finance-runtime/knevo-absorption-20260923/protocol-repair-closeout/current.json`；作者意见与驱动not_evaluated分开，不是新11题通过率。

## 已验证
798ccefb7干净统一定向1519P/2S/1X/0F，Ruff/收据验签通过；两条撤保护反证见红。两份非法返回原生重放与schema均拒收，0模型调用。七原件hash不变。
新live固定58f28c237，5题原文保真/material_only/0 Episode工具请求；不证明全IO为零。量具改动无新live。

## 未验证 / 已知边界
旧f1fd整链0/12不翻案；Q14概率/因果漏判与真实Q18台账、空集、权限、身份、跨轮未补验。
Schema是生成描述，不是供应商强制解码；包2仍违例。最新代码无全仓/前端/组合main门禁，旧8aadc全绿不可移签。历史diff-check原件空行、共享vault lint红保留。

## 下一步
1. 原规则下追unsupported/nonfactual锚点互斥，不自动归一化。
2. 派生计算逐句绑全输入，删句后重验八问；同时查首层耗时和共享绝对截止时间，分清无预算与服务超时。
3. 修历史认领/A-B改判与Q14语义反例；再补真实Q18前置。获合并授权才固定组合跑全门禁。

## 踩过的坑
用主树`.venv-workbench/bin/python`。run_main_gate从目标树cwd跑；量具用`python -m intelligence.eval.knevo_regression --inspect-run <目录> --case-id <原ID>`。重放要带material_outputs，漏传会误诊report_keys。独立数据根非OS沙箱；私有诊断摘要不泄漏原文。共享harness-reference脏且旧，未接管。
