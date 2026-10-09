# 2026-10-09 · 长河 / Dashboard 四项隔离修复

## 身份与结论

实现提交 `b4062d55b927a9c83ae996b0b0f342457b05067c`，分支 `fix/river-dashboard-evidence-1009`，树 `~/fwp-wt-river-dashboard-fix-1009`。
基于当时 `origin/main@6c1d9f5d4`，组合 Dashboard `028590984` 与联合消费者分支 `5509ecef3`；组合提交 `6bcd20f26`。

用户授权“执行 / 继续”四项修复；本轮限隔离实现与验证，**未推送、未合 main、未部署、未写生产库、真实模型请求0**。
已知反例与本机 Python / 前端工程回归通过；完整 E2E、视觉和真实金融回答验收未完成，不是发布批准。
本快照后若只提交文档，新的 tip 不能冒充下面的同 SHA 全量收据。

详细报告及原件根：`~/.finance-runtime/reviews/river-dashboard-fix-20261009/REPORT.md`，同目录 `completion.json` / `sha256-manifest.json` 记录最终身份与文件校验。
原审查仍在 `~/.finance-runtime/reviews/river-dashboard-review-20261009/REVIEW.md`；旧联合 `NOT_PASSED` 与旧真实 GLM 全文未过不改签。

## 背景与发现顺序

1. 10-09 原审查确认 Dashboard 交互、日期和证据合同有实质进步，但两处边界反例：窗外前序归档改变后旧引用仍 accepted；缺关键价格仍确认断板。长河联合分支则在模型材料准入处挤掉全部三条 D4 事实，提纲仍引用这些 ID。
2. 新树先组合候选与当时 main。唯一文档冲突保留“本集唯一作者格式”与“历史比较镜头”两侧章节；没有接管主树其他 agent 的研究流程改动。组合基线相关组62P/1F，仍红于 D10/D4 grounded 联合证人。
3. 先加入指纹五类变化与18类无效报价反例；红后修复。连续复盘顺序测试也先红后调整：覆盖和读数在前，详细读法默认折叠。
4. 再修联合准入。不是扩大窗口或截短历史：D10保持完整单块推断、已有 verified 支持每来源保留完整行；必要席位与省略说明不能共存就停止模型调用。额外边界红测试发现了来源保留及省略说明预算问题，修正后定向156P、扩大569P。组间重叠不相加。
5. 提纲与实际送达集合闭合：`answer_spec_for_registry()` 验行生成子集，原审计全集不变；composer 确定性校验、修复、展示与缺项补写完成门使用该子集，避免用全集给省略 ID 授权。
6. 提交 b4062d55b927 后干净树全仓与前端复跑；只读重现原诊断及本地真实 Chrome 交互。实际导出 evidence 与 API JSON 相等，未配置模型的隔离入口拒收并保留附件。全部预览页和服务已停止。

## 决策与被否方案

| 决策 | 替代方案 | 评价与结果 |
|---|---|---|
| 指纹绑定可见归档及前序比较依赖，版本升2 | 只改文案；只比较最终差值；只看窗口内文件 | 文案不阻止换证据，同值不同版本仍须重读。采用输入身份，旧指纹要求刷新。 |
| 缺失/非有限/非正收盘价、涨停参考价、成交额进入待核 | 只凭名单消失或正成交额确认断板 | 无法证明未封板就不能确认；保留原ST/无成交分流及正常对照。 |
| D10整块推断 + 每事实来源最低席位 | 抬12K/48KB；截历史表；D10升级事实；只保留任意来源的一条事实 | 前三者改变合同，最后一种仍能让D1代替全部D4。采用来源最低席位，同源最短完整行，再沿相关度/硬度竞争。 |
| 来源支持、原子上下文和真实省略说明共用预算 | 极紧预算静默省略说明仍调用模型；为求绿删断言 | 模型不知道覆盖不足会过度推断。联合入口放不下就确定性降级；通用registry精确单行预算接口仍保留。 |
| 模型侧子集与完整审计分离 | 全集提纲直接进入模型；用全集允许未交付ID；破坏审计只留子集 | 选前者会悬空引用，后者丢审计。采用完整行相等校验并投影子集，身份与证据原子不重写。 |
| 读数前移、详细读法折叠 | 删除说明或重做整页 | 本轮只修阅读顺序，保留合同/草稿功能；不将前移外推成完整首屏/视觉验收。 |
| 先签工程与送达，金融质量另验 | 测试绿即替旧GLM失败翻案；把已知D4元数据缺口说成已修 | 确定性测试不证明自由解释正确。既有query_basis/strict通道与Episode owned合同不在本轮修复内，保持明确未完。 |

## 实现及固定反例结果

- `river_review_history.py`：`comparison_source` 含前序日期、状态、原因、SHA256；五日窗首日09-18为120，窗外09-17从100改999，差值+20→-879时旧引用明确拒收。改写/补建/删除/损坏/同值换版本五例均过；无关09-25变化不误拒。
- `board_calendar.py`：新增 `quote_invalid` 及前端标签“行情字段待核”；缺close/pre_close不再确认断板，完整封板和完整断板对照保持。没有声称真实抽查的十条断板已判错；报价表整体缺席的旧unverified兼容路径未动。
- `answer_model.py` / `ask_synthesis.py`：固定接口替身截取联合registry为11,967字符 / 15,935 UTF-8字节，完整D10行11,216字符；三条D4送达一条（row:2）和counter:1，15条省略明确告知，提纲悬空ID=0。D4-only三条全送达。**来源保底不是完整覆盖，也不保证全部反证/缺口入窗。** JSON只压缩分隔空白，沿用原atom视图，不宣称补齐被原视图省略的provenance。
- `ReviewHistory.tsx`：覆盖→市场读数→折叠读法；增加市场读数区域可访问名称。组件专项7P；E2E代码同步展开折叠区，但完整Playwright套件本轮未运行。

## 验证与收据

证据根下：

| 检查 | 结果 / 原件 |
|---|---|
| 干净b406全仓Ruff + pytest | 21,703P / 78S / 2X / 0F / 0E，收集21,783，999.30秒；`test-receipts/gate-RWMgEdqC/pytest.json`及原始日志 |
| 收据自证 | `--require-full-scope --expect-revision b4062d55b927 --base-drift-max 0` exit0；`evidence/receipt-verification.log`；基座以本机origin/main为准，未向远端宣称刷新 |
| 同固定版本前端 | 25文件241P、ESLint/TypeScript/build通过；静态产物与构建无差异；`evidence/frontend-fixed.log` |
| registry四项+台账crosswalk | 五项exit0，反向101行仍warning；`evidence/registry-check.log` |
| 模型入口离线截取 | `evidence/admission-receipt.json`、`joint-input.json`、`d4-only-input.json`；合成库哈希不变，新模型0 |
| 原反例与真实归档只读 | `evidence/boundary-probe.json`；真实exports前后哈希一致 |
| Chrome CDP交互抽查 | `evidence/browser-*.json`；真实API+合成归档，非生产、非全套E2E |

Python统一本树`.venv-workbench/bin/python`（锁定3.12.13），Node26.0.0 / pnpm10.12.1。
Node测试设置`NODE_OPTIONS=--no-experimental-webstorage`，否则宿主实验性storage与jsdom冲突；不删除存储异常测试。
Vite仍提示579.74kB主JS大于500kB，未改提示阈值。本轮没有新skip/xfail；原自然时钟字节协议测试此次通过，但未修改其截止日夹具，不据此宣布隐患解决。

浏览器验证：默认折叠与DOM顺序、缺日保留、矩阵切换和展开/收起、导出JSON与API一致、草稿恢复/清空、仅交接坐标指纹和方法、无模型明确拒收。1280×625无整体横溢；指标顶部约y=693，**仍不在该首屏内**。未做修复版手机/平板或视觉验收；未自行启动另一套浏览器规避web-access约定，不把局部CDP证据写成完整Playwright通过。

## 未完成与接续

- **D4 `query_basis` / `strict_double_red` 在grounded通道的既有缺口未修**，D4-only同现；普通B和原生Episode的既有合同保持。owned片段核验不等于全文语义核验。
- **新真实模型/金融全文验收为0**。获准后固定候选、入口、数据与首发问题，分别验送达、利用与解释；不能靠本轮离线绿灯签旧金融失败已修。
- 完整Playwright、修复版移动/平板/视觉、远端Actions未跑；用户授权推送后需为真实合入候选补齐，不借PR77或其他分支绿灯。
- 真实窗口09-03→10-08仍10/20可读，10-08缺daily-review；24K开场日卡只交付9日、23,457字符，09-16预算省略明确。与12K registry不同链路。归档产出/补齐另安排，不能以daily-agent代替。
- 发布、生产库写入、重启、合main须另确认；最后生产health仍干净6c1d9f5d4478，加载/仓库指纹一致。

## 工具沉淀与清理

可复用失败形状已沉淀为正式测试，而不是仅留一次性脚本：指纹五类变异在`tests/test_review_evidence_handoff.py`，无效报价在`intelligence/tests/test_board_calendar.py`，准入/来源席位/省略计数/子集校验在`test_registry_joint_admission.py`，实际消费者在`test_history_d4_joint_consumers.py`。这些测试是今后的自动门禁。

一次性诊断脚本和红/绿日志归档到私有证据根，脚本头有用途、固定夹具与写入边界；未再建立依赖测试私有fixture、硬编码本机真实exports的通用`scripts/`命令。此处选择测试归位而非生产工具：目标是反例棘轮，真实数据诊断不具备可移植接口。跨项目原则续记既有`info-not-delivered-bug-pattern`，不另造平行总纲。

本轮两个Chrome页已关闭，18897/PID48768已停止；绿门禁自动删除其basetemp。修复树和证据保留，未动主仓脏文件、生产服务、其他agent交接或其他工作树。
