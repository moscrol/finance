# 历史来源绑定与缓存授权 · WIP #841

## 这个分支做什么
接替#829，基于#832；724缓存授权加固后前向合入固定main028a成为f73。#832仍是PR基线，不执行合入#832/main。

## 决策与被否方案
缓存非授权；同run锁内重载、校验仅读一次；refresh替换；保旧错误合同。否中断日志/作者回归代独立签字、自动重试/加购/重开旧K3。自然预算未定不启动。详情`docs/handoffs/2026-09-22-history-review-resume.md`；旧包不改。

## 当前状态
业务代码仍f73d2133968d51d3c782d3e12ee9aa4d0618ef45。本轮独立审查固定docs头43511e3f15bd18bfd49868dfbac5b1d3774fd0bc，后续仅本归档/交接文档。读取恢复后两条审查已读源码，但终稿前额度耗尽：Spec/Quality均BLOCKED_USAGE_LIMIT_NO_FINAL_REPORT。自然仍not_passed；未合main/#832、未部署8792、未写生产。

## 已验证
- 最小Codex只读探针成功，确认完整43511 SHA及read_history_artifact签名，不算审查。
- Spec395.184s/Quality421.208s，前后SHA/status稳定、各600s时限未触发、exit1用量限制，终稿缺失。新包`docs/verification/2026-09-22-history-review-resume/`；大日志在`~/.finance-runtime/reviews/react-trace-integration-20260921/history-review-resume-43511/`，由EXTERNAL-SHA256SUMS绑定，须保留。
- 本轮pytest=0、金融探针=0；旧64b0的599P与f73全量各属原SHA，不移签。非docs diff为空。
- 新增个人软链`~/.local/bin/codex-code-mode-host`指向应用内宿主；会影响该用户CLI入口，未改config/权限/服务。地图build到43511，31102节点。

## 未验证 / 已知边界
无独立裁决；225/25自然理解/有效分母/数字引用/判官消费未验。#793/#794、#833/#845联合树未签，main e827组合未验。磁盘最近约3.9GiB，低于原全量6GiB停止线，未跑全量/装依赖/起服务。hash不认证来源，锁不防直接改盘；HTTP用户下载与同会话reader分账。

## 下一步
先核额度和磁盘，再固定SHA新开有界独立审查，终稿缺失仍blocked。自然题/模型/provider尝试硬上限/服务端墙钟与停止规则确定后才走workbench_probe。它的--timeout只限客户端等待，不取消服务端。合入需用户确认并验实际组合/main tip。不关#793/#794、不接管别线。

## 踩过的坑
软链CLI同目录缺配套宿主会阻塞；本次绝对CLI路径与补链一起生效，未做单变量对照。--ask-for-approval放exec后会解析失败；现存config/hooks warning未修。CLI tokens used不等于计费金额；共享磁盘变化不归因本轮，外置哈希不等于原件备份。
