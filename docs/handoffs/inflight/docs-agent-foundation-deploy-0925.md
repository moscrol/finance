# docs/agent-foundation-deploy-0925

## 这个分支做什么

承接用户「合并部署收尾」授权，记录切换前阻塞和可接续候选；不是成功部署证明。

## 决策与被否方案

选就绪全过再切，否带503宣布上线：规程要求readiness全true。
选候选独立venv，否升级共享环境：依赖可对账且不影响其他进程。
选保留台账歧义，否伪造switch：本轮没有真实切换。
展开见 `docs/handoffs/2026-09-25-agent-foundation-deploy-blocked.md`。

## 当前状态

部署已授权，不再沿用旧交接的「未授权」。停在切换前：8792仍为3b7e473575b0，启动器和软链未改。
readiness HTTP503：行情快照09-24，fact_market_daily最新09-22，只读复算一致。未获生产数据回填授权。
已准备干净ea42fac4254b候选及本树环境；主干随后前进03352758cf9b，旧完整收据已被精确版本门禁拒绝。
部署账本还有port=null的f210 startup歧义；没有删除或补造记录。
机器事实：`~/.finance-runtime/reviews/agent-foundation-0924/deploy/status.json`；本分支只写交接，未合main。

## 已验证

ea42候选bootstrap/pip check通过，doctor ready且无依赖漂移；与受测环境57项包相同；离线smoke 2P；前端3文件字节一致。
旧完整门禁只证明ea42；四张原PR的实时状态见证据根pr-readback.json，不重复合并。

## 未验证 / 已知边界

未验证033527或本交接SHA全仓门禁，未切8792，未跑真实模型探针；生产数据未写。
候选doctor的production_verified=false；其代码图未建，不能称架构语义已验。
候选有venv不等于启动器已使用它，当前生产仍硬编码主树解释器。

## 下一步

先授权canonical daily-full补齐数据。就绪全绿后fetch并固定新主干，重跑四叶、核对台账归属、接线受测解释器，再切换并完成三项验证和备份。

## 踩过的坑

文档合入也改变SHA，不能复用旧收据证明新主干。若改启动器为快照内venv，回滚要同时恢复启动器与软链；不升级共享环境凑依赖。
