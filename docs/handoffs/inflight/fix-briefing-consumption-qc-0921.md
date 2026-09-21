# 晨汇消费修复

## 这个分支做什么
修IMA缺输入假成功，验证晨汇经教学旁路进入长河；不部署生产。

## 决策与被否方案
缺输入exit2；只读行情+独立标签库；缺行情BLOCKED不造行。旧18788额度限制不可推成K3全局无额度，既有18790桥接已实跑成功。保留模型报告另附异议，不按误报改代码、不把完整报告当批准。详见 `docs/handoffs/2026-09-22-briefing-k3-bridge-qc.md`。

## 当前状态
PR #847/#157继续WIP。此次finance送审518ddf8d0、base a2c8d1f90；KB送审7a47a6dc4、base d0caf3114。随后仅增加收据/交接，业务代码未改，未合main/部署。
桥接三会话97请求均无模型错误：finance首轮40次触顶无报告；KB30次正式BLOCKED；finance第二轮27次CHANGES_REQUIRED。协调者核验发现误报/范围缺口，接纳状态REVIEW_EVIDENCE_DISPUTED_NO_APPROVAL，无独立PASS。进程全结束，无自动重跑。

## 未验证 / 已知边界
finance报告用正确拒绝的反例当缺陷，正向fixture缺strength列失败；KB误引旧index且漏定位实际存在raw。异议不代签独立审查。提示混淆事件布尔与教学汇总NULL，下轮修输入合同。
官方事实、语义发布、生产代码/KB/标签绑定和线上自然问答未验；09-18原消费BLOCKED未解除，本轮未重查行情。长河仅市场汇总非全文；trade_date_only非冻结历史回放。

## 下一步
先校准审查输入定位/字段/日期合同，再明确新的有界补审，不无限重试。最终head/base、KB日志号、合流工程门禁和用户合入授权重核；正式main收据另跑，生产另验真实行情消费。

## 踩过的坑
每条bash显式cd；KB显式FINANCE_WS。exit0≠审查完成，REPORT/verdict齐全也须验证论证。BLOCKED报告交付和审查范围完成分开计。原log MD5与Markdown摘要身份未确证，不改历史。

## 已验证
旧合流338db9114：Python12520P/85S/2X，Ruff/注册表绿；前端110P、E2E34P/2S；KB旧e4cca9531全量529P。旧实际消费09-15 PASS、09-18 BLOCKED。
本轮finance定向12P、KB5P及抽取1338一致；raw当前=BASE=HEAD，报告SHA与首尾树指纹核过。桥接收据在docs/verification/2026-09-22-briefing-k3-bridge/，不是新全量工程或独立批准。
