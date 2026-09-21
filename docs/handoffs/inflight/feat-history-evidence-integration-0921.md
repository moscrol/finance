# 历史来源绑定与缓存授权 · WIP #841

## 这个分支做什么
接替#829来源返修，基于#832/a140；新增缓存命中当前授权、锁内单次读。#841仅以#832为diff基线，不执行合入#832。

## 决策与被否方案
- 缓存不是授权；RunStore既有run写锁内重载元数据、重验、仅读一次，否双读和另一套锁。
- refresh重建替换；成功才写缓存，拒绝不改别名/结果/原件；省略conversation参数保旧错误合同。
- 历史严格恢复与普通旧档窄兼容保留；hash不代证真实归属。
- 固定SHA绿不抵消main漂移；不降阈值、不移签docs。完整取舍见`docs/handoffs/2026-09-21-history-authority-followup.md`。

## 当前状态
代码`7249378a5bdb9b01cc62ec3bca13af3149bd48df`及证据`50c9bfcf243b47b985469f21b3883a91792f3000`已推；#841正文/评论5461更新，open/WIP未merged。新包80文件326556字节，Git核79/79；旧f90包73/73未改。本份为后续docs。记忆134bc4cf已推，未动共享脏树。未合main/部署8792/写生产。

## 已验证
- 724首尾clean全量12659P/87S/2X/17W，0F/0error，809.93s；收据`20260921T135039Z-7249378a.json`精确checker0。JUnit新增24项无删除，89项skip/xfail不变。
- 同SHA315P定向；前端六步0（110P/E2E34P2S）；Ruff/registry/crosswalk六条0，保留98条warning。
- 七撤保护均行为红、无收集错；225行9页累计905次卡离线恢复（含重复元数据）身份/特征一致，源不变、模型0。
- 主包`docs/verification/2026-09-21-history-authority-followup/`，后验回执在同级`2026-09-21-history-authority-closeout/`。

## 未验证 / 已知边界
main批次checker1：相对028a251a共同祖先f2c3，13提交/6merge超过5。独立Spec/Quality未做，旧K3超时不代签；自然金融仍not_passed。225/25与候选数字自然引用/判官、#793同窗候选排序、#794展开/版本/预算/取消仍待。#833/#845联合树未验。私有_write_run复现不证公开可利用漏洞；锁不防直接改盘，临时store不认证原始归属。

## 下一步
冻结实际合流base/head再跑全叶；独立/自然验收另确认预算与范围。无授权不合main、不部署、不重开K3、不补绑漏引数字、不关#793/#794。

## 踩过的坑
未知run错误类型退化由消费者抓到；visibility不可用仍FileNotFoundError。并行pytest曾撞名不能累签，本轮串行。磁盘约8.9Gi，保留失败原件/owned临时目录。主包工装为固定版源码快照，正式保护在测试；工具失败与产品红分账。
