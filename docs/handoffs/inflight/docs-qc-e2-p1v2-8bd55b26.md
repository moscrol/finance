# E2 P1v2 复审 · 8bd55b26

## 这个分支做什么
独立审D1分类器，未改实现。正文 `docs/handoffs/2026-09-14-e2-p1v2-8bd55b26-qc.md`。

## 决策与被否方案
- 退修：3项P1级+3项P2级；不进入实施阶段P2。
- 否了把长文/混合句残留全留P4：已影响分类，不只是题文精度。
- 旧T3探针从全kinds改为message_kinds：q7 premise是正确新增，不能误报回归；保留旧输出。
- 纯函数组合反例先修D1；否了提前PK或下游重扫全文，避免因果与职责混杂。

## 当前状态
正文、探针、收据已提交 `3ab65b5e`；本交接随收尾提交。未推送、未合并、未部署。
树 `/private/tmp/e2-p1v2-qc-8bd55b26`；作者树/主树/目标实现均未改。
远程实施分支核对同8bd55b26。R7旧广扫归属撤回接受。

## 已验证
- 三文件73 passed/1 xfailed：目标rev，代码dirty=false。
- 五文件88 passed/1 xfailed：env-i/umask022；目标rev，dirty仅审查脚本，不是干净全量证明。数字重叠不加总。
- 扩展探针46项29通过/17断言失败，归六类；原24项校正T3控制后23通过/1真失败。
- T2/T3 txt与run.json.question逐字节一致，原题八题保留及消息/题级标注通过。
- ruff、diff、字段门禁及审查提交钩子通过。代码地图重建ready但无query命中，定位依据源码。
- 证据 `docs/handoffs/evidence/e2-p1v2-8bd55b26/`；脚本 `scripts/e2_boundary_review_probe.py --repo <目标树>`。

## 未验证 / 已知边界
无全量结论。P2两轴/hash、P3冻结与九类注入、P4逐题合同、P5跨轮继承/恢复/来源、P6纯度、P7全新原始T2→T3均未验。纯解析错误不是生产越权实测。

## 下一步
作者修F1强保护跨界、F2长文复核、F3A8/虚构声明漏检、F4同句未闭合引号、F5长/引用续行丢题、F6引导块指令终点。更新“残留只影响精度”声明；保留原题与组合探针，固定新revision再审。

## 踩过的坑
掩码用于隐藏内容，不等于原始空行；已保护内部不能再参与外层配对。共享函数不等于识别集合完整。收据先核树/rev/dirty原因，再看数字。方法沿用permission-intersection-requires-complete-candidates，工具已归scripts，不扩生产门禁。
