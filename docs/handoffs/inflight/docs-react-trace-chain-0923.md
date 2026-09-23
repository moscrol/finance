# #81 / #832 在途交接

## 这个分支做什么
#81 六项 trace 修复前向收口的文档载体（PR #892）；产品唯一 #832，仍 WIP。

## 当前状态
产品 `d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c` 已普通推送 #832，合流固定 main `626d8a508`，六冲突已解。候选独占树 `/Users/a77/fwp-wt-react-trace-chain-0923`（detached、干净）。文档更新 INDEX #81、QUEUE #75、六行对照/决策/收据。未合 main、未部署、零真实模型请求。
完整证据根 `/Users/a77/.finance-runtime/reviews/react-trace-chain-20260923/`，精选原件已复制到 `docs/verification/2026-09-23-react-trace-chain/`，逐文件哈希见 MANIFEST.json。

## 已验证
新头全仓 Python 14710P/0F/0E/85S/2X，exit0、5220.45秒，collected14797对平；同SHA/干净/固定解释器，--require-full-scope和独立收据校验均通过。Ruff/提交钩子、前端120单测/构建、registry五项通过（存量反向98行warning）。merge-tree exit0。迭代1797P/8S、九撤保护全被断言捕获，非新头独审。

## 决策与被否方案
四项产品实现已在#863，只保留条件删句清理/历史绝对分页增量，原七测试不删。采用main数字门与diagnostics通道，不回滚observation适配旧测试、不放宽数字判据。先投影成功再登记历史分页。文档独立，避免移动已测产品头。理由见 `docs/handoffs/2026-09-23-react-trace-chain.md`。

## 未验证 / 已知阻塞
工程准入未过：E2E首轮31P/3F/2S、次轮32P/2F/2S。次轮tablet/mobile刷新恢复仍在workbench.spec.ts:232的5秒等待失败；trace定位初始化bootstrap（tablet耗5.4秒，mobile未完成），未获稳定低负载main对照，不定为设施噪声。两轮trace/快照全留外部frontend*/test-results，12步日志哈希已核。
新头独审只排#75，未开预算；#76自然金融另授权，旧not_passed不变。09-22 K3对旧a140已有PASS_WITH_LIMITS，不能移签新头；#841归#68。

## 下一步
先定位/对照E2E初始化时延，不重跑刷绿、不只加超时；四叶齐绿后再依#75/#76授权推进。任何代码头变化重取对应收据。当前测试进程与19381/19384服务均已结束；完整Python结束后自有basetemp由门禁清理，未发磁盘中断。

## 踩过的坑
旧runtime分支全在#832，但旧树有他人删除，不强清。旧#832内09-21 inflight过时，以本入口和PR正文为准。Gitea写入超时不代表未成功；文档#892由回读确认，PR正文经issues端点写回并核对。
