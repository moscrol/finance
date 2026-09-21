# 夜跑部署差距收尾

## 这个分支做什么
#827准备已合#795/#796夜跑代码的装机候选；不抢#810/429、归属三单、Arena。

## 决策与被否方案
- 新建三根固定adcda94b；否原地reset旧sync：它有补丁/产物，保留回退。
- 同步/L2/生成独立目录；否跟随8792软链或旧生成整树覆盖L2。
- 原安装器加nightly-only/dry-run；否重装6任务，共享helper不同就拒绝。
- 不变S7底座、不带未合#810/429；理由及发布步骤见`../2026-09-21-nightly-deploy-closeout.md`。

## 当前状态
代码2137345da已推，#827 open/WIP；证据归档和本交接只含文档，不移签代码收据。三候选`~/.finance-runtime/finance-{sync,generation,l2}-adcda94b5e40`已建，均净未装机。
8792由另一会话15:35切adcda94b，health/ready正常；#828部署文档已进main f783f19c8。本单不重复切。夜跑装机6文件哈希及loaded旧根/runs未变。

## 已验证
固定2137345da：Python12460P/0F/85S/2X，Ruff0；前端110P/E2E34P2S；registry五项0；适用hooks通过。首尾净同SHA/tree。收据+JUnit12547项+stdout/进程exit0一致。
安装/接线53P；5个撤保护变异被捕获。真实候选adcda上定向80P、生成7+外层4探针绿；旧S7 wrapper+新schema合成库5场景过。L2/方法18文件、旧指数补丁逐字保全。
证据`docs/verification/2026-09-21-nightly-deploy-closeout/manifest.json`（74原件）；原件`~/.finance-runtime/reviews/nightly-deploy-closeout-20260921/`。

## 未验证 / 已知边界
独立审核未跑；未签后来main合流/文档尖，未合main/装机/真实采集/删树。未证同花顺最新日/关键值恢复；#810/429未带。S7仅合成库，不是完整生产副本或302132演练。sync会把runlog/quality写进代码树（既有行为）。窄安装无跨job事务/自动回滚，部署前须备份与人工回退预案。

## 下一步
先确认审查与最终合流对象，再完整门禁；用户确认后按日期快照发布步骤备份/核漂移/切2个夜跑job，实际采集另授权。旧根和证据树不删；8792他会话已切，不重复操作。

## 踩过的坑
原Python汇总exit1是行首正则漏掉同一行的收据；保留run.json，qc_existing_checks只读原精确收据核对，未重跑。初次plist测试红因plutil接受裸字符串，已补Label/RunAtLoad语义校验。
