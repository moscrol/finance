# 302132 回填验收：绑定真实对象与可靠失败输出

固定候选 `3736d5bf`、代码 `00d64e37`。本轮有限独立复核确认 v6 的 49/49 演练和旧干净全量收据真实，同时发现两条漏检：两轮 spec/child 一起改成其他合法股票代码仍 PASS；超大整数钉值使有限数值检查抛 OverflowError，未产生约定的 FAIL JSON。只补既有独立验收脚本和原测试；不执行生产回填，不改写入器或历史原件。

## 单一实施片

- [ ] 从 `3736d5bf` 建独占 `fix/backfill-acceptance-closeout-0920`。指定主树 venv，在全新临时目录复跑 `backfill302132-design/probe.py` 的三格：正常37项PASS、错对象仍PASS、超大数退出1且无输出。原 probe 输入不变，旧目录不覆盖。
- [ ] `scripts/verify_302132_backfill_acceptance.py::_validate_receipt()` 用已有 `CODE = "302132.SZ"` 绑定每轮授权对象；仍验证格式、父子相等、跨轮完整 spec 相等。不能仅把脚本 SQL 改为服从可伪造的 spec.code，也不增加第二份目标配置。
- [ ] `_is_num()` 对 JSON 数值的有限性判断必须是总函数：bool/NaN/Infinity/超大正负整数等返回 False，正常有限 int/float 不误拒；溢出不得逃逸。失败必须沿既有 schema 违规路径产生结构化 FAIL 和 rc=2，且跳过依赖无效 schema 的数据计算，不靠最外层吞异常假造成功。
- [ ] 在 `tests/test_repair_backfill_stock_history.py` 补真实验收 CLI 反例：apply/verify/两轮同步错对象（子报告文件保持各自相等）、超大数在 stock/technical/window 等既有数值入口、bool/非有限对照和正常值。保留基线及旧65项验收测试，不改 oracle 输入、源表保护、备份/独立子报告/逐轮 parquet 绑定。
- [ ] 两项定向撤回保护均应使新断言失败；恢复后用同输入通过。使用临时小库与既有 fixture，不复制或改生产库、不重建真实演练库、不触冻结 parquet。
- [ ] Ruff、相关89项原模块及新增回归，pathspec 提交，正常推分支，≤3KB inflight、日期快照、外部证据 manifest。原报告“未push”改为已推只在新交接中澄清，不覆盖别人的旧树。
- [ ] 独立 Spec → Quality，再处理当前 main 合流与全叶。旧9706P和本片定向绿不等于主线准入，更不授予生产回填权限。

证据根：`~/.finance-runtime/reviews/research-closeout-20260920/backfill-acceptance-fix/`。采用 subagent-driven-development，在前一实施片两轮复核通过后串行执行。
