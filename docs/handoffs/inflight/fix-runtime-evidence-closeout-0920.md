## 这个分支做什么
修复证据快照拒绝合法展示、API测试夹具漏等Timer。固定底a7f5cc06，不吸收main。

## 决策与被否方案
- v2分别保存首写账本与精确展示序列；只允许supports/contradicts因请求而异，其他字段全量比对。否定只比hash、改写首写原件或自动扩大coverage。
- 截止外展示须完整可解析日期且晚于固定cutoff；不入事实/覆盖，不用标题授权。
- v1读回保留版本/摘要，只有新capture写v2。
- 夹具提交任务前记录所属Timer，保留被任务表移除的引用；等worker后再等Timer，不扫描其他线程，不改生产shutdown。
- 详见../2026-09-20-runtime-evidence-closeout.md。

## 当前状态
代码7199db11、7c3b36b4已提交并推送gitea；无PR、未合并部署。最终文档身份、clean状态和外部收据见下述manifest。下一站为独立Spec→Quality。

## 未验证 / 已知边界
不构成进程重启driver、跨进程租约/单写者或未知效果对账；检查点后的私有结果与消息现场仍未补齐。未跑真实模型与自然金融质量、整仓四叶门禁；旧全量收据不移签本分支。8792未动。

## 下一步
协调者固定最终SHA，从a7f5cc06独立复核两项修复；通过后仍按原合流与用户确认规则处理。

## 踩过的坑
mixed原探针退出0但JSON为storage_failed，须读结果；旧timer探针同步退出后才release，修复后不能拿它5秒超时作绿。新测试异线程teardown、事件放行，且断言无关Timer仍活着。

## 已验证
定向348P、改动文件Ruff、提交钩子通过。六处撤保护均红→绿。原future四格和mixed两格绿，支持durable/ephemeral；v1/v2、摘要/分类篡改、共享fence、授权/子树、API配额/结算回归保留。
外部证据：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-fix/manifest.json`（含命令、日志摘要与最终固定SHA收据）。
