# #845 冻结源码工程续验 05

## 身份与结论

- 源码全程clean：`442476f7def1013f1fadebaf6594971921147edc`，原#833不动。仅外置验证记录器/文档变更，不改产品代码或测试断言。
- **整体CHANGES_REQUIRED / 未验收**。Python完整收集面已执行但原始两条环境红；定向复验2P不得移签成无保留全量绿。新SHA E2E34P/2S成立，不再是04中的未完成状态。
- 未合并、部署、生产回填、删除工作树或重启付费独立审核。历史四自然题仍未复验，旧not_passed不翻。正式门禁沿#814，本包只记操作员工程证据。

## 发现顺序

1. 用户“继续”后复核，源码与docs树身份一致，仅上一轮自有04包/快照未提交。磁盘已恢复约28GiB，故启动有界续验；40分钟普通组帽、120秒原生组帽、2GiB下限。04包先以28bbf474b封212成员推#838并核提交字节，旧六包不改。
2. 外置`coverage_plugin.py`只分组及记录结果，不更改断言。五个已知不能嵌套Seatbelt的测试单列原生组（四个函数，其中一个两个参数）；普通组保外网阻断/禁止写主树与共享记忆。两组同clean SHA、同解释器；原生组仅收集两个指定模块，不实际运行其他42项。不要把这个分组命令说成未分组原始`pytest -q`。
3. 普通组完整结束：**12802P / 2F / 87S / 2X / 5 deselected**，pytest1283.94秒，runner1286.73秒，exit1、无自动/外部中止。原生组**5P / 42 deselected**，exit0。两组并集精确覆盖12898个收集ID，无重叠、漏项、setup/teardown/collection错误；合计**12807P / 2F / 87S / 2X**。X是既有预期失败，不算P。
4. 两F均为`test_rag_worker_keepalive.py`中RSS断言得到None。相同环境有界对照：外层sandbox下两F且`/bin/ps` exit71、Operation not permitted；无外层两P且ps正常。源文件与父b6de无差异，夹具运行临时fake RAG，不加载模型/索引。不为绿改产品或删断言。首次终端快速诊断2P未纳正式收据；`rss-outer`/`rss-native`是随后有原日志/JSON/XML的对照。**对照解释这两条失败，不抹掉原全量exit1，也不是一次新的完整通过运行。**
5. E2E首轮9P/27F、exit1：本机共享Playwright缓存目录不存在，27项均在launch阶段报缺`chromium_headless_shell-1179`，未执行页面断言。保原输出、JSON与27个本地trace哈希，不归因产品回归或某个清理者。
6. 通过锁定Playwright1.53.2的官方install，把Chromium headless shell1179下载到本轮专用外置目录（only-shell，含其ffmpeg）。仅此依赖下载允许出网，不涉及金融源/模型。记录安装命令、输出与可执行文件SHA；没有改package/lock/config。复验只补PLAYWRIGHT_BROWSERS_PATH，并换独立结果目录，同36个测试ID：**34P/2S、exit0、0 flaky、0 retry**，89.33秒。桌面/平板/手机套件都跑；两跳过为原spec设定。
7. 测试结束后runner及19851/19854服务退出。磁盘约44GiB，不删除他人目录。`analyze.py`逐阶段/测试ID/JUnit和Playwright JSON对账后产生summary.json；所有源码身份保持一致。

## 收据与边界

- 04同SHA已有六组定向1014P/4S、十五有效变异、Ruff/registry四项/台账/前端lint、typecheck、110P、build通过；本包只补Python完整面及E2E，不重签文档tip或后来main。
- 01-04旧包及父b6de结果不改；新包Git提交后再用仓内`check_evidence_archive.py`核不可变blobs。源码冻结与文档提交各记身份。
- `ordinary/collection.json`包含全收集面及选择面，`native/collection.json`包含47项中所选五项；`reports.part-*.jsonl`按原字节、整行拆分，合并与原文件hash一致，避免仓库5MiB单文件上限。拆分不是删记录。
- 原`.log`/`.py`归档为`.txt`仅改名不改字节。`sources.json`记录原件映射/分片哈希/本地trace哈希；浏览器二进制、临时DB/用户态和zip不入仓。旧run_e2e_first.py与改后run_e2e.py分别绑定两次命令，不用最终脚本冒充首次运行。
- Node26与workflow Node22差异仍在；完整工程结果带上述隔离/版本边界。尚无#814正式全绿收据、三领域独立终审、自然四题或联合树验收。不能用作者工程结果覆盖产品质量未过。

## 下一步

若继续工程闭环，先把七个环境相关ID（五个原生沙箱+两个RSS）纳入经确认的分组计划，或在正式安全测试环境跑原始全量，取得新的精确SHA完整绿记录；不得移动05原exit1。完整清单能由本包解析器复核，无需靠日志百分比推断。独立/自然验收仍分账且需授权，不自动续模型审核、不接管#814或邻线。
