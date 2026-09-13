# L2 / E2 合并就绪复核

## 这个分支做什么
只审 L2@3458a7f0 与 E2 设计@fdeaf1cb 能否合；基线 gitea/main=e40f22b8。报告已提交 c16e7c47，详见 [日期快照](../2026-09-13-l2-e2-merge-readiness-qc.md)。

## 决策与被否方案
- L2 代码复审通过，否了直接签合并：准确候选 frontend/e2e 未核齐，Python 绿不可代替全部叶子。
- E2 退回补正，否了只关闭 retrieval_planner：Episode 最终工具授权也必须受约束，已有 evidence-free 路径可复用。
- OQ 建议非用户拍板：默认哈希省略；严格材料题禁跨会话记忆、保留明确引用的同题链上下文；单 Episode 逐题槽。

## 当前状态
未 push、未合 main、未部署、未写生产库、未启动 E2 实现。作者树与主树在途均未动；本树为独立 QC，只有审查文档。

## 已验证
- 候选 3458a7f0 全量收据 20260913T122812Z：9554P/0F/77S，revision/解释器/依赖/target/基座漂移0校验通过，未重跑全量。
- 本轮干净候选：Ruff exit0；目标16P（125613Z 收据）；旧独立 QC 的 CLI拒空库/回滚/非pct列与幂等/NULL四例4P。
- registry四项及台账交叉检查exit0（反向warning）；diff --check通过。
- git对象清单：E2 evidence仅8文件；MANIFEST/QC包实际在主树未跟踪目录，不在fdeaf1cb。

## 未验证 / 已知边界
- 未跑frontend/e2e；不称完整等价CI通过。未重复生产52日审计或live重跑。
- E2：D2把不联网/假设/仅材料混为一体；D4漏最终allowed_capabilities；TaskFrame已有user_premises与默认字段省略机制，稿子现状需更正。
- A4错将T3 Q8≤200字memo写给T2；T3必须在新建T2→T3同题链中验证，不能裸题无上下文。

## 下一步
L2补齐准确候选所有叶子全绿及专属交接，再请用户明示授权。E2先按报告F2–F5补证据与设计，再复审；不能先实现。主干变化则重判收据。

## 踩过的坑
落盘≠入提交；manifest列21条不等于21个冻结文件（含frozen=false外部轨迹）。不把材料里引用的限制词当用户指令。无新增通用工具，复用现有收据/registry/Git与QC脚本。
