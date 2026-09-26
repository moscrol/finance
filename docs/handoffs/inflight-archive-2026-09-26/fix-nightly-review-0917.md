# 09-16/17 local复盘恢复

## 这个分支做什么
恢复两日真实行情→staging验收发布→L2→报告/快照，封住指数隐藏复盘会回退。

## 决策与被否方案
- 模板/装机/生效三态核对；只改local，否整份回滚以保留L2根。
- 历史取Sina、核实IPO/CDR；否改今天快照日期。
- staging显式include-completed重算，否信旧success；历史no-caps。
- 生成固定387028b8根，否盲跑旧finalize；仅一次性调用。
- 背景/被否方案/完整证据：`docs/handoffs/2026-09-17-local-review-recovery.md`。

## 当前状态
树`/Users/a77/fwp-wt-nightly-review-0917`；代码5204bb32，日期文档617ecc7b。两日主链已恢复；本枝未push/合并。plan已local，同步树仅覆盖指数模块，L2根未改。主管结束、锁已释放，勿再SIGCONT。两个未跟踪quality-09-16/17.json是产物，不提交。
证据根RUN=`/Users/a77/.finance-runtime/review-recovery-20260917/`；最终发布run_id=cca104bedc85，有换库前备份及SHA收据。

## 未验证 / 已知边界
- 已安装finalize仍是旧生成调用；本轮一次性成功≠正式部署/下次无人值守成功。
- 方法labels/outcomes到09-17，但旧v3协议对v6标签capture refused；rc0≠前向登记完成。
- L3仅09-17 dry-run，唯一候选是投资者问题无公司回答，未apply；09-16无as-of不补滚动查询。KB receive≠apply，晨汇WARN保留。
- 未验Workbench模型episode/浏览器视觉；manual/unverifiable不是命中。本枝全仓pytest/前端/E2E/registry及独立QC未跑，不满足合并准入。
- local沿用成员身份、部分板块等权涨幅；旧资金流字段NULL、09-17清越amount空保留。未做全链网络审计。

## 下一步
1. 先推进生成根分支正式验收/部署，保留L2根；方法协议迁移另走新登记/active切换，不改旧协议。
2. 本枝合并另跑固定revision四叶检查，等用户确认。
3. 读RUN冻结摘要与closeout-evidence-manifest.json；09-17 canonical摘要后来被22:34–22:37别轮覆盖，不认领它。

## 踩过的坑
旧success只证明旧输入；重试会跳过。L2涨幅两位，完成标记无输入指纹。产物/库不入Git。通用经验入vault；KIT/BUILD另树a75b1ba（docs/recovery-receipt-inputs-0917）已推未合，主树他人WIP未碰。

## 已验证
- 两日local数据/报告/L2门COMPLETE（19/20表，非full）；跨日PASS。股票5549/5553，各403板块金额/边际量/适用等权涨幅重算0差；CDR各11成分。
- L2三步均complete/失败0；当前名单及两位涨幅与结果一致，quant处理100、结果60/43。
- 原生成19步、队列刷新10步均PASS；报告/矩阵/KB接收实物验过。快照served=09-17；8792 readiness确认DB/快照同日。
- Ruff/定向114P；收据20260917T142352Z-5204bb32；删刷新分支变异1F后恢复通过。14日历史对账达阈值≠完全复刻。能力图谱audit rc0，记忆已回写。
