# 研究求证候选：输入边界复验

## 裁定

继续阻塞行为验收，不启用 `FINANCE_RESEARCH_REASONING`，不合 main、不切 8792。
本轮修的是可确定性验证的输入限制及规则适用范围，未证明研究质量改善。
前一轮记录原样保留于 [09-20 验收](2026-09-20-research-reasoning-awareness.md)。

## 发现与修改

1. 原始供需题的“只分析以下虚构材料，不查其他资料”未被编成材料合同，
   既有注册表仍允许外部读取。现在在 resolver/controller 模型前冻结为
   fictional + material_only，能力和检索计划均为空。
   没有把全部必答槽改为 user_premise：这会绕开 E2 在途的逐句来源工作。
2. 原始“请复核刚才的解释”没被当续问，丢了旧日期及 local_only 条件。
   顶层复核声明现在复用原用户指令基底；明确允许重查时保留旧日期锚点，
   当前显式新日期优先。新主体/话题切换不能强制继承；助手原答不能恢复权限。
3. 第一版真实续问虽能交付和撤回部分归因，但重新查了五次，且替换题材数据。
   **“只用已取得的数据”不等于“可以重查本地”**。第二版把前者收窄为
   material_only，禁止新的本地读取，不接受用重查结果冒充旧快照。
4. 引号和围栏已有保护，但 `>` 引用行漏在保护外；新增整行保护及嵌套反例。
5. CR-01/02/03、SPT-A10 改成按待证主张适用：交易强弱需要盘面资格，
   经营/财务机制不强制从盘面开始；股价/成交额不能全局压过产业事实。
   两引擎共用的基线文本与 Episode 的基线说明同步修正。
6. 明示 E1 等编号只在本轮有效；保留原 unknown_evidence_ref 硬拒。
   提示不替代来源恢复，也未新增工具、预算、视角菜单或反思轮。

配套解析/基线修复不受研究求证开关控制。以后做 on/off 配对，必须使用同一份配套修复；
不能把旧 09-20 off 答卷与这版 on 答卷直接归因比较。

## 隔离运行

- 工作树 `~/fwp-wt-research-reasoning-awareness`，HEAD 基座 `83808b3a`，当时为未提交候选。
- 正式 Workbench conversations/messages 入口；复用 `intelligence.eval.live_probe` 和
  `scripts/workbench_probe.py`，没有改写用户消息/助手历史，没有 CLI ask 冒充。
- 端口 18893；V1、V2 独立用户根；均 glm-5.3-flash、研究提示 on、hybrid、max。
- helper 沿用 grounded presenter 关闭配置，不是生产展示配置的完整复刻。
- 原件 `~/.finance-runtime/reasoning-boundaries-20260921/`；第一版在根目录，第二版在 `v2/`。
  `health.json`、`candidate.patch`、代码 tar、每次 probe.log 与隔离 users 原件保留。
- V2 loaded/repo 指纹一致：`b4bcaae235316a19f09553bc4003480c9774913272c8ac5f86d1fda51a98a7c7`。
- 两版测试服务均已停止。生产前后实读仍为 `bf662e9310ff` / clean，未重启。

| 版本/题 | run | 结果 |
|---|---|---|
| V1 供需 | `run_20260921_003128_973514` | 读取合同已修正、零工具，仍因前提 basis 不匹配失败；不是完成材料交付。 |
| V1 本地行情 | `run_20260921_003128_977902` | 交付，但仍过强推断“中小市值被抽血”等，行为未过。 |
| V1 反证续问 | `run_20260921_003345_707664` | 日期/local_only 保留，未再死于未知 E1，撤回部分归因；五次重查违反只用旧数据，故拒收，不作为成功样本。 |
| V2 供需 | `run_20260921_003959_299376` | fictional/material_only，空工具/空计划，2 次模型尝试，basis_mismatch 后缺口稿；合法材料来源仍未接齐。 |
| V2 本地行情 | `run_20260921_003959_302394` | 仍断言“抛压衰竭”；把量价组合说成新增资金的证明，并将后续新增资金证据误当作可推翻“成交额本身不足以证明”的条件。未通过机制边界。 |
| V2 反证续问 | `run_20260921_004230_432838` | 真正编为 material_only，不发新工具；投影为 non_research 后被 Engine B 材料总闸挡下。公开为兜底拒答，非研究交付。 |

每版每题仅一次，V2 是看过 V1 后返修，不是盲评、留出题、重复配对或正式 T2/T3。
没有单凭 completed、提示送达或零外呼判成功。

## 自动检查

固定解释器 `~/finance-workspace-private/.venv-workbench/bin/python`。
最终定向回归 **1008 passed, 4 skipped**，收据
`~/.finance-runtime/test-receipts/20260920T163859Z-83808b3a.json`。
全仓 Ruff 与 `git diff --check` 通过。
三处进程内变异均被对应回归抓住：撤旧输入上限、撤续问意图继承、撤引用行掩码；
见 `v2/mutations.log`。未改运行中的服务源码来做变异。
全仓 Python **11989 passed, 85 skipped, 2 xfailed**，1096.70s，exit 0；收据
`~/.finance-runtime/test-receipts/20260920T165815Z-83808b3a.json`，原始日志和 JUnit 在 `v2/python-tests.*`。
这是 HEAD `83808b3a` 上本轮未提交候选的检查，不是后续干净提交或合流签字。
运行期间代码/测试文件冻结，仅完善了本轮文档；没有前端/E2E/registry 的新收据。
V2 代码包 `changed-files.tar.gz` SHA-256：
`229b80661aa4f791727912c9885c55945768fb6ab544ed9ec3c1c4ecb6e2da54`。
代码提交 `f3dc8717` 后，在干净树复验四个直接相关测试文件 **135 passed**，
收据 `~/.finance-runtime/test-receipts/20260920T170006Z-f3dc8717.json`；提交门禁全绿。
该干净收据只覆盖 135 项，不能冒充上述全仓检查。

## 下一片边界

1. `turn_control_core.project_turn_decision` 以是否需要检索决定是否研究，
   `ContinuousTurnAdapter.handle` 对 non_research 让路；材料复核虽为 research lane，
   仍被这一投影排除。应区分“需要研究交付”和“允许/需要取新证据”，不能加假检索需求。
2. 与 E2 材料来源 owner 对齐无编号题的逐句来源绑定；当前原题正文存在，但正文存在不等于
   取得 binding 资格。不复制整个未验收分支，不放宽证据门。
3. 跨轮引用须从同用户、同会话的权威 run 工件恢复原始工具证据及来源/日期/口径，
   重新核验本轮范围后生成新编号，并留 old run/hash -> new ordinal 映射。
   历史助手陈述始终独立为 assistant_judgment；缺原件、跨会话、日期越界不得降为猜测。
   `outcome.evidence` 已保存原始工具条目，`EvidenceLedger` 可复用，但本轮未接继承路径。
4. 补充适用性复验，再做同版本 on/off 配对、未见题和独立语义审核。
   当前只证明输入边界修复，既没解决材料交付，也没解决模型的过强归因。
