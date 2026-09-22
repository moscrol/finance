## 这个分支做什么
修复来源日期不一致时的事实交付、用户历史截止强制和 `local_only` 本地行情快照可见性。

## 决策与被否方案
- 统一取用户/调用方较早截止，保留 `requested`：否了只靠模型守窗，因为模型自觉不能形成权限边界。
- 只给有市场授权的 `local_only` 加窄快照工具：否了放开综合 `market_data`，避免离线入口获得联网能力。
- 日文件自身日期/质量决定历史事实，保 NULL/0：否了借 latest/meta 补历史，避免伪造当时状态。
- 证据、文本、gaps、trace、缓存一起做严格截止隔离：否了只过滤证据列表。
- 读取禁止测试记录尝试后再断言：否了把替身异常被吞误当成“未读取”。

## 当前状态
候选 `53054bfd4336bebd0d570273a58e92758fb623be`，tree `2aa8e01864722bd6a659a672e9cd76813f398eeb`。源码未漂移；证据包提交 `38ceead0e746c877acc63f0fd47e87cddc0b0519`。2026-09-22 05:08Z（13:08 CST）后针对同一 SHA 的独立 Spec/Quality retry-01 仍因 Codex usage limit 各 exit 1（无 verdict，CLI 提示 try again 16:40，未标时区），原件已归档；结论仍 `AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED`。新 K3 未启动。2026-09-22 晚（S1 会话 #63 收尾）：上述 retry-01 原件与配套文档当时只改了 `manifest.json`、未重生 `sha256-manifest.txt`，本轨补齐（172→181 条）后提交为 `4ac4ad0f9`，`check_evidence_archive.py --revision 4ac4ad0f9` ok 181/181；分支已推送 gitea（`gitea/fix/market-date-advisory-0921` == 本地 tip），仍无 PR/合main/部署/生产写入。独立审查树 `~/.finance-runtime/reviews/market-cutoff-independent-53054bfd4-tree-20260922` 仍是 53054bfd4 的干净 detached 快照，未动。

## 已验证
Python：Ruff 0，12594P/87S/2X/17 warnings/0F/0E；精确收据 `20260921T185949Z-53054bfd.json` 与 JUnit 一致。前端 110P、E2E 34P/2S；registry 五项 0；原 24/24 变异捕获。授权单层撤 guard 仍被最终过滤挡住；双层撤 guard 1F 且被捕获。归档敏感扫描 184 位置/27 唯一值/未分类 0。

## 未验证 / 已知边界
真实 Workbench 仍未接受；市场题误路由、PIT/完整自然语言截止、后来 main 组合、浏览器业务、夜跑和生产效果均未验。旧 K3 runner 及新目录旧身份副本禁止直接执行。本轮不再重试、不换账号/模型、不把额度失败改写为审查结论；retry-01 归档于 `docs/verification/2026-09-22-market-cutoff-followup/raw/53054bfd4/independent-retry-01/`。外部验证目录 Ruff 的 `来源可追溯` 是历史 fixture 裸文本，不是候选仓库门禁结果。

## 下一步
新归档已按 Git blob 核验（`4ac4ad0f9` 上 181/181；此前 172/172，旧包250/68/200也通过），共享记忆已回写且只保留存量26 errors/17 warnings，进程和19651/19654/19276端口已退出。待额度恢复、独立审查可用且主线核对后，重新绑定准确 SHA 的 K3 writer/GLM judge，走真实 conversations/messages 两原题复验。

## 踩过的坑
完整 Python runner 启动不等于 pytest 已启动；必须看 `resource_admission` 和子进程收据。敏感匹配不能按 token/JWT 形状泛放行，必须逐位置核上下文。收据、候选 SHA、归档包和主线合并状态不能互相移签。

详见 `docs/handoffs/2026-09-22-market-cutoff-followup.md` 与 `docs/verification/2026-09-22-market-cutoff-followup/README.md`。
