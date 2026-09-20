# 在途交接：fix/backfill-acceptance-closeout-0920

## 这个分支做什么
收紧 302132 回填独立验收：收据授权对象必须等于实际 SQL 对象，JSON 数值校验对超大整数也 fail closed。

## 决策与被否方案
- 选择在每轮 `_validate_receipt` 绑定 `spec.code == CODE`；否掉只靠股票代码格式、父子一致和跨轮 spec 全等，因为两轮可同步伪造为另一只股票而 SQL 仍查 302132。
- 选择让 `_is_num` 捕获 `math.isfinite` 的 `OverflowError` 并返回 False；否掉最外层吞异常，因为 schema 失败应结构化 rc=2 且跳过依赖无效 schema 的数据计算。
- 测试沿用真实 CLI + tiny 30 日 fixture；否掉读取生产/旧演练产物，避免把历史收据误签给本提交。
- 展开背景与被否方案：`docs/handoffs/2026-09-20-302132-backfill-acceptance-closeout.md`。

## 当前状态
- 代码冻结：`be3f29306739ff55ac7f40adbbc9f55503c26abf`；只改验收脚本与原测试模块。
- 原 89 项全部保留，新加 15 项；本交接与日期快照单独提交。
- 未合 main、未建 PR、未部署、未跑生产回填/真实模型/API。

## 已验证
- 冻结 SHA：相关模块 104/104 PASS；两目标文件 Ruff PASS。
- 原 probe 修前：control 37P；同步伪 code 仍 37P；超大整数 rc1 且无 JSON。
- 原 probe 修后：control 37P；伪 code 与超大整数均结构化 FAIL rc2。
- 定向 mutation：撤 CODE guard 时 3/3 断言失败；撤 overflow guard 时 5 项失败；恢复后同输入 15/15 PASS。
- 证据：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/backfill-acceptance-fix/manifest.json`；manifest SHA256 见同目录 `manifest.sha256`。

## 未验证 / 已知边界
- probe 的 child 是真实写入并由独立 CLI 验收，但 parent 收据来自 fixture；不等于生产全父链演练。
- 历史 49/49 与 9706P 属于 `00d64e37`，本轮没有重跑或移签。
- 未跑无关全仓 Python/前端；本片只签 104 项相关模块、Ruff、probe 与 mutation。

## 下一步
1. root 按 Spec→Quality 顺序复核本冻结候选与证据 manifest。
2. 通过后由 root 管理 PR/合入决策；合 main 仍需用户确认。

## 踩过的坑
- 白名单 PATH 未先放虚拟环境时，pre-commit 会落到系统 Python 3.9；已用规定虚拟环境重跑并通过。
- 本轮重复排查已固化为测试与 mutation，未新增一次性脚本；失败形状已有门禁覆盖，不另写通用工具。
