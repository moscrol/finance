# #845 工程续验 06 决策快照

## 背景
源码固定`442476f7def1013f1fadebaf6594971921147edc`。05在同一SHA完成12898 ID收集，但普通组有两条RSS失败：外层macOS Seatbelt阻止`/bin/ps`，导致RSS为None；无外层的两条配对通过，只能解释环境差异，不能把2P拼回05全量。用户继续授权重新取得完整Python工程收据，不启动独立模型审核、合并、部署或生产写入。

## 发现顺序与取舍
1. 启动前核对源码clean、磁盘停止线和无遗留进程；固定七个环境ID及脚本/插件SHA到`plan.json`。五个自带Seatbelt测试和两个RSS测试放入environmental组，普通组只排除这七条。
2. 先跑environmental：7P/49 deselected，exit0；通过后跑ordinary。普通组继续保外网阻断（localhost例外）及共享主树/agent-memory写入阻断，最多2400秒，磁盘低于2GiB停止。
3. 两组均使用`.venv-workbench/bin/python`、清理继承环境、关闭共享pytest receipt；插件只选择和记录，不修改断言、不新增skip。它是预声明两组完整收集，不是单进程未分组`pytest -q`。
4. ordinary 1306.09秒正常退出：12802P/87S/2X/7 deselected。两组collection精确并集12898 ID，交集0、漏项0；逐ID setup/call/teardown、JUnit、runner退出码无失败。与05 collection和skip/xfail名单一致，只有两RSS新通过。
5. 对账器坏副本自检制造八类损坏（漏报告、重复阶段、缺call、teardown失败、exit1、选择集不全、日志变更、JUnit错误），均拒绝。它只证明记录器边界，不增加产品测试数。

## 结果与证据
完整分组结果：**12809 passed / 87 skipped / 2 xfailed / failed 0**。普通组外层隔离，环境组无外层；源码首尾clean，未超时、未发停止信号，磁盘约49.7GiB。06包先本地生成33成员、约13.9MB，提交并推#838：`3fd631017b4b40eec4926024f68af0976161da8f`。提交后九包825成员全部通过`check_evidence_archive.py`；旧八包相对57f187de9不变，06 28整件原件和2份JSONL分片重组字节一致。

发布回读：#838评论5560（head为3fd631017），#845评论5562（head为442476f7d）；PR均open、未合。发布回执在外部运行目录的`publication-06/`，不追加冻结包。

## 仍未闭合
06只补Python完整工程执行，不等于#814正式收据、三领域独立终审、历史原四自然题或联合树验收。04定向/前端叶和05 E2E34P/2S不重新移签到06；Node26与workflow Node22差异保留。旧05两红、04中断、E2E首轮缺浏览器等历史原件均不改。

## 后续与禁止事项
后续如继续，先取得用户对#814正式门禁或独立/自然验收的明确授权；不重跑06、不重复POST、不自动续付费审核，不合main、不部署8792、不生产回填、不清理其他工作树。方法可迁移：先固定分母与例外环境，再用实际ID和逐阶段收据证明覆盖；检查器必须用坏副本验证拒绝。
