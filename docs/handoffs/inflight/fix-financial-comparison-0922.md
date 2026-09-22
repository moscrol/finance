# 半年/全年混比漏检（分支 `fix/financial-comparison-0922`，未合）

一句话：**#835 前向整合候选仍会放行「2026中报净现比0.132，较2025全年净现比1.009走弱」这类
跨期别混比；本分支把这一句式补成拒句并做了撤保护验证，但 R6 四题的自然验收仍未翻案。**

- 工作树 `~/fwp-wt-financial-comparison-0922`，base `d82cb16b5`（#835 `fix/financial-forward-0921`，PR open 未合）
- 证据目录 `~/.finance-runtime/reviews/financial-comparison-20260922/`
- 授权边界：有界离线核查；**未**跑付费模型审查、未跑新 live、未 push、未合 main、未部署

## 先量后修：漏检是实测出来的，不是读代码猜的

`probe.py` 走真实验收路径（`SemanticEpisodeVerifier.verify`，judge off / llm 两种模式，socket 全禁）：

| 用例 | 修前 | 修后 |
|---|---|---|
| `2026中报净现比0.132，较2025全年净现比1.009走弱。` | 放行 | 拒句 partial |
| 同上但省略第二个指标名（`较2025全年1.009走弱`） | 放行 | 拒句 partial |
| 先写「与全年不可直接比较」再转折「但较2025全年…明显恶化」 | 放行 | 拒句 partial |
| 中报 vs 中报（可比） | 放行 | 放行 |
| 只列示且声明不可比 | 放行 | 放行 |

`probe-before.json` / `probe-after.json`：契约达成 10/18 → 16/18。

## 改了什么

`intelligence/services/financial_claim_checks.py` 新增 `_relative_ratio_comparison_mismatch()`：
同一句内，把前一分句**显式命名**的比率期别带给「较/相较于/相比于」分句，期别长度不同即判不一致，
汇入既有 `financial_claim_mismatches`，输出照旧走 `metric_evidence` 缺口与修复账、保留同句已绑定引用。

## 撤保护验证（六处守卫逐一拆掉，确认都被用例杀死）

| 变异 | 结果 |
|---|---|
| 摘掉挂钩 | 18 例红 |
| 去掉「不可比声明」豁免 | 2 例红（误拒被挡住） |
| 允许裸数字充当期别锚 | 2 例红 |
| 去掉「较」锚定 | 2 例红 |
| 期别只比年份不比长度 | 16 例红 |
| 去掉方向词要求 | 2 例红（`较2025全年存货126.81亿元上升`） |

`mutation.json`。过程中还删掉一处**死守卫**：函数内部又切一次句号，而调用侧 `claim_sentences`
已按 `。！？；\n` 切好——原写法无论怎么变异都杀不死，属多余复杂度，已移除。

## 明确没做到的（别当成已解决）

- **主语歧义句仍漏判**：`2026中报净现比0.132，2025全年净现比1.009走弱。` 没有「较」，两种读法都成立，按「宁可漏判不误拒」放行，已写进对照用例钉住。
- **无绑定事实的期别不查算术**：`2025中报含金量为9.999` 在只绑定了 2026中报 事实时放行（`probe-masking.json`）；`2026中报含金量为9.999` 会被抓。这是引用/缺口规则的范围，不在本次改动内。
- **自然验收未动**：旧 R6/R3 整题 0/4 不变；F2 未取得真实报告、F1 免责声明误判等缺陷不受本改动影响。
- 只证明了「这批句式会被拒」，**不证明**模型答对、来源已恢复或服务已部署。

## 测试

干净环境（`env -i` + `umask 022` + `.venv-workbench/bin/python`）：

- `intelligence/tests`：11449 passed, 23 skipped, 2 xfailed（851s）
- 其余收集面：1903 passed, 62 skipped（763s）
- 合计 **13352 passed / 85 skipped / 2 xfailed / 0 failed**

与 #835 收据 13305P/87S/2X 的差额未逐条对齐：两次运行环境不同（本次 `env -i` 清空了个人状态变量），
skip 数差异未追查，**不宣称**这是同口径复现。

## 门禁命令今天跑不通（与本分支无关，base 就坏）

AGENTS.md 写的等价 CI 是 `.venv-workbench/bin/python -m pytest -q`，但全树收集直接中断：

```
ERROR scripts/archive/test_kb_freshness_fix.py
ModuleNotFoundError: No module named 'check_kb_freshness'
```

`a41e86dfc` 把脚本移进 `scripts/archive/` 后，该测试的 `from check_kb_freshness import …` 失去了
`scripts/` 的 sys.path（`scripts/check_kb_freshness.py` 本体还在）。该提交是 base 的祖先，非本分支引入。
本次用 `--ignore=scripts/archive/test_kb_freshness_fix.py` 绕开并如实记账。
**影响判定口径**：任何「全量绿」的说法在修好这个收集错误前都不是用文档里那条命令跑出来的。

## 下一步（谁接都按这个顺序）

1. 修 `scripts/archive/test_kb_freshness_fix.py` 的导入（或从收集面排除并写明），让门禁命令能产出一个数。
2. 本分支合入 #835 候选前，仍需独立终审——#835 上一轮是 `BLOCKED_PROVIDER_CAPACITY`（240P 后容量中断、无报告），续审 `NOT_STARTED_SHARED_PROVIDER_CAPACITY`，封档在 #838，**至今未出结论**。
3. 自然四题重验只能在有独立审查预算时做，别用旧题挑绿代替。
