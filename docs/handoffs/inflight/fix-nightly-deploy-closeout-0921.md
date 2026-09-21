# 夜跑部署差距收尾

## 这个分支做什么
#827准备已合夜跑代码的窄发布，不接管#810/429、归属三单或Arena。

## 决策与被否方案
- 新建sync/生成/L2固定adcda94b三根；否reset旧根，补丁/产物/回退点保留。
- 用户「执行」后先独立复核和最新合流全叶；否历史绿收据移签。
- 最终全量磁盘耗尽、Quality无结论即停；否25P诊断拼绿、自动重开审查。
- 只归档回收本轮pytest scratch，否删他人树/生产数据。展开见`../2026-09-21-nightly-deploy-execute-blocked.md`。

## 当前状态
最终候选2ea6c3db（已合当时main f783f19c8）已推#827，仍open/WIP。后续文档不移签代码收据。用户条件式合入/夜跑发布授权已有，但前置未过，**未合main、未装机、未采集**。
夜跑六装机文件仍原哈希，loaded旧根、runs3/4；三adcda候选干净未用。8792仍他会话adcda，health正常；readiness现503（快照9/21、DB9/18），别抄旧ready。

## 已验证
2ea6：Spec PASS，33请求；安装20P/接线33P，自建21断言根复跑21/21，哈希已核。报告误比逐字保全对象已在qc勘误，原文保留。
前端110P/E2E34P2S、registry五项0、Ruff0、生成7+4边界及hooks通过。
Python原进程12454P/2F/8error/85S/2X，全部失败错误含ENOSPC；首尾同SHA干净。回收自有临时目录后仅两失败模块诊断25P，不替代全量。
证据`docs/verification/2026-09-21-nightly-deploy-execute/manifest.json`；外部`~/.finance-runtime/reviews/nightly-deploy-execute-20260921/`。

## 未验证 / 已知边界
Quality10请求/260秒exit1，stderr空、事件中断，无报告；同期磁盘耗尽但退出原因未证，无自动重开。独立整体未过。
全量仍红，final-gate-qc=BLOCKED。自有3.1GiB scratch全项验档后回收；299MiB包留外部。空间仍紧，不能立即并发重跑。未签文档尖/后main。
旧S7只验合成库非完整生产副本；同花顺目标日/关键值恢复、真实日报/L2/生成均未验。安装器无双job事务/自动回退；发布脚本仅准备未执行，绑定2ea6和红QC。

## 下一步
先协调磁盘/并发，固定最终对象重做全量；Quality另获一次明确有界补审。全过才合入并按release-plan备份/核漂移/锁/卸载两job/窄安装/loaded核验；不kickstart，效果另验。旧根/他人树不删。

## 踩过的坑
JUnit的setup/teardown可同case多状态，不能按case互斥分类；看原进程/收据/元素。压缩包逐项随机getmember慢，顺序校验；只读fixture目录需先完整验档再定域回收。
