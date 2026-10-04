## 这个分支做什么
四片Harness候选及S1接缝修复；工程、独审、真实质量均过才上线。任务FINANCEWORKS-3。

## 决策与被否方案
- 接纳/反馈经ResearchHarness；loop保留取消/截止/预算/持久化，否默认harness回落。
- 最新授权“没有总上限，plan随便用”：套餐内按需用，否继续用50元闸阻塞；不扩张为套餐外无限现金。
- 真Claude Code复审用套餐；Workbench须标准API，否伪装工具绕用途限制。
- 两轴静态通过不代质量/新main；否转签旧报告。详见[套餐复审](../2026-10-04-harness-plan-review.md)。

## 当前状态
- 产品pin=25de6994bdb79b57e9cf06fcb81f6f5796c67079，含main@108835e27。起始docs头fe26223；当前头由Git读。
- 新Spec/Standards已终结，均未发现确定P1/P2阻塞。Claude Code客户端、后端glm-5.3；64+104次请求全完成，无失败/切通道，后台已退出。
- main另进展到180dbf1e7（本轮观察，需重取），25de未含新记忆/前端/sidecar增量，不签组合验收。
- PR30仍Draft/OPEN，无auto-merge；生产软链仍ffe1c60d，未合入/部署。Workbench新模型请求0。

## 已验证
有效套餐及账户绑定已核；两轴只读/互隔离/出站沙箱各11项通过，全部回包身份/usage/结算及输入哈希审计过。25de既有完整本机/CI另列，不转签docs头。证据在`~/.finance-runtime/reviews/harness-budgeted-preflight-20261004/plan-review-20261004T1025/`，读closeout.json和两轴live/report.md、audit.json。

## 未验证 / 已知边界
独审未执行测试；SDK真实时序/恢复/claim对齐仍有盲点。快照未带变异脚本，作者补核51定义锚点不冒充独审。CLI美元估价非实付、推理token未独立返回。标准API现金通道/边界、完整预注册、真实质量及新main组合未验；套餐许可不覆盖Workbench。

## 下一步
读最新任务/Git/PR；独占树前向集成最新main，按新SHA补门禁与受影响复审。再完成标准API准入，冻结3题完整多轮、数据、6对AB/BA、匿名评分和停止规则，经claim_ledger_id预注册。最多12格仅预验，失败不补跑；正式效果/金融错误/发布门另验。R17/R19/240、共享Memory、其它活动树及生产配置不动。

## 踩过的坑
裸CLI模型名不等于回包；工具身份不等于模型身份。bare模式只露Read，临时目录需隔离。只读快照不是完整仓，缺scripts应列盲点。缺usage不按0；账页0%不等于无限额度。旧封口不可覆盖，Gitea代码ref非数据备份。
