# E2 单份正文、逐句判官与真实交付复验

## 状态与范围

分支 `fix/e2-material-closeout`，树 `/Users/a77/fwp-wt-e2-material-closeout`。
代码头 `be01127e7dd12ffb0398013bfbc3699d9e3ef9d0` 已推送 WIP PR #770。
最后一次应用运行时改动是 `013766102fc43248f4471ae7c7d197021ee23911`；
`be01127e` 只修诊断脚本记录层及两个测试，`intelligence/{services,runtime,api,webapp}` 无差异。
本文接续 [上一轮验证](2026-09-16-e2-material-closeout-verification.md)，不覆盖历史失败。

结论：工程改动已落地，有界真实探针仍反证语义交付未收口。**不能签收 D6/P7，不合 main、不切 8792。**
独立审查按用户决定关闭，不自动重试，也不写成独立通过。

## 按发现顺序

1. `1e4cc6b6` 已修真实 runtime 的零工具续轮义务，但三次简单题仍有双写句子漂移，以及计算句只引用问句却通过同源判官。
2. `f67833c5` 增加显式 `render_from_claims=true`：`draft` 必须为空，正文从逐句绑定排版。旧格式仍逐字匹配，精确引用、来源、basis 和必答槽检查不变。判官每条 claim 必须给严格布尔值和理由；原句/锚点/判决进入私有工件。相同原句按题区归属，不借另一题的位置。
3. `6ce17416` 同步主干后全仓通过，三次真实题却暴露模型没收到明确终局形状：漏渲染开关、错改 basis、JSON/claims 格式失败。
4. `812e74ce` 将冻结合同的完整 JSON 模板送达 writer，明确新旧模式条件；没有自动补返回值。模型开始使用新模式，但出现句尾 `**` 被拆成一句、公开材料 ID，以及声明夹带数字漏判。无编号 B 的计算被拒后只剩两条原始事实，机器仍 completed，尚未证明必答内容完整。
5. `bd6a5778` 保留 Markdown 收尾符号的原文切片；终局公开字段里的已知材料 ID/消息坐标按可修复 FORMAT 拒收，最终公开投影再过滤并重验交付。仅按冻结目录精确识别，不扫掉所有形似 `m-...` 的用户数据。补齐关键字与具名判官回调的材料 payload；规则明确声明重复数字也需本句锚点。
6. 该版受控三例对照符合预期，但自然编号题的判官说“句内已给出对应材料锚点”，实际 `material_anchors=[]`。提示词与自由理由不足以证明引用存在。
7. `01376610` 要求判官显式给 `support_kind` 与 `anchor_indexes`。程序核对本条真实锚点范围、整数类型、唯一性、历史引用条件与类型矛盾；缺字段或假锚点不能形成有效报告。`supported=false` 只能收窄结论。**这不把语义蕴含硬编码成正则，也不证明 nonfactual 分类正确。**
8. 真实编号题再次反证：一条重复 12.5% 的 `reasoning` 句无锚点，被判官当 `nonfactual` 放行，理由借了 c3。故未签收。加粗计算句与自己的锚点已正常交付；带 240/30 的另一声明这次重新绑定了来源。
9. 把重复的判官对照做成 `python -m scripts.material_claim_support_probe --live`。首版记录器用 `asdict(ModelTurn)` 深拷贝只读参数失败，四例无有效判决；该次的 `calls=0` 是记录丢失，**不能推断零外呼**。`be01127e` 改用已有 `ModelTurn.to_dict()`，调用前先记尝试，异常只记类型并重新抛出；保留首次工件，不覆盖。

## 方案取舍

| 选项 | 判断与结果 |
|---|---|
| 继续让 draft 和 claims 各写一份，再模糊匹配 | 否决：会把身份漂移掩成“近似正确”。显式单份渲染消除双写，原来源校验照跑。 |
| 宿主自动补模式开关或把 basis 全改成 user_premise | 否决：替模型篡改合同返回值。改为提供冻结 JSON 模板，返回仍严格验证。 |
| 只看全局 passed 或漂亮的理由 | 否决：自然样本已出现凭空声称锚点存在。增加逐条支持类型和本条锚点序号，保留原文/理由供复核。 |
| 对所有数字用正则断定“支持/不支持” | 未采用：数字存在、出处存在和语义支持不是同一判断，格式编号与方法说明也可能含数字。只机械核对声明使用的凭据，不假装解决语义分类。 |
| 因测试绿或三个答案算对就签收 | 否决：编号题仍能借邻句；同源判官与自然作者共享盲区。对照和自然生成两种样本均保留。 |
| 反复补抽直到全绿 | 否决：每个固定版本先定次数。新脚本记录层修复后仅完整执行一次四例，失败仍保留，不补字段、不重跑。 |
| 在脏 harness-reference 原树写工具索引 | 否决：原树 BUILD.md 属他人改动。另从 gitea/main 开文档树，KIT/TOOLKIT 候选索引提交 e2b8d99，未合 main。 |

## 工程收据

Python 均使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；全仓使用
`env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI="$KNOWLEDGE_WIKI"`、`umask 022` 与 `bash scripts/run_main_gate.sh`。
收据根 `~/.finance-runtime/test-receipts/`。不要用共享 latest 或零计数自检收据。

| 固定 revision | 结果 | 具体收据 |
|---|---|---|
| 6ce17416 | 11240 passed / 83 skipped / 2 xfailed，干净树 | 20260916T122715Z-6ce17416.json |
| 812e74ce | 11241 passed / 83 skipped / 2 xfailed，干净树 | 20260916T123959Z-812e74ce.json |
| bd6a5778 | 11258 passed / 83 skipped / 2 xfailed，干净树 | 20260916T125646Z-bd6a5778.json |
| 01376610 | 11271 passed / 83 skipped / 2 xfailed，17 warnings，609.74s，干净树 | 20260916T131707Z-01376610.json |
| be01127e | 565 passed，十个材料/协议/语义/修复相关文件的定向回归，干净树 | 20260916T131931Z-be01127e.json |

`01376610` 具体全仓收据经 `--expect-revision` 校验 exit 0，校验时记录层与两个测试已在工作区修改，校验器明确警告收据不含它们。
`be01127e` 定向收据经 `--expect-revision be01127e --require-target test_e2_material_claim_review.py` 校验 exit 0。
**没有声称 be01127e 或后续文档头重跑过全仓。** 老 SHA 的收据在新头校验会因 revision 不同失败，不得借用。

`01376610` 另通过 Ruff、registry、前端 lint/typecheck/build、107 项前端测试、Playwright 34 passed / 2 skipped。
`be01127e` 再跑 Ruff 与 registry 通过；应用/前端源码与父提交逐路径 diff 无差异，未重复前端与全仓。
测试/门禁进程均已退出，临时 8826 服务已停止。警告主要为既有 utcnow 弃用。

变异验证仅在独立 Python 进程内 monkeypatch，不修改候选树：
- 去掉已知材料坐标保护，5 个反例失败。
- 换回旧分句器，8 个 Markdown 反例失败。
- 绕过锚点回执校验，7 个反例失败。
- 记录器两个新测试修前 2 failed，修后进入 565 passed。
这些预期红的收据不能作为正常测试通过记录。

## 有界真实样本

工件根 `~/.finance-runtime/e2-material-closeout-f7950553/`。目录名是历史根，不代表当前代码 SHA。
两道固定输入：
- U：`只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？`
- N：`只依据以下材料回答。\n\n「甲本期收入240万元，本期新增订单30万元。」\n\n1. 新增订单占收入比例是多少？`
每个版本顺序 U/U/N，各建新会话，原始 run 和全部失败保留。以下 run 均有 `run_20260916_` 前缀。

| 版本 | run 尾号 | 观察，不等于验收 |
|---|---|---|
| 6ce17416 | 202042_546956 / 202144_401948 / 202228_721271 | 前两次漏开关或错 basis；第三次 JSON/绑定拒绝，仅证据不足。 |
| 812e74ce | 203331_639160 / 203421_513979 / 203552_558529 | A 修两次后 20%，声明数字弱锚点漏判；B 加粗误分句，拒计算后仅剩事实却 completed；C 12.5% 但泄露材料 ID。 |
| bd6a5778 | 204942_837668 / 205214_313029 / 205312_464868 | 均给出比例且无 ID；B 有一次 JSON 修复；C 的无锚点数字声明被判官凭空说成已绑定。 |
| 01376610 | 210901_879736 / 211030_271881 / 211133_260447 | U/U 各 1 LLM/0 工具/0 invalid，20% 且计算锚点完整；N 2 LLM/0 工具/1 invalid，格式修复后 12.5%，但 c8 借邻句且 nonfactual 漏判。 |

实际 run 根为 `users-<SHA>/<probe-user>/runs/`，不是 probe 终端打印的默认 users 路径。
对应用户：`probe-e2-claims-0916`、`probe-e2-wire-0916`、`probe-e2-boundaries-0916`、`probe-e2-receipt-0916`。
每个 run 的 `continuous-episode.json` 保存逐句 checks。最新 N：
`users-01376610/probe-e2-receipt-0916/runs/run_20260916_211133_260447/continuous-episode.json`。
其 c8 原句为“比例12.5%是对材料内两个数字的直接算术结果，若两者口径或期间不一致，该比例需相应调整。”，
`material_anchors=[]`、`anchor_indexes=[]`、`support_kind=nonfactual`、`supported=true`；reason 借 c3。
三次机器/语义/publication 都为 completed，不能覆盖这一反证。判官均同源，不是独立验收。

### 固定判官对照

`bd6a5778` 手工三例在 `claim-judge-control-bd6a5778.jsonl`，错误问句/范围锚点拒绝、正确锚点与纯范围通过。
脚本化 `01376610` 四例记录层失败在 `claim-judge-control-01376610.jsonl`，无有效判决，不计为语义结果。
修记录层后 `be01127e` 原始请求/响应/判决在 `claim-judge-control-be01127e.jsonl`，每例一次真实调用：

| 固定 case | 结果 |
|---|---|
| unbound_numbers | 明确拒绝，指出数字不在本句引用里 |
| empty_anchors | 明确拒绝，数字声明不能无锚点 |
| bound_numbers | 通过，收入/订单均有本句来源 |
| pure_scope | unavailable，返回 nonfactual 却带 anchor_indexes=[1]，违反该类型须空序号的协议 |

脚本 exit 1，三例符合预期、一例协议失败。没有把 unavailable 当成功拒错，也没有补字段或继续抽样。
该量具固定作者输入，只检验判官，不经过 Workbench，自然作者分布不同；不能代签 P7。

## 下一步与禁止事项

1. 收口 nonfactual 误分类及“删核心计算后只剩事实仍完成”的内容完整性，先冻结反例与判据，再改实现。
2. 缩小真实终局/判官结构错误，不靠自动补字段、模糊引用或放宽来源闸。当前回执类别与序号约束仍有实际格式成本。
3. 正式 P7 必须新 Workbench 会话原始 T2→T3、不重复禁令、不用失败残桩；本轮未执行。五格自然跨轮、local_only 全读取面也未完成。
4. 合并前仍须用户确认，并对当时合并候选重跑全部叶子；当前主干 db4a269a 的本机 merge-tree 无冲突不代表授权或验收。
5. 8792 最后只读核对 healthy/clean/match，revision db2963d4；由其他工作线部署，本分支未部署。不得沿用旧恢复命令。

## 沉淀

诊断脚本已在仓内，KIT/TOOLKIT 索引在 harness-reference `docs/material-claim-receipts@e2b8d99` 候选分支，未改其脏原树或合 main。
可迁移原则回写 vault `contract-vs-delivery-mismatch`：模型的解释本身也是待核验声明；程序只认证凭据形状，语义分类须另验；固定对照通过不能替代自然生成。能力现状只更新既有 capability graph 行，不另建清单。
