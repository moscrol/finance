# 8792 公开交付与准入反事实

## 范围

本目录的 `public-delivery-v12.json` 对应v12固定run；`public-delivery-v19.json` 对应候选 `8810bac84f67ffd6179b744710f4a88f3b5c51ee` 的三个新固定run。它们都不是任意回答的正确性验证器。完整本机证据在 `~/.finance-runtime/8792-premise-market-evidence/`，包含原题、v1-v19原始工件、代码审查原件和v19 live用户根。原始失败不删除，不把新版测试收据移签给旧版或反过来使用。

`check_public_finance_delivery.cjs` 用实际 `marked` 解析器比对表头、每行公式/单位/数值及固定片段。它不证明所有解释、供应商真实性、其他运行或源码身份。原文只读；三个变异只在进程内改字符串。

```bash
node scripts/check_public_finance_delivery.cjs \
  --runs "$HOME/.finance-runtime/8792-premise-market-v19-users/probe-premise-market-v19-20260921/runs" \
  --webapp /Users/a77/finance-workspace-private/intelligence/webapp \
  --fixture docs/verification/2026-09-21-8792-premise-market/public-delivery-v19.json
```

v19实际结果：正常fixture为3/3通过；`wrong_pe`、`collapsed_boundaries`、`swapped_breadth`三个进程内变异均按预期失败。

同一命令加 `--mutation wrong_pe`、`--mutation collapsed_boundaries` 或 `--mutation swapped_breadth` 应分别失败。未命中变异也失败，不以无效替身充当反证。fixture 锁定 `marked` 15.0.12，其他版本先明确验证范围，不能偷偷更换。

## 准入守卫

脚本核对固定 SHA、已跟踪文件清洁状态、实际 import 路径和源文件哈希，禁用正常测试收据及字节码。测试本身仍执行代码，并非 OS 沙箱。使用项目解释器，在中立目录执行：

```bash
cd /tmp
env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI="$KNOWLEDGE_WIKI" \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  /Users/a77/fwp-wt-8792-premise-market/scripts/probe_premise_publication_guard.py \
  --checkout /Users/a77/fwp-wt-8792-v19-k3-review \
  --expected-revision 8810bac84f67ffd6179b744710f4a88f3b5c51ee
```

正常v19为3项通过；加 `--disable-admission` 后是实际断言失败（2失败、1通过），不是TypeError、导入失败或未收集测试。这个过程内变异只证明当前公开准入测试能抓到绕过，不证明OS沙箱或任意财务文字。首次替身签名错误另留原件，不算有效反证。

## 独立审查

v19完整Python为12044 passed / 85 skipped / 2 xfailed，前端六项通过；这些工程结果不替代公开交付审查。v19短diff K3代码复核为PASS，范围限于题设计算状态、缺单位崩溃和范围冲突修复。v19公开答案的确定性复核确认两题计算数字及行情核心数字；行情run内judge留下P3：公开句子“EDA、封测、存储、汽车芯片随后”没有绑定到该句引用的E2/E3/E4/E52，故不能把行情自由文字写成全量PASS。独立财务K3两次请求均被供应商以HTTP 400拒绝，无有效报告，记INCOMPLETE；不能用completed、judge passed或无效请求替代财务独立签字。canonical也不是第二供应商。

后续返修新增的K3边界回归在冻结v12源码中立回放为9失败、59通过；返修树定向95通过。包括历史情景和缺口延续、主体前缀与子串混并、场景数值溢出及真实第三轮合同。旧失败原件和第一版测试现金流文本替换未命中的日志均保留，后者不是有效功能反证。完整测试和独立复审必须在新候选冻结后重跑。

普通非静态PE题设未进入专用计算器；未识别数字文字仅交语义审核并记录未程序核验片段。这是持续存在的覆盖边界，不因本轮修复而变成数学保证。v19的live sidecar为18893，原三题各一次、前两题同会话、行情新会话；收尾前须确认active/queued归零。registry 的外部 `kb/rag-query` 漂移仍红。不合main、不push、不部署、不付费外审、不删除生产。
