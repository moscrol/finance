# Round-8 附加修复 QC

## 这个分支做什么
独立复核 05 `dd5d54aa` / 最终 `f8540a53`，只归档审查与探针，不修改业务。

## 决策与被否方案
- 原错配费用 summary 修复通过；否了据此最终放行：生命周期折叠和公开收据仍有两个相邻 P1。
- 两项父版本均可复现，记新增发现，不诬称 dd5d54aa 引入回归。
- 探针归 `scripts/review_probes/`；显式 check 文件不混入业务默认测试，不用 xfail 掩红。
- 详情：`docs/handoffs/2026-09-14-research-evolution-round8-addendum-qc.md`。

## 当前状态
审查与探针已提交 `e9637fb5`，本交接另提交。05 暂不签最终放行；01/02/04 保持候选。未 push、未合 main、未碰生产及主树他人改动。
R8A-1[P1]：measure.py 按 attempt_id setdefault，两个 run 复用 attempt 被折成一个，第二次缺账消失；起止事件跨 run 同形。
R8A-2[P1]：measure.py 费用派生缺口仍 OR 匹配。原错配输入的 summary 已 unknown，但 Receipt 仍 valid、unknown=[]。

## 已验证
- 干净 f8540a53：05 119 passed；全仓 ruff 绿。
- 第 3 轮 5 passed；4–7 轮 23 passed；05extra exit=0。
- 原提交回归测试父红子绿；独立检查父 4F/3P → 子 3F/4P（剩 3 红是上述两个根因，合法双身份/run-only/attempt-only 均绿）。
- 核历史全量原件：9659P/0F/77S，dirty=false，exit=0 @dd5d54aa；最终 SHA 只加 docs。四轨 HEAD/dirty 与汇报一致。

## 未验证 / 已知边界
本轮未独立跑全量、第一轮硬绑旧 SHA 脚本、06 集成/前端/E2E/registry。06 观察器本身用 run_id 派生 attempt_id，不正常生成冲突；05 公开合同仍须校验。

## 下一步
1. 执行方修两个相邻 P1，收据/汇总均加断言，保留三种合法身份对照。
2. 显式运行 `QC_TREE=<05树> <主树>/.venv-workbench/bin/python -m pytest -q -rf scripts/review_probes/check_product_value_identity.py`。
3. 复跑历史安全断言及干净代码 SHA 全量，再交 06 集成验收。

## 踩过的坑
去重前先验身份，否则下游联合校验守的是已丢行的输入。summary 门不反向修复公开 Receipt。
完整证据 `~/.finance-runtime/reviews/research-evolution-round8-addendum-qc-20260914/`。历史全量收据不含 xfailed 计数，未独立背书 2 xfailed。
