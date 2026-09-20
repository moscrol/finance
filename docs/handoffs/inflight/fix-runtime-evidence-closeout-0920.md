## 这个分支做什么
修复证据快照拒绝合法展示、API测试夹具漏等Timer。固定底a7f5cc06，不吸收main。

## 决策与被否方案
- v2分别保存首写账本与精确展示序列；只允许supports/contradicts因请求而异，其他字段全量比对。否定只比hash、改写首写原件或自动扩大coverage。
- 截止外展示须完整可解析日期且晚于固定cutoff；不入事实/覆盖，不用标题授权。
- 日期返修：完整日历形状先去外围空白、月日补零，再严格解析；保存原文本。正文/路径/后缀垃圾及上游不识别的week-date不获资格。
- v1读回保留版本/摘要，只有新capture写v2。
- 夹具提交任务前记录所属Timer，保留被任务表移除的引用；等worker后再等Timer，不扫描其他线程，不改生产shutdown。
- 详见../2026-09-20-runtime-evidence-closeout.md。

## 当前状态
代码11216c81返修日期残项后，clean d197450d通过独立Spec→Quality。已推送gitea，PR #798以fix/runtime-contracts-0918为底；本次只回写状态。未合入main或部署。日期返修详见../2026-09-20-runtime-evidence-date-forms-repair.md。

## 未验证 / 已知边界
不构成进程重启driver、跨进程租约/单写者或未知效果对账；检查点后的私有结果与消息现场仍未补齐。未跑真实模型与自然金融质量、整仓四叶门禁；旧全量收据不移签本分支。8792未动。

## 下一步
协调者处理与当前main的8处实测冲突，保留双方API及夹具约束，再跑合流版本完整门禁；main合并仍须用户确认。

## 踩过的坑
mixed原探针退出0但JSON为storage_failed，须读结果；旧timer探针同步退出后才release，修复后不能拿它5秒超时作绿。新测试异线程teardown、事件放行，且断言无关Timer仍活着。

## 已验证
本轮：原日期矩阵6F/6控制→12P，日期相关模块63P、Ruff/提交钩子绿，单个撤规范化变异6F/24P→30P。未重跑348或旧六变异；它们仅签原56d6062e，不移签最新SHA。
独立复核d197450d：Spec原12格与相邻守卫通过；Quality另16P。两份收据分别保存在runtime-evidence-recheck/date-final与quality，不合计为整仓结果。
本轮证据：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-fix/dates-repair/manifest.json`。父目录manifest保留原56d证据。
