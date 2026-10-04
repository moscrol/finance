## 这个分支做什么
四片Harness与S1集成；工程、独审、真实质量分别验收。PR30保持草稿，质量过门后再谈上线。

## 决策与被否方案
| 选择 | 否决 / 理由 |
|---|---|
| 固定51b66d52验组合 | 不转签25de；新main仅文档漂移不重定本批 |
| Workbench沿用多模型配置 | Claude Code只是复审客户端，不进产品依赖 |
| 套餐内按需复审 | 不设旧50元帽；不扩为标准API无限现金 |
| 预算先持久预占再发包 | 缺usage留unknown，断线不证明免费 |
展开及收据：[前向验收快照](../2026-10-04-harness-forward-acceptance.md)。

## 当前状态
产品pin=51b66d52fd7ea8970dfab163f1c24704b298ac58，含main04799bc6；已双远端回读。当前文档头由Git读，不转签候选CI。
FINANCEWORKS-3已由验收接手方置in_review(v11)；同方接手FINANCEWORKS-6(v5)诊断旧真实首错，本分支不抢占。父任务仍进行。
PR30 Draft/OPEN，无auto-merge，候选未合/未部署。生产只读观察为04799bc6健康，非本轮部署。两棵门禁树已保全拆除，4个测试DB克隆仅本地备份。

## 已验证
固定51b：Python20639P/76S/2X、collected20717/full-scope；前端210P、E2E52P/2S；registry五项及GitHub五项成功。四片51+history8+boundary16变异红→绿。Spec91/Standards73次回包均glm-5.3，均无确定P1/P2；同模型隔离静态审查，不代质量。
证据根`~/.finance-runtime/reviews/harness-budgeted-preflight-20261004/forward-20261004T1256/`，先读engineering-closeout.json。

## 未验证 / 已知边界
本批真实Workbench模型请求0。六组假运输18次；预算原型18测试/6变异及1假发包+68本地拒绝通过，仍offline-only、未独审。真实token/推理计费上界、全部运输硬帽与现金准入未闭合。
旧shell sidecar缺deploy/rejudge/cache隔离；live_probe的测试不替它背书。旧conversation预检读question而非完整turns。SDK真实时序/存储恢复/逐句对齐未签。

## 下一步
先读任务6最新归属/评论协调。标准API用途/有限费用、真实运输、实际入口全部写路径和只读数据闭合后，冻结A/B、3题完整多轮、6对AB/BA、匿名全文评分与停止规则，再claim预注册。最多12格只预验、失败不补跑；正式两档效应/金融错误/发布另验。

## 踩过的坑
completed可伴partial/llm.used=false；工具名不等于模型回包。CI/收据只能签同SHA。旧封存不覆盖，Git ref不是数据库备份。R17/R19/240、共享Memory、其它活动树及生产配置不动。
