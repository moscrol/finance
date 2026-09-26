# #84 看板集成候选

## 这个分支做什么
#812 看板修复与 #876 清理工具共用安全采样；已前向 main `3bb81b9638f9`（83ac274ea）并纳入 #903 文档（98c3ffea9）。本轮再补 macOS plist 只读兼容，不改仓外启动文件。

## 当前状态
实现载体 #895；#903 的报告已进入本枝。实际 PR head/开闭状态以 Gitea 为准，不从历史快照抄。用户要求「继续推进直到可以合并部署」，本轮推进到可合并/可发布，不扩成实际合主线或切 8792 授权。
本轮固定候选及四叶状态只读 `~/.finance-runtime/reviews/worktree-board-hardening-20260924/integration-01/{README.md,result.json}`。缺文件、未完成、dirty 或 revision != 本枝 HEAD 都不放行；旧 b26 四叶不移签。把动态结果外置，避免为回填计数再次改变受测 head。

## 决策与被否方案
- main 与报告先整合，最后统一验；否沿用旧分支绿绕过漂移门。
- 标准 plistlib 失败仅在 macOS 交系统 plutil 转二进制，stdin 用已读 bytes，stdout 再解析；否改原 plist、正则修 XML、吞异常。失败/超时/非字典仍 unknown。
- 本单是仓内 CLI，发布完整提交与同版共享模块；否顺带重启金融服务或覆盖脏主检出。
- 展开：`docs/handoffs/2026-09-24-worktree-board-integration.md`。

## 已验证
开发态定向 59P；撤 native fallback 1F、撤 dirty 保护 1F、旧版九反例9F，源码未被变异脚本改写。实机 context errors=[]，原 plist 哈希未变。以上不代最终 head 四叶，最终读数以本轮目录为准。旧 b26 的14665P等四叶留在上一轮证据根。

## 未验证 / 已知边界
12 棵 ownership 树仍各两项 tracked 删除，全部保留；#64 完整mtime/ignored/reflog/授权未重算。没有重开K3、删除真实树、关闭#812或实际合并/部署。真实库/模型/跨仓显式探针不因工程门禁绿而变成已验。

## 下一步
核本轮 result.json 与候选身份，fetch 后核漂移和 merge-tree；全部放行且用户确认才合。#812在替代实现实际合入后留指针处理；#903已被本枝吸收，只能带接替指针收口。工具可在固定检出直接运行，不需要切8792。

## 踩过的坑
XML注释里的 `--detach`：Expat拒绝、macOS接受。全局GATE_KEEP_BASETEMP会污染测试默认清理行为；本轮不设置。测试框架只释放本轮成功临时夹具，旧证据不动；磁盘3GiB止损。Gitea请求命令级NO_PROXY，超时写入先回读marker。
