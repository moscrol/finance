# 归属续轮接手：只读收据不能绕过工作树身份

## 背景与真实断点

用户要求接手中断会话。粘贴日志中的计数订正其实已完成：协调分支 `6c74fa012` 已推，旧固定组合仍为 `e1b63b1a`，两份manifest各登记30文件。主检出含他人改动，本轮未碰；没有把“Checking deployment readiness”当成合入或部署授权。

共享看板比粘贴日志更晚：Arena已另有 #816，但其追加评论5165记录离线NO-GO。它与归属三项是不同候选，本轮仅核对链接和报告，不复验、不接管、不把其工程绿搬来给归属三项签字。

## 按发现顺序

1. 只读核工作树、远端main和PR #811/#812/#813/#814/#816。指定PR均open/unmerged；没有独立审查记录足以批准这轮归属组合。远端main仍 `728f327160bbd2485cb635e7ef09d040d718d7b5`。
2. 两份旧归档各30项，共60项大小、SHA256和源文件逐字节全部一致；没有运行旧seal脚本、改日志、改收据或重封旧manifest。v1失败和v2作者工程通过保留各自语义。
3. 新隔离树 `~/fwp-wt-ownership-resume-review-0921` 固定e1b63b1a，相关188 passed/1 skipped，Ruff及门禁读回0。这是定向复验，不称新全量或独立Spec/Quality。
4. 额外反例发现：`main_gate_receipt.py` 把tree比较藏在 `args.pytest_exit is not None` 内；`--receipt` 只读模式没有新进程退出码，错树、缺tree、数字tree三种样本均返回0。合法样本也返回0，排除了门禁普遍故障。所有坏样本是仓外复制的fixture，不冒充实际收据。
5. 在干净、已确认没有他人改动的 #814 来源树补正式测试：7个断言先红，旧实现28个既有测试绿。将tree比较上提为所有模式的不变量，修后相关56 passed；代码提交 `cdf6647cfe852bd19c23df0408b4bc2af306da6f` 已推原#814。随后在该干净源码尖经真实shell门禁再得56 passed。
6. 从同一main建立新独占v3，合入 #812 `6c74fa012`、#813 `5994230d`、#814 `cdf6647cf`，固定为 `47530e20fe5c3195e50ce429b31898d57918e413`，已推 `baseline/ownership-gates-v3-0921`。相对e1b63b1a，行为差异仅helper与测试两文件；其余差异是来源尖已有文档。没有修改原v1/v2树。
7. 在v3重跑所有叶子：Python12068 passed/85 skipped/2 xfailed；前端110 passed、E2E34 passed/2 skipped，安装/lint/typecheck/build全0；finance-only registry五项0。三叶前后同SHA、Git干净、固定main未动，唯一收据回读及环境条件校验0。
8. 新helper回读旧原件：在对应旧树上，v2正确收据仍0、v1零计数失败收据仍4。旧测试结果不翻案，新收据只签v3。
9. 本轮86个文件封存到 `docs/verification/2026-09-21-ownership-resume/`，清单自身另计。旧坏样本、先红日志、实际收据与文档分账；全部复制后核哈希/大小/源字节。通用模式续补既有证据卫生笔记；harness-reference原干净文档树追加 `7b40fe0`、推原PR14，未碰其主脏BUILD。

## 决策对照

| 采用 | 否决 | 理由 |
|---|---|---|
| 先核Git/PR/原档再继续 | 按终端最后一行开始部署 | 工作标签不是操作授权，粘贴进度可能落后 |
| 本地反例与最小修复 | 无预算启动外部模型、把自审命名独立PASS | 当前没有独立模型调用授权，作者证据不能自授独立性 |
| 所有模式都核tree；执行模式额外核进程退出码 | 用是否执行pytest决定是否检查身份 | 只读入口仍可消费错对象，模式不同不取消身份不变量 |
| 新固定v3及全叶收据 | 在e1b63b1a追加修复后沿用旧12061P | revision必须对应真实测试对象 |
| 文档封存放协调树 | 为写交接推进固定验收树 | 防止提交完交接后收据立即不再指向该树尖 |
| Arena保持独立阻塞线 | 顺手并入或重复做已有NO-GO审查 | 其原子完成/恢复/发布审计需另外的状态合同 |

## 证据与状态边界

完整索引：`docs/verification/2026-09-21-ownership-resume/README.md`。
唯一v3 Python收据：同目录 `v3/python/receipts/gate-Idx5hl80/pytest.json`。
本輪解释器全为 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。全量控制台仅末15行，2X来自控制台而非JSON；没有清洗原始ANSI/空白。旧归档完整性记录和修复前PR快照也在新目录。

工程通过不等于独立Spec/Quality。没有真实生产库读取/写入、回填、部署、8792切换、定时任务调整、外部参赛调用或树删除。生产软链仍指向bf662e9310ff；这是路径观测，不冒称重新完成生产health/live验收。三单或组合不能重复合；后续文档提交不继承47530e20的收据。

## 下一步

1. 在明确授权和时间/费用预算下，按新 `review-request.md` 对47530e20另起独立Spec/Quality；不要再拿旧e1b63b1a作为本修复的最终代码对象。
2. 合main前重核上游和真实候选；任何实际合流身份变化都需要相应新收据。作者门禁绿不自动授予合入许可。
3. 生产回填仍另验当前冻结源、完整副本、磁盘/备份、父子staging与失败不发布/恢复；本轮合成数据回归不是生产排练。
4. Arena沿#816已有NO-GO另修，旧UI/runtime/history和活跃线不重复接管；树清理另查ignored/reflog/进程引用并单独确认。

工具归位：缺口已进原helper及正式回归，不另造同功能门禁；仓外probe/runner/seal仅服务这个冻结对象并随manifest留证，不安装为长期自动调度器。
