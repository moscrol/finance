# Workbench 记忆异常：HTTP 离线验收

## 当前结论

测试实现：`c367aa2a702e3a40bf826982c4e936a3f50b3f14`；实际受测干净版本：`78b25943fb126636f4df33255f2f6827a3f7818f`。本次续验没有改测试或运行时，只执行既有候选并归档证据。

| 层次 | 状态 | 证据与边界 |
|---|---|---|
| HTTP 故障与恢复测试 | PASS | 22P/0F/0error/0S，15.25秒，含自适应研究 off/on |
| 相关定向回归 | PASS | 24文件，824P/0F/0error/0S，66.98秒；包含上面的22项，不能相加 |
| 收据身份与范围 | PASS | 两份收据校验均exit0；同SHA、解释器、依赖指纹、dirty=false，收集数与结果对平 |
| 全仓 Ruff | PASS | `validation-78b25943f/ruff.log.txt`，exit0 |
| 当前候选四叶门禁 | UNKNOWN | 本次未执行全仓/前端/E2E/registry四叶；旧`698fd172d`四叶不移签 |
| 生产装配、真实模型采用、金融质量 | UNKNOWN | 无真实模型调用，未做部署服务或浏览器验收 |
| 合入、生产发布 | BLOCKED | 未push、开PR、合main或部署；尚待对应验收及授权 |

本轮先取得资源准入，再顺序执行HTTP与扩大回归。两次归档准入观测均未发现其他pytest，磁盘空闲高于12GiB阈值；这只是时点采样，不是全机锁或性能测试。两个测试进程均结束，无本任务后台等待器。

## 已验证的场景

所有HTTP场景分别固定`WORKBENCH_ADAPTIVE_RESEARCH=off/on`，不继承会话环境。既有同用户命中、跨用户隔离、撤回三例保留；公用断言验证真实Episode身份、证据哈希、可选先验槽和非市场事实声明。

- corrections/judgments台账损坏：坏JSON或非对象行均显示unavailable而非empty；有效纠偏不能掩盖损坏的另一台账，源文件不变。
- 读取异常：首请求显示unavailable，不暴露异常私有标记；移除故障后下一空会话恢复召回。
- 两个读取超时后第三请求busy：同步事件保持线程阻塞，provider边界先于读取完成；释放后旧Episode未被迟到结果改写，新请求恢复召回。测试独立线程池结束时等待线程退出。
- 写入权限错误与磁盘满：实际`Path.open`追加边界注入故障；失败trace仅含有界字段，run留降级，研究仍到provider边界，无假成功行；恢复后可写，顺序重复不多写，再开空会话能读到。

顺序重复不证明并发去重；测试线程释放与回收不证明能硬取消真实卡死的磁盘IO。TestClient仍是进程内HTTP，上一条完成答案是合成夹具；无回答模型替身只验证送达，不验证采纳或金融答案。所有用户、会话、run、Episode及部署台账均位于临时根，网络与模型工具执行守卫通过。

## 收据与复现

本次原件均在`validation-78b25943f/`：

- `20260925T102917Z-78b25943-22a739a4167f.json`：HTTP单文件22P。
- `20260925T103514Z-78b25943-5a23162f5d8c.json`：24文件824P，完整文件列表见`target`。
- `http.log.txt`、`regression.log.txt`：原始测试输出。
- 两份`*-receipt-check.log.txt`：在受测干净SHA上执行`check_test_receipt.py --expect-revision 78b25943fb126636f4df33255f2f6827a3f7818f`，均exit0。这是指定文件集的范围核对，不是全仓`--require-full-scope`认证。
- `admission-http.json`、`admission-regression.json`：启动前准入记录；`manifest.json`核对本次9件原件字节。

解释器为`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，依赖指纹`e1c50cb821a30f00`。运行环境只保留HOME与受控PATH，umask022；`FORESIGHT_USERS_DIR`、`FWP_TEST_RECEIPT_DIR`和`--basetemp`使用`/tmp/architecture-http-validation-78b25943f.3dbLzZ/`下相互独立的HTTP/回归目录。pytest使用`-q -p no:cacheprovider`，未用`-k`、`--ignore`或提前退出筛选。

重跑须先资源采样，再从收据`target`读取实际文件集并使用新的临时根。收据只签实际受测`78b25943f`；后继文档HEAD不移签。上轮`c367aa2a7`仅有静态检查的状态不是过去已经跑过测试。

## 历史阻塞与生产边界

本目录根部的`manifest.json`、`admission-01.json`、`admission-02.jsonl`、`admission-03.jsonl`仍是上一轮原件，记录09:27:36Z至09:32:03Z五次资源拒绝和当时pytest未启动。原件不改写；本次准入与通过记录另存子目录。

根部`health.json`、`readiness.json`亦为上轮有限字段记录，不是完整HTTP响应：09:28Z health200/healthy，未认证代码身份；readiness15.013秒超时。当前续验未再采样，生产readiness仍UNKNOWN，不将历史200外推成现在就绪。

上轮fetch主干`64847b7a173bfb7191012638e8ec044ea31e0513`比已整合`9d5b9800a`多两次提交、三份文档，文本预检无冲突；本次未fetch或再merge，不认证此刻主干漂移。#76 L6判官不可用由相邻owner管理，不借其预算或改变配置。

下一步是验收方冻结实际待合入候选、复核届时主干、取得对应四叶及用户确认；生产数据/索引/发布前置与真实Workbench、CLI、金融质量另验。阶段C跨日稳定性与D配对优化尚未完成。

历史决策：`docs/handoffs/2026-09-25-workbench-memory-faults.md`。旧整合门禁：`docs/verification/2026-09-25-architecture-main-integration/README.md`。
