# T3 值槽续检、无效裁决与边界反例 · 2026-09-19

## 结论与授权

**停合。原“待核对，实际为1.587”四例已经修复，但新反例仍失败，且没有有效的新外审通过。**
业务提交 `746b716ff95d40898697628e197fd266a9473bf6` 已推 Gitea，沿原 `q/research-data-readiness` 实现线。
完整既有工程门通过，不代表随后新探针或自然金融回答通过。未开 PR、未合 main、未部署。
末核远端 main 为 `b22ddf8b0285a952de1e6e18c04db0f4abe448e7`。

本轮用户“继续”是接续返修与验收，不包括生产切换、清理主树、解除 KB 防写或推进其他任务线。
金融自然 conversations 0、新市场取数 0；8792、夜跑、他人树、shim 封存均未动。旧自然回答 not_passed 不翻案。

## 发现顺序

1. 从干净留证 tip `58f38d89` 接续；原样占位探针仍 exit1 / 0P4F，保存在 `hedge-repair-01/original-before.*`。
2. 将两句接入真实 `SemanticEpisodeVerifier` 出口及既有同回合续修矩阵；新首红 **51F/186P**。
   槽扫描只消费自己的 `待核对`，继续检查明确后续数值；已找到正确值也不免残余扫描。
   未定位标记移到对应期别前；扫描到下一期别声明截止，参照期“为2025中报的1.2倍”另辨。
   七文件 410P 后，手工反例发现并列期别间的标记会破坏再次解析，先留 **2F/34P**，再修顺序绑定对标记透明。
3. ARL-0003 两个低等级反例也先留 **2F/5P**：无连接词“本期为零披露”及“巨潮资讯网显示…[E2]”。
   有限词表补入，不宣称任意否定/任意来源已识别。合法占位、邻期、金额/附注及 Markdown 成对保护。
   冻结前相关九文件 **715P**；变异由28扩至36组，旧有序绑定变异因返回值形状改动同步锚点/替换值，未删/换测试目标。
4. 冻结 `746b716f`，完整检查通过并推 Gitea。原六例6P，原占位四例4P，脚本及输入未改。
5. 提交累计审查 ARL-0004，依赖并 supersede ARL-0003，范围 `d38dab3f..746b716f`，1039个artifact、37个唯一测试文件。
   首次 `qc-repair-746b716f` 在 CLI 本地失败：`Prompt is too long`，合成错误、API duration 0、报告token/费用均0，无裁决。
   封存221件原件后，在新独占根 `qc-retry-746b716f-01` 对**同一字节请求/claim**补试一次；业务差异、源码、测试及三份旧裁决完整保留，历史原件路径改为已逐字节核验的清单摘要。
6. 补试模型给 `status=PASS`，但五项 required check 为 PARTIAL。原门禁拒绝：
   **`INVALID_VERDICT / failed_check_for_pass`，direct validation exit1，authority=none**。
   没有把总状态改成 CHANGES_REQUIRED，也没有把五项改PASS；没有第三次请求或放宽验证器。
   原三份有效 CHANGES_REQUIRED 未被有效的新裁决覆盖。其意见可作反例线索，不是准入凭据。
7. 原样复现模型意见，新增只读 `scripts/review_probes/check_ratio_scope_boundaries.py`。
   在精确746上 **4P/12F**；精确79对照 **8P/8F**；两次exit1、target_unchanged、0模型。
   无效裁决不代表其每条意见错误，也不能用它的“low/非阻塞”标签掩盖真实出口失败。

## 新反例：三类回归与三类既有盲区

每句原样×judge off/确定性成功替身；正确计算产物2026中报1.588、2025中报0.289。

| 原输入 | 79dba348 | 746b716f | 归因 |
|---|---|---|---|
| `2026中报含金量为1.588，行业排名第3。` | completed，无finding | partial / unlocated | 独立序号误报，新回归 |
| `2026中报含金量为1.588，同期经营现金流1,234.56亿元[E1]。` | completed，无finding | partial / unlocated | 千分位拆成裸数字，新回归 |
| `2026中报含金量为1.588，2025中报的含金量为0.289。` | completed，无finding | partial / unlocated | “的”例外跨邻期，新回归 |
| `2026中报含金量为1.587元/元。` | 错值completed、无finding | 相同 | 单位被值匹配/残余扫描同时豁免，既有 |
| `2026中报含金量实际为158.7个百分点。` | 错值completed、无finding | 相同 | 同上，既有 |
| `收入可核[E1]，2026中报含金量待核对；实际为1.587。` | 错值completed、无finding | 相同 | 跨分号不继承比率语境，既有 |

两类控制另计：单一正确比率，两版均过；原逗号占位，79失败而746通过。因此4P/12F不是同一题集比旧四例退步，也不是整体质量统计。
新增红针尚未变成通过的 pytest/CI 保护，不加 xfail、不改题；已有11988P不能覆盖随后新增的断言。

其余外审线索尚未全面复现：格式化旧标记可能再插一次；续修提示未明确要求修好后删标记；任意词表外归属/否定仍可能连坐或漏出。不得写成均已核实/修复。

## 取舍与被否方案

| 选择 | 被否方案 | 理由/剩余代价 |
|---|---|---|
| 占位只消费自身值槽，仍查后续数字 | 继续整期continue；只特判原句 | 前者免检，后者不能覆盖同类关系 |
| 先保角色/期别，不猜比率 | 任意后续数字当比率；整句删除 | 可误删独立事实；当前保守残余扫描仍有新误报，未准入 |
| 标记参与重检但不改变并列绑定 | 标记使列表解体；有标记就免检 | 幂等修复必须重验第二次解析，而非只看首稿 |
| 保留未知标记直到作者解决 | 检查器自行清除旧不确定性 | 不擅自认证，但提示送达不足尚待复验 |
| 两个独占review根、保首失败 | 覆盖同号run；自动retry直到绿 | ID须连state root使用；本轮仅两次CLI dispatch |
| 信任既有裁决验证器 | 手改PASS/PARTIAL、豁免必需项 | 自相矛盾裁决无效；意见可复现，批准权不可伪造 |
| 新红针与旧收据并存 | 工程绿覆盖行为红；放宽合同迎合实现 | 同一精确版本也可能既有套件绿、新断言红 |
| 只读探针正式入仓，一次性驱动仅归档 | 安装第二永久runner | 复用既有review/变异协议；不复制编排能力 |

## 工程检查与调用账本

精确746全量收据 `~/.finance-runtime/test-receipts/20260919T085036Z-746b716f.json`：
- Python **11988P/0F/0E/87S/2xfailed**；Ruff exit0。
- 前端lint/typecheck/build全0，组件110P；E2E34P/2S（8914/8915，隔离台账）。
- 固定三仓registry五项全0；Finance/KB/site前后干净。KB `1254224be89e2c4974350b7f3e985dbedb5dc043`，site `f606583867fe1cad8de96b06be1dd6cfe2b57e51`。
- 36组撤保护全部真实断言失败且逐项还原绿，baseline/restored-full均416P。
- 原保真6P、原占位4P；目标源码hash/导入根/前后状态均已核验。

两次外审隔离预检均1116P，不是模型自行跑测试；两根均验证1021件历史档案原字节。
request SHA-256：`ed52088dda5b401ec1289bbe225cfa2bbd8c3191ec67baa9b4ef1a768495b84f`。
两次dispatch均sonnet别名、本机配置为claude-opus-5；首次本地无API，补试信封报告claude-opus-5。
补试580.771秒，CLI报价 `$2.1568412500000003`（list估计，非结算）；真实provider请求数未知。
每次600秒/$6上限，无tools/MCP/plugins/hooks/持久session；没有自然金融模型会话。

后置只读 `scripts.agent_review.gate` 120秒工具超时、stdout 0字节，无exit code/决策；未推测耗时原因，未重跑。
直接 `validate_verdict` 已完成并明确invalid/none；不能把gate超时记成通过或另一个有效裁决。结束时无残留进程/8914、8915监听。

## 留证与接续

runtime根：`~/.finance-runtime/convergence-20260919/retention-repair/`；
本轮归档：`docs/verification/2026-09-19-t3-ratio-scope/`，681件原件/9,620,137字节；manifest绑定原始路径、大小、SHA-256，保留原始空白。
关键目录：`hedge-repair-01`、`candidate-746b716f`、`qc-repair-746b716f`、`qc-retry-746b716f-01`；总账`hedge-closeout-outcome.json`。
新写代码/说明单独diff检查；原件空白以manifest验证，不清洗或关闭门禁。旧两轮档案、三份有效裁决及超时均不变。
共享harness-reference仍有他人BUILD.md改动、领先Gitea一提交，未覆盖；通用原则回写已有记忆文章，未另建清单。

接手先原样复跑新红针和两个绿针，再将六类反例纳入既有真实出口/原预算修复矩阵：

```bash
umask 022
cd /Users/a77/fwp-q-research-data-readiness
env -i HOME="$HOME" PATH="$PATH" LANG=en_US.UTF-8 FORESIGHT_LLM_KEYCHAIN=0 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/check_ratio_scope_boundaries.py \
  --code-root /Users/a77/.finance-runtime/convergence-20260919/retention-repair/candidate-746b716f/registry-pinned/finance-workspace-private \
  --expect-revision 746b716ff95d40898697628e197fd266a9473bf6
```

预期exit1/4P12F；同目标换`check_delivery_fact_retention.py`应exit0/6P，换`check_ratio_hedge_delivery.py`应exit0/4P。
修数值角色/单位与作用域时，保留独立排名/金额/邻期对照，不能只从漏检摆向误报。
新业务SHA需重验全套并取得有效独立裁决；新审查绑定旧三份CR和本次invalid意见，别隐去历史。
完整门只签746，不移签后续归档tip；未来待合tip另验。真实conversations固定题/证据/GLM flash及5.3兜底/预算单独验，合入及生产切换仍另授权。
