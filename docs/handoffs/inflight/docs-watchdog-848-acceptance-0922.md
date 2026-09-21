# #848 授权范围完成

## 这个分支做什么
保存watchdog修复验收与授权合并后交接；文档独立提交，不移签代码收据。

## 决策与被否方案
- 用户“授权，推进”只合固定#848并验实际提交；否了扩大到部署/#846。
- 实际merge commit重新完整验，否了用候选绿代签；历史红收据保留。
- 0.2s预算未增加，0.8s已收窄为到期至watchdog返回，否了假称旧整轮墙钟保证未变。
- 本轮快照：`docs/handoffs/2026-09-22-watchdog-848-authorized-merge-and-main-gate.md`；前轮验收与独立限制见同目录`2026-09-22-watchdog-848-acceptance.md`。

## 当前状态
- #848已按授权合并，实际提交`a2c8d1f90773fdf3dcb7cf53f5d9733590924ae1`；双亲e82717d9/2007edfa5，tree等于受审候选。
- 实际main完整门禁PASS，最终PR评论5563回读一致；自有runner、pytest和测试服务均已结束。
- 本docs分支仅文档后继，未合main；生产仍adcda94b5e40 recovery，未部署/重启/写行情。#846仍open/WIP。

## 已验证
- 独立候选：同一位Claude规格/质量PASS_WITH_LIMITS，不是双签。
- 实际a2c8d1f9：Python12511P/85S/2X、0F，17warnings/1155.85s；Ruff、registry五项0。
- 前端六步0、unit110P、E2E34P/2S，一次通过；首尾全树干净，产物已归档。
- 原生收据`20260921T191851Z-a2c8d1f9.json`，完整SHA/解释器/指纹/干净/base drift0校验通过。
- 证据`~/.finance-runtime/reviews/848-postmerge-main-20260922/evidence-audit.json`，含JUnit/日志hash/收据原件副本；审计时远端main==受测SHA。
- 授权与合并记录：`~/.finance-runtime/reviews/848-authorized-merge-20260922/`，消息aa752be6。

## 未验证 / 已知边界
- 新绿不改写e82717d9历史12509P/1F，也不证明假钟作用域/线程窄窗等独立限制消失。
- 无新生产health/readiness或真实金融问答；含未验K3的main仍禁止整体部署。
- #846无有效独立终审，不能用本轮绿补齐。
- 候选首轮E2E trace未归档；本轮实际main的test-results已另存。预检端口与runner实际端口不同但服务正常启动，详见快照。

## 下一步
1. 本授权范围已完成，无待跑任务；后续文档分支单独处理，不移签代码收据。
2. #846独立验收、生产readiness与K3发布边界分别处理，不自动推进。
3. 不整体部署main、不重启8792、不写行情，不清事故或他人证据。

## 踩过的坑
- ps查不到已退出进程的1不是测试/收据校验失败；逐工具核返回码。
- 原生收据秒级命名会覆盖，及时复制；E2E重跑前先归档。
