# 在途：输入与底座验收
## 这个分支做什么
阶段A基线与B离线前置，不是生产恢复。母规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。
## 决策与被否方案
- SPT词面条件合同拒收；同句不保证同主体/时点/确认。实验仅失败重放，正式评分/保存拒绝实验字段；不恢复旧3/3。
- 票据/装配/送达/采用/质量分报。记忆开口复用runner，不依赖模型主动选工具；授权+身份双闸，不回落default。
- 记忆非市场事实，gap非判断；1秒与根期限交集，两槽限流，迟到不回灌。展开：`docs/handoffs/2026-09-25-memory-opening-prefetch.md`。
## 当前状态
P0写侧f3d39d7d2；P1开口读侧9533417c3已提交，后继文档不移签代码收据。未push/PR/合main/部署。
临时根P0写入→下一轮首请求自动带入纠偏通过，无需模型调用工具；透传被纠正完成稿主体，避免省略主体的新行失联。证据：`docs/verification/2026-09-25-workbench-correction-ingest/`。
SPT挑战4P/8F、REJECTED；原画像1/3，正式卷缺/真实边界空。风远十条替代关系、余42条及人工原授权仍待owner追溯。
09-25 01:43历史readiness503缺market_data_consistency，本轮未重探，不能当当前生产状态。
## 未验证 / 已知边界
未读写真实用户、补数/换库/重建索引/恢复采集或新增模型。首请求PASS来自真实Episode循环+模型替身，不是HTTP/UI验收。真实Workbench/CLI采用与金融质量UNKNOWN；完整发布门禁未跑。
material_only/local_only仍无预取。线程超时不能杀磁盘IO；槽满回busy，退出仍可等待底层读取；未做生产稳定性演练。共享能力图谱在树外，本轮未改。
## 下一步
1. 核最新主干漂移、owner复核写侧与读侧，合入前完整门禁并等用户确认。
2. 行情/KB/发布owner闭合日期/身份/范围/字段/索引；预算齐后按#76分别验Workbench和CLI，再C/D。
3. SPT不恢复拒收合同；正式画像/考卷走批准流程。风远沿Q-002追溯，不复制队列。
4. 共享图谱owner回写P1离线PASS与9533417c3指针，保留未部署/真实采用UNKNOWN。
## 已验证
9533417c3干净定向641P/0F/0S，收据clean-opening-receipt.json；Ruff/差异检查/提交钩子通过。P0临时根探针PASS。旧读侧117P绑定ec806440c，写侧231P绑定f3d39d7d2，不移签。
## 踩过的坑
词面实验拒收不等于SPT通过；缺就绪前置不新增模型运行。记忆坏行/读取失败不能报空命中；只给gap贴标签不足以阻止事实绑定，终止与后验两处都要验。
