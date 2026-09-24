# 半年/全年混比漏检（分支 `fix/financial-comparison-0922`，未合）

一句话：**#835 候选仍放行「2026中报净现比0.132，较2025全年净现比1.009走弱」这类跨期别混比；
本分支把该句式补成拒句并做了撤保护验证，但 R6 四题的自然验收仍未翻案。**

- 树 `~/fwp-wt-financial-comparison-0922`，base `d82cb16b5`（#835 `fix/financial-forward-0921`，PR open 未合）
- 长文与证据：`~/.finance-runtime/reviews/financial-comparison-20260922/`（`README.md` + `summary.json`）
- 未跑付费模型审查 / 未 live / 未 push / 未合 / 未部署

## 先量后修

`probe.py` 走真实验收路径（`SemanticEpisodeVerifier.verify`，judge off/llm，socket 全禁）实测：三种写法
（完整句、省略第二个指标名、先声明「不可直接比较」再转折）修前全放行、修后全拒；契约 **10/18 → 16/18**。

## 改了什么

`intelligence/services/financial_claim_checks.py` 新增 `_relative_ratio_comparison_mismatch()`：
同一句内把前一分句**显式命名**的比率期别带给「较/相较于/相比于」分句，期别长度不同即判不一致；
走既有 `metric_evidence` 缺口与修复账，保留同句已绑定引用。

撤保护六处全杀（摘钩 18 红 / 去豁免 2 / 裸数字充锚 2 / 去「较」锚 2 / 期别只比年份 16 / 去方向词 2，
见 `mutation.json`）；并删掉一处**死守卫**（函数内重复切句，调用侧已切好，怎么变异都杀不死）。

## 读数

- 分段跑（`--ignore` 绕开 base 上的收集错误）：合计 **13352P / 85S / 2X / 0F**——**不是**文档那条命令的读数。
- 门禁在 `fix/gate-collection-0922` 修好后，两分支合起来（`verify/gate-plus-financial-0922` @ `f815c28a0`）
  跑**无任何 --ignore** 的全树：**13388P / 85S / 2X / 0F**，exit 0；收据 `scope` 全空、`collected=13475` 对平。
- 对账：13352 + 36（门禁分支新增测试）= 13388，逐条对上。
- 与 #835 收据 13305P/87S/2X 的差额未逐条对齐（环境不同），**不宣称**同口径复现。

## 明确没做到的

- **主语歧义句仍漏判**：`2026中报净现比0.132，2025全年净现比1.009走弱。`（无「较」）按「宁可漏判不误拒」放行，已写成对照用例。
- **无绑定事实的期别不查算术**：只绑 2026中报 时 `2025中报含金量为9.999` 放行。
- **自然验收未动**：旧 R6/R3 整题 0/4 不变；F2 未取真实报告、F1 免责声明误判不受本改动影响。
- 只证明「这批句式会被拒」，不证明模型答对、来源恢复或已部署。

## 下一步

1. 先合 `fix/gate-collection-0922`（门禁能产出数字是其它一切读数的前提；与本分支零冲突）。
2. 本分支合入前仍需独立终审——#835 上轮 `BLOCKED_PROVIDER_CAPACITY`（240P 后中断无报告），
   续审 `NOT_STARTED_SHARED_PROVIDER_CAPACITY`，封档 #838，至今无结论。
3. 自然四题重验只能在有独立审查预算时做，别用旧题挑绿代替。
