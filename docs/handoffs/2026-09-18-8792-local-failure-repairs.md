# 8792 局部失败返修：保留可信交付，不降低事实门

## 背景与当前裁决

用户纠正：错误内容要拦，但不能因为局部错误把有依据的答案一起拦掉；能补证或改成有依据的定性条件则修复，不能补的说清缺口。该纠偏已由标准 CLI 写入真实用户 `linxiaoqi5111` 的 canonical corrections 台账，未验证下一次 prompt 是否实际带入。

旧代码 `3faf64fb` 的四次真实会话、零重发保留 `not_passed`：F3 运行失败，F1 删阈值后清单残缺；其余两题 report partial。本轮修复提交 `a969d30a` → **`9655b16d37b95c9f16e201cf41811c2999e1c5bf`**；独立树 `~/fwp-wt-8792-boundary-integration`，分支 `fix/8792-boundary-integration`，基线 gitea/main=0a1cb8c4。

**新 revision 工程检查通过；没有新增真实模型验收、push/PR/合 main/部署。** 生产只读 health 仍 bf662e9310ff healthy，8828 未启动。旧原件 R=`~/.finance-runtime/reviews/8792-boundary-live-20260918/`；新证据 R2=`~/.finance-runtime/reviews/8792-boundary-repairs-20260918/`，两者不混。

## 按发现顺序

1. **F3 最后一个工具名不是根因。** 原公开 trace 没有 stack，进一步读独立 episode durable `events.jsonl`，57 条最后请求为 `web_fetch(url=file:///nonexistent)`。离线用原形状复现栈：`ToolCallDigest.__post_init__ → normalize_query → json.dumps(mappingproxy)`。URL 参数被拒后，进展记账 fallback 没处理递归只读参数，导致本来可反馈给模型的单次错误扩大成整轮失败。有效 http(s) 的假 provider 异常也复现，证明不是放开文件读取能解决的事。
2. **只改投影边界。** `_mapping_for_json` 仅把 Mapping 转为新 dict，JSON 自己处理 tuple；递归冻结原件不动，任意其他对象仍 TypeError。非法 URL 不派发，模型收到 invalid_query；provider 假异常记 tool_exception；同 episode 保住既有证据/绑定并继续 finish。最初红 6F/2P，最小两文件绿 23P；后来新增拒绝任意对象测试。
3. **清单标题不证明完成。** 原 F1 删除 0.3/0.8 无依据触发条件后，只剩指标和复查日。旧 parser 把后续“缺口”与历史 09-11 一起登记。先补回归（22F/3P），再让章节在后续标题/分隔线/缺口/来源/风险提示前停止；粗体不是星号项目符号，换行字段属于同项，日期/到期/占位文字不算触发条件。
4. **不能只保住一个好项就把整份清单算完整。** 第一版 parser 仍有 1F/78P，补“每个列出的项都应完整”检查；登记仍只取单项合法部分。加强反例，把下一章也写成“若…则…”后发现普通“来源：”漏边界（1F/29P），补入。完整性提示本身不能填平缺口，重复投影不叠提示。
5. **真实 semantic verifier → adapter 的组合路径。** 删错句后以实际公开稿重算 track 表达槽，不把旧 missing_outputs 永久并入；同 session 的现有 repair loop 能请求纯表达补全（工具额度 0），修好后再过门；预算用尽/仍缺条件则保留可信正文、明确缺件、partial，不假完成。最初组合红 10F/1P。修复提示明确指标/时间/可证伪条件、不得编数字阈值，合成槽不要写进 bindings。
6. **修复失败不能撤销已核验稿。** 追加修复异常、复验异常两种回归，4F。异常路径只可恢复同轮最后已成功核验的公开答案；新候选未经复核不能露出。身份、结构完整性、取消与非空边界仍查；公开脱敏、材料交付复查和领域告知仍施加。失败与恢复来源都留私有记录；恢复本身失败也不放行。
7. **全量抓住定向测试漏掉的公开出口。** a969 的干净全量 **1F/11676P**：新恢复函数 `public_answer=answer` 绕过统一 `session_projection.view()`。没有放宽架构断言，而是接回 view、在既有出口登记表新增这个真实调用者；49 项定向通过后提交 9655。新干净全量重新跑，11677P，不借首轮收据。
8. **原件离线重放 + 反证。** 原 F1 授权写从历史误收 2 条变为 0 条；原 live 阳性仍 1 条且 due=10-21；退出都 0。F3 仍拒 file URL 但进展可序列化。八处逐一撤保护均业务 exit1，磁盘源码 hash 不变。不能说旧 live 因此翻绿。

## 方案比较

| 选择 / 备选 | 评价 | 裁决 |
|---|---|---|
| JSON 边界复制 Mapping | 保住不可变原始合同，错误形状可正常记账 | 采用 |
| 全局解冻 / `default=str` | 削弱共享参数约束或把未知对象伪装成合法文本 | 否 |
| 同 session、同根预算修复 + 再核验 | 复用证据和权限，纯表达不另开工具 | 采用 |
| 关事实门 / 放宽数字 / 重发挑绿 | 把失败藏掉，不解决可靠交付 | 否 |
| 只留核验成功的前稿 + 显式 partial | 安全与可用性并存；回滚的是表达，不是完整性裁决 | 采用 |
| 异常时露出最新候选 | 借旧收据给新断言授权 | 否 |
| 全拒答 / 全禁写 | 负例可能绿、阳性却被毁；用户已明确否定 | 否 |
| 重新造研究/登记入口 | 旁路既有 budget、opt-out、session 与审计合同 | 否 |

可迁移原则：**事实核验和任务完整性是两道独立检查。删除一个错误断言不会让邻居自动失效，也不会让任务自动完成。恢复已核验状态不能升级未核验新状态。**

## 验证与保留的仪器错误

权威收据 `~/.finance-runtime/test-receipts/20260918T034028Z-9655b16d.json`：干净精确 revision、Python 3.12.13、标准 venv、依赖指纹 3328bed61f3e21ea，无 bypass；11677P/81S/2x/17 warnings、696.78s。fetch 后八项校验通过、base drift=0。前端 lint/typecheck/107P/build，E2E34P2S，Ruff、registry/catalog过；crosswalk98 warnings原样保留。细表/重放命令见[验证索引](../verification/2026-09-18-8792-boundary-repairs/README.md)。

- guard 测试初写缺 `semantic_verifier` 构造参数，9F；随后 wrong-frame 夹具自身违反 AgentOutcome 事件锚定合同，1F/586P。改夹具为另一 frame，不改生产约束；两次日志保留，不能算业务缺陷数。
- closure 初读 health 顶层导致 runtime字段 null；后正确读取 `health.runtime` 核得 bf662，两个记录都留。
- 敏感扫描把 Python 点分表达式当 JWT 形状；首次逐项审阅未识别两个长 import 的前缀而失败，后按实际 import AST 核销，未决 0。只对这些代码词形成立，不代表全系统零泄漏。
- 代码地图 empty/refused_empty，只作入口索引；没有据空图宣称无机制。主检出、`harness-reference/BUILD.md` 都有他人改动，本轮不碰。
- 记忆图谱73节点、断言162→164（新增两条在途符号），无漂移；vault仍19 errors/17 warnings。封存器首次按整行比较lint告警，因项目笔记一行回写使旧体积告警409259→409549字节而停；保留首版脚本/读数，只归一这条已知告警的字节数再比身份，无新增/消失问题，不修旧lint。

## 工具沉淀与剩余边界

- 可复跑量具已进入仓内 `scripts/review_probes/replay_boundary_failures.py`、`run_boundary_repair_mutations.py`，不留在 /tmp；分别防“只用合成形状”和“全禁写取得假绿”。场景特定，不包装为通用 harness 工具。共享知识追加到 `contract-vs-delivery-mismatch`，harness-reference 树脏且领先，不顺手合它。
- 最终绿色测试的 semantic judge 为固定替身；纯表达 repair 用 CallbackEpisodeSession，F3 是真实 loop＋假模型。原文重放没有跑完整 verifier。两模式离线绿不等于生产判官已关或 GLM能自然写出好修复。
- 未完善任意中文/Markdown parser，不把条件形状当证据支持。隐式时间节点、默认 30 天仍是既有行为。
- 最近两期报告口径、请求截止日透传、失败用量/判官 tokens、旧 manual mappingproxy 同源性未证；保留 unknown，不能填 0 或签稳定性。
- 原 219 文件封印复核一致；本轮真实纠偏另有用户台账副作用，不宣称所有生产用户文件没变。无市场库回填、无额外清理、无生产试写。
- 下一步先独立代码复核；新真实模型验收需用户确认预算与协议，再用新身份/精确 revision/独立所有写口执行，每题一次，失败留分母。远端交付、合 main、切8792、判官开关分别授权；#770/RE06/#53/#56另线。
