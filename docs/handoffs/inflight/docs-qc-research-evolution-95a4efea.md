# 05 补遗复核 · 95a4efea / 75ab917a

## 这个分支做什么
独立复核 05 的生命周期冲突、收据联合身份修复及相邻费用边界；不改业务实现。

## 决策与被否方案
- 原两项关闭，但保留两处收据层 P1 退修；否“汇总 unknown 就足够”，06 会独立展示收据。
- 缺口校验必须共享候选资格＋身份＋组件；仅抽公共身份谓词仍漏 selected=False、tool 代替模型费。
- 反例已脚本化，未造通用静态规则（合法组件依赖领域合同），未改脏的 harness-reference。
- 展开：`docs/handoffs/2026-09-14-product-value-95a4efea-qc.md`。

## 当前状态
证据提交 `342fd6cd`；本文件为随后文档收尾。仅审查脚本/报告，未 push、未合 main、未外呼/写生产。主检出他人改动未碰。
- S1 P1：`measure.py:573–579` 遍历含 selected=False 的审计全集；错配粗账压掉正确细账后，被排除细账仍把收据 incomplete→valid。
- S2 P1：同处 any(身份匹配) 仍让第二执行的 tool / writer+tool 代替缺失模型账；收据 valid/缺口空，summary 才列 writer/review。
两项在父 f8540a53 同样存在，非本次新增回归。01/02/04 保持候选，06 仍是最终集成验收前提。

## 已验证
- 候选干净树 05 模块 121 passed；全仓 Ruff 绿。
- 上轮身份检查：父 3红4绿→候选7绿；第4–7轮23绿。
- 新检查：候选3红4绿，父4红3绿；三个合法费用控制绿。
- 核全量历史原件 @95a4efea：dirty=false，9660 passed/1 failed/77 skipped，exit=1；同失败ID单跑3/3绿。不是全量绿灯。
- 完整JSON/日志/历史收据：`~/.finance-runtime/reviews/research-evolution-95a4efea-qc/`。

## 未验证 / 已知边界
本轮未重跑全量、第1–3轮、06/前端/E2E/最终组合registry。收据只能核失败ID，不能单凭它独立核“10s超时”根因。

## 下一步
修测量层有效候选过滤、按协议逐执行组件缺项推导；保留失败只需writer和原流程人工计时对照。重跑：
`QC_TREE=<候选树> .venv-workbench/bin/python -m pytest -q -rf scripts/review_probes/check_product_value_selection.py`
再复跑旧身份检查及最终干净组合全部门禁；本轮未授权合并。

## 踩过的坑
外置pytest探针的自动收据可能绑定探针树SHA，不是被子进程导入的目标；身份看QC_TREE/根映射及输出JSON。selected变量实际是带标记的全集，不凭变量名认语义。
