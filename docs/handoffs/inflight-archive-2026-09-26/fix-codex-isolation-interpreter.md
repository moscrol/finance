# fix/codex-isolation-interpreter

## 这个分支做什么
独立修复 PATH 前置虚拟环境时 Codex 沙箱探针无法启动 Python，并保留失败输出；迁移候选 b2d40776 不动。

## 决策与被否方案
- 取当前 sys.executable 的真实路径；不扩大沙箱放行目录，不靠换 PATH 躲失败。
- 追加默认兼容的解释器/返回码/截断输出字段，proven 仍需四项 denied 和成功退出。
- 比较与复现详见 docs/superpowers/specs/2026-09-12-codex-isolation-interpreter-design.md。

## 当前状态
本提交为独立清障，基线 gitea/main=6382c13b；未推送、未开 PR、未合入。代码与交接同次提交。

## 已验证
- 旧实现：参数化安装测试在 venv PATH 下红，普通 PATH 绿；0.92s。
- 修后 test_codex_headless_runtime.py：31 passed / 1 skipped；收据 20260912T103436Z-6382c13b.json（本分支未提交阶段、dirty=true，非最终门禁）。
- headless_tool_gateway + conversation_orchestrator：138 passed；收据 20260912T103637Z-6382c13b.json（同上）。Ruff 与 diff --check 通过。

## 未验证 / 已知边界
本分支未单独跑全量；统一在迁移+台账清障的最终候选验全套。watchdog 历史间歇失败未归因，不能以定向绿宣布已修。非当前主机安装位置若仍在沙箱禁止范围，保持 unproven，不自动放开目录。

## 下一步
将本提交与 docs/hybrid-ledger-dependency、冻结迁移 b2d40776 在新树组成最终候选；最终状态见仓外门禁目录 instruction-migration-clearance-20260912。合并仍需用户确认。

## 踩过的坑
主 pytest 解释器相同，不代表 sandbox 子解释器相同；command_sha256 包含临时 cwd，不能当二进制 hash。已有安装测试成为回归工具，不另造通用脚本；没有新增 harness 部件。
