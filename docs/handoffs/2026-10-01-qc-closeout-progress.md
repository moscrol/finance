# 10-01 质检收口：实现、验证、启用分开记

## 授权与版本

用户要求推进 PR #10 收口、模型准入、四格冒烟、台账和 PR #8 内容验收边界。
本轮不合入 main、不切生产、不改模型配置、不启动 240 次实验。
用户贴出的审查摘要针对 `03d333ec0`；其链接 `/workspace/.finance-cloud/review/2026-10-01-progress-report-review.md` 在本执行环境及 Mac 均不可读，本轮只采用用户明确贴出的五点，不冒称读过全文。

核查 PR #10 时为 `6080e32c2`，fetch 时另一会话已推入语义记忆提交 `983590438`（默认关）。
本轮从后者建立独立干净工作树，分支 `fix/qc-closeout-1001`，不直接覆盖并发 PR 分支。
代码地图 query 返回 empty，未据其作架构结论；下列实现关系来自定点读取源文件。

## 1. 已补的模型证据完整性

- 修复目录有父产物就提前停止搜索的问题，始终递归查子目录。
- 沿实际 `episode_ref.episode_id` 追踪子/孙事件；路径计算复用生产 `JsonlEpisodeStore`。
- 直接读 store 事件时自动找同 store 的兄弟分支；公开 run 产物通过 `--episode-store` 显式提供 store。
- 缺子分支、坏引用和环路拒绝准入。重复输入去重，不因父运行模型正确而忽略子运行。
- `model_harness_2x2.py analyze` 强制冻结 plan，自动重读每条运行的 artifacts 及子分支；自报 admission_exit 不能代替证据。JSON 输出保存逐项判定、证据哈希和 plan 哈希。
- 边界：接入的是**实验分析/验收入口**。生产运行时未增加自动拦截；正式四格运行器尚未接通，仍需在未来每次运行完成后调用同一门禁。

新增父子覆盖测试：旧实现 8 failed / 19 passed，修后 27 passed。
新增分析入口覆盖：旧实现 6 failed，修后 6 passed。
更新旧 CLI 单测夹具，给每条模拟运行附明示的模型产物，未放宽准入规则。
以上为开发中收据，不冒充最终提交的干净树全量收据。

## 2. Mac 真实标签 A/B 及新发现

首轮使用现成脚本扫描实际 users 全范围，无 --since / --users 筛选、没有调用模型：

| 项 | 结果 |
|---|---:|
| 发现 episode | 966 |
| 重放成功 | 952 |
| 重放失败 | 14 |
| 改标签涉及 run | 158 |
| 涉及证据卡 | 568 |
| 成功部分原样 / 改标签待核 | 325 / 325 |
| 成功部分消失 / 新增 | 0 / 0 |

首轮 14 份失败中，11 份缺完整 contract，3 份在 claim source bindings 反序列化时报错。后续已证实后三份是读取器漏做嵌套解码，不是原始绑定非法，见 §7。
定点读取原文未发现这三组目标标签，但**不据此静默排除或当作重放成功**。
没有删除、修写或迁移任何真实存证。

旧脚本在上述情况下仍 exit 0，这是本次实测发现的合并依据漏洞。本轮将任一重放失败、基线范围不一致改为 exit 2；出现新增或原样臂漂移仍 exit 1。三个反例旧版全红，修后绿。输出记录输入 SHA-256 供后续同一存证对账。
**本轮不能宣布全量 A/B 通过，也不能宣称这三组标签在本样本中改善了待核数量。**
后续须给出老产物的兼容读取方案，或由验收者明确批准有依据的适用范围；不能自动补造合同/来源绑定。

## 3. 单位与报告勘误

- 保留完整旧 Linux 读数：1 failed + 1 collection error；Python 3.11 语法差异不是 Mac 全量通过的替代证据。
- 删除“min/max 在几十范围就是百分数、小于 1 就是小数”的错误判据。
- 要改变单位标签，必须有供应商定义、采集转换链、同日原值与落库值对账；无法取证就保持原状。
- 本轮未新增百分数字段变更，竞价/海外 5 日字段继续未核验，不靠极值补 `%`。
- CI 已存在；仅按实际 SHA 查询结果。没有另立本地提交前全量测试需求，也没有把旧提交绿灯继承到新提交。

## 4. 四格冒烟的真实阻塞

定点读取旧 `four-arm-20260827/scripts/react_console.py`：
- 模块文档明示“无 LLM”，循环被拆为 prepare/call/finish，由外部调用者决策；每次工具调用重建时钟预算。
- SHA-256：`3156f312a73f473ec8c48ab810a7f63ab53d288e54d0fb956f0e331e6c29a8a9`。
- 抽查 A3 / A5 的 session：有 calls、answer、code_root，但无 served_model / served_models。
- 旧 machine-truth seen/unseen JSON 的顶层为 generated_at/set/source/arms，是既有结果文件；不把“文件存在”当作新运行已能评分的证明。

| 门 | 状态 |
|---|---|
| F1，薄 ReAct × G | BLOCKED：旧控制台没有可切换的模型客户端 |
| F2，产品 × C | NOT_RUN：未启动隔离探针，未验证兼容通道 |
| F3，四格身份取证 | BLOCKED：旧 ReAct 抽样产物无身份；父子检查代码本轮已补 |
| F4，各格一题评分 | NOT_RUN：F1/F3 前提未满足 |

0165589c 首轮收口阶段没有消耗付费模型试跑额度。后续已做有界真实调用，见 §7；没有把手工答题伪装成模型臂。
下一步应先确定同一个薄驱动器、C 的确切模型及取证接口，再做四格最小冒烟。若更换驱动器/模型/版本/预算，必须冻结为新实验，不能直接归因旧 0.29 差距。

## 5. 台账与 PR #8

Mac 原子领号工具已实发 `R-20261001-01`～`07`，写入本分支 Open 表：
前五项对应既有修复，后两项对应本轮模型取证和 A/B 完整性。
均注明**事后登记、非标准四阶段分诊、非事前预注册**，保持 pending，不把代码单测通过写成生产效果 confirmed。
实验尚未开跑，未提前领取实验编号。

登记前 10-01 基线：160 行、107 pending、102 过期待处理、15 天无新增。
新登记不会消除历史 102 条欠账；未自动把过期改成证伪，也未无证据关闭历史项。
PR #8 不在本轮改动范围内，内容验收不通过就保持不部署。

## 6. 证据位置、验证与下一步

原始运行日志/产物只留 Mac `~/.finance-runtime/qc-closeout-20261001/`，不向 Git 提交用户题面或答卷：
- `model-admission-red.log`：父子模型覆盖红测试。
- `experiment-admission-red.log`：分析入口红测试。
- `ab-completeness-red.log`：A/B 完整性红测试。
- `label-ab.json` / `.log` / `.exit`：首次原脚本 A/B；exit 0 是旧行为，不可采作全量通过。
- 最终提交的 gate、A/B 和收据另以 `final-*` 命名；执行结果以实际日志和 exit 文件为准，不在开始前预写成功。

开发迭代时四个直接相关测试文件合计 102 passed、定点 ruff 通过。
最终提交需要再跑相关回归、全仓收集与规范全量门禁；前端和 GitHub 检查以同 SHA 的真实状态为准。
合入前仍有硬阻塞：14 份重放失败的处理口径、同版本完整验证。实验阻塞独立存在，不拿其余绿灯替代。


## 7. 继续推进：同版本全量完成、兼容读取与薄驱动集成（10-01）

### 7.1 已完成的 0165589c 验证，不继承给后续新提交

- 精确 SHA `0165589ca95e3298a9c92ff209cb1d5f46ab7d94`，Mac 干净树规范全量门禁 **18,968 passed / 75 skipped / 2 xfailed / 0 failed / 0 error**，耗时 1,067.07s，exit 0。
- 收据 `~/.finance-runtime/qc-closeout-20261001/final-gate-receipts/gate-UIqnIzcb/pytest.json` 经 `check_test_receipt.py --require-full-scope` 验证：收集 19,045 条，收执相等，无缩面，解释器/依赖/版本/干净状态一致。
- 同 SHA GitHub PR #11 的 python/frontend/e2e/registry-check/workbench-check 五检查均 SUCCESS。
- 真实待重判队列前后 SHA-256 均为 `edd22d9cd4694bdb405091540d3270e883e5471edcd76fb65eb89d0faaa525a8`。字节一致，当前同一内容 7,385 行。`R-20261001-05` 据此 confirmed，范围只限本次测试，不扩张为将来不会污染的保证。
- 后续改动先放独立继续树，未用未提交实现替换这次全测的受验树。下述新实现需要新 SHA 的验证；不能继承这里的 18,968P。

### 7.2 三份老存证恢复，仍不抹掉另外十一份

`judge_loss_point_replay._rebuild_outcome` 原来只将外层 list 转 tuple，内层 claims 仍是 dict，触发 `invalid claim source bindings`。现在复用生产 `ClaimSourceBinding.from_dict`，同时恢复材料锚点和历史助手来源；不删除 claims，不改原件，不补造合同。

- 合成测试先红 **2 failed / 5 passed**，修后 **7 passed**。材料来源、历史助手来源无损 round-trip；非法 kind、空引用、非法坐标、字符串 claims 仍拒绝，旧无 claims 仍兼容。
- 开发树真实 A/B **966 扫描 / 955 重放成功 / 11 失败，exit 2**；相对 016 的三份已恢复。全部 966 个输入 SHA-256 一致。
- 改标签仍涉及 158 run / 568 卡；待核 325 → 325，新增 0、消失 0、原样臂漂移 0、范围差 0。旧 baseline 含 errors，仍不能以其宣称全量绿。
- 十一份已逐个核对相邻 `run.json` 的 artifact 清单：continuous-episode / answer / report 三件的字节数和 SHA-256 全部匹配。
  - 7 份：run failed，report blocked，research/business blocked、transport failed、answer missing，仅失败占位回复。
  - 4 份：run/report completed，但控制器 lane=clarify、完成步骤为 clarification，pending_task_frame 存在且 clarification_rounds=1；是澄清回复，没有研究 contract/outcome。
- 这是一份**有依据的不适用候选清单，不是已获批准的排除规则**。严格门禁仍报十一份失败。没有把 955/966 偷换为 966 个研究答案全部成功。
- 私有清单 `qc-replay-smoke-20261001/non-candidate-inventory.json`，SHA-256 `33092c7e1a6a3a92b34789ff359e1ac4a241dbaf5dabe2e9f432d14dde906bbc`；原始用户题面/答卷不进 Git。

### 7.3 薄 ReAct 有了真实模型与金融工具闭环，但尚非完整四格

新增 `intelligence/eval/thin_react.py`，**只用于评测，不接生产 runtime factory**：
- 同一个小循环接 G/C 模型适配器和同一只读工具回调，不引入产品的研究门、修复轮、分支或隐形写稿模型。
- 每个真实 model_turn 先持久化，再自动运行现有身份准入；缺证据/错配在派工具前拒绝，最后再重算一次。上层无需记得手动调用脚本。
- 工具白名单与整批预算在调用前检查；显式总时限、模型轮数、工具次数；保留真实物理 provider_attempts。模型/工具回调必须遵守剩余时限，此处不宣称能强杀任意阻塞回调。
- 已有文件拒绝覆盖；模型异常、工具异常、截断回答、晚到回复都保留失败证据，不冒充 completed。18 个合成边界测试全部通过。

真实集成分两段，均非正式 2×2 读数：
1. 合成整数工具协议探针：G=`glm-5.3-flash` 与候选 C=`glm-5.3` 各两轮，实际 served_model 与请求一致，工具调用及回答均完成、自动准入 exit 0。
2. 薄驱动金融工具探针：两模型各查询同一 2026-09-30 市场成交额问题；同一 APFS 克隆库、固定截止日期、只开放官方 `finance_query`，无网络搜索、无真实用户记忆、无生产写入。两模型同网关按启动间隔至少 90 秒串行；每模型最多 4 物理请求、4 逻辑轮、3 工具调用、90 秒，运行前 manifest 写入问题/代码/数据哈希及限额。

| 模型 | 实际模型轮 / 物理请求 | 金融工具 | 自动身份准入 | 完成耗时 |
|---|---:|---:|---:|---:|
| glm-5.3-flash | 2 / 2 | 1 次 success，1 条证据 | 0 | 11.63s |
| glm-5.3 | 2 / 2 | 1 次 success，1 条证据 | 0 | 10.70s |

上述 live 为开发阶段集成，精确源码哈希在 manifest；随后增加“后续轮缺身份不能被前轮正确身份掩盖”的更严格逐轮检查及两项单测，没有追加模型调用，不能把开发 live 冒称提交后同 SHA live。

两份公开回答均返回 14,377.22 亿元、日期 2026-09-30；这里仅记录回答与工具数据一致，**没有给正式 machine-truth 分数，也不能由此认定完整版更强**。快照前后 SHA-256 一致。原件及每次模型/工具事件在 `qc-replay-smoke-20261001/thin-finance/`。

**身份限制**：响应的 served_model 是网关自报的实际模型元数据，不是对底层权重的独立证明。`/models` 目录本身不算调用证据。当前可用两配置同 endpoint，后续正式计划若采用它们，不能沿用“不同 provider 可以并行”。

### 7.4 评分器发现与边界

指定路径 `four-arm-20260827/scripts/score_machine_truth.py` 实查为 **0 字节**（mtime 2026-09-09），不能因文件存在或旧结果 JSON 存在就说能给新答卷评分。
找到 Python 3.12 缓存字节码，SHA-256 `195ad5598432e64f9be8a0a60025f8a14d7e2df5b246ecdd2f82c9a21366ac88`，在隔离加载名下恢复可调用 scorer，复用原 `d9_mutation_check.py`：基线可判、泄漏注入翻红、剥标记翻红、合法前瞻不误伤、advisory 不入分母，exit 0。
这仅证明该哈希缓存可执行且通过这些变异检查，**没有恢复/改写空源码，没有证明所有旧分数可复算**。正式评分前须恢复可审查源码，或明确冻结和审查这份缓存的临时加载方案；不临时发明新分数绕过它。

### 7.5 剩余验收与证据定位

- PR #11 保持 draft，不合 main、不切生产；PR #8 的内容验收要求不变。
- 新实现开发回归：7 文件合计 135 passed，定点 ruff 通过；提交后须同 SHA 重跑，不拿 dirty 收据称最终绿。
- 四格仍**未完成**：薄 R 的两个模型/金融工具集成已通；完整产品 P×G/P×C 尚未隔离试跑；统一冻结题目、快照、C 选择和可审查评分器后，才跑四格评分冒烟。核心 Episode 或裸 API 均不冒充完整产品。
- 不跑 240；不根据这次新驱动解释旧 0.29 差距。历史十一份范围口径未获批准前，严格 A/B 保持 exit 2。
- 新证据根 `~/.finance-runtime/qc-replay-smoke-20261001/`：`claims-red.log`、`claims-fixed-label-ab.{json,log,exit}`、`non-candidate-inventory.json`、`transport/`、`thin-finance/`、`scorer-cache-mutations.{json,log,exit}`。新提交最终验证另用 `final-*` 保存，以实际 exit 和收据为准。
