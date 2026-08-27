# 设计：用户主框架视角落地（慢变量从纠偏流水账搬进画像）

日期：2026-08-19
状态：设计稿，待用户审阅
权威来源：`docs/learning/perspective-lab.md`；`docs/superpowers/specs/2026-07-03-perspective-lab-design.md` §2.5、§16
现有实现：`intelligence/services/perspective_lab.py`；注入点 `intelligence/services/ask_synthesis.py:804-836`；连续引擎 `intelligence/runtime/continuous_turn_adapter.py:435-439`；检索侧 `intelligence/services/retrieval_planner.py:111-168`

## 0. 一句话结论

用户的金融解读视角是**慢变量**，现在错放在 `corrections.jsonl`（滚动流水账）里，已被后来的工程类纠偏挤出注入窗口。本 spec 把它搬进为慢变量设计的容器 `user_framework` 画像，并用**差分声明**表达对 KOL 框架的继承关系——不合并、不复制，保留继续蒸馏与独立归因的能力。

## 1. 目标与非目标

### 1.1 目标

- **主线（2026-08-19 用户对齐后新增）**：把两位 KOL 的**判读方法**（怎么读数据）切出来内置为领域基线，默认生效、贴数据块；**判断倾向**（怎么下注）留 persona 层显式开关。判读方法关掉产品就退化成查数机器人，倾向关掉只是少个观点——这是分层依据。清单已产出：`docs/learning/reading-rules-inventory-2026-08-19.md`。
- 在用户空间建立 `user_framework` 画像，使方法论级判读常驻而非滚动。
- 把 KOL 框架的继承关系写成**差分**（采纳 / 采纳结构但阈值待定 / 我自己的），血缘可追。
- 全程不破「事实层与认知层分离」（`docs/learning/perspective-lab.md:12-14`）。

### 1.2 非目标

- **不翻全局默认视角模式**，且**不再需要翻**。原初稿把「默认开视角」当作待议项；对齐后判读方法走领域基线层（默认生效），persona 层保持显式开关即可满足需求。`intelligence/api/app.py:1114/1160` 的 `neutral` 默认保持不变——`perspective_lab.py:621` docstring 明写「默认行为必须逐字节不变」，翻它会移动所有基线读数。
- **不把 KOL 画像内容复制进 `user_framework`**。理由见 §3.3。
- 不改 `corrections.py` 的 `DEFAULT_RESIDENT_LIMIT`，不给 corrections 加相关性召回（那是另一个 spec 的事，且会改所有用户的注入体积）。
- 不动 `episode_semantic_verifier`、不动 8792、不动 finance 主库、不做 P3 角色胜率。
- **不由 agent 撰写用户框架的内容**。见 §5 的人机分工红线。

## 2. 术语

| 词 | 含义 |
|---|---|
| 慢变量 | 方法论级判读规则，跨题材跨日稳定。应常驻画像，不该每次现场重算。 |
| 快变量 | 单次纠偏、单题材观察。归 `corrections.jsonl` / `experience_cards.jsonl`。 |
| 差分声明 | `user_framework` 中对外部框架的采纳记录：采纳什么、改了什么、拒绝什么。 |
| 继承 vs 复制 | 继承＝声明采纳并可 override，血缘保留；复制＝抄一份，血缘丢失。本 spec 取前者。 |

## 3. 现状（全部 [实测] 2026-08-19）

### 3.1 注入管线是通的

- `ask_synthesis.py:804-809` → `perspective_lab.build_runtime_context`；`:867` 拼进合成 prompt；`:1700/1933` 进 composer。
- `continuous_turn_adapter.py:435-439` — continuous 引擎同源注入。
- `retrieval_planner.py:111-168` — `perspective_active=True` 会改变强制 provider 集合，即视角同时影响**检索**与**合成**。

### 3.2 但今天等于没有

> **[更正 2026-08-19]** 本节初稿写「画像一份没建」是**错的**——那是在仓内路径
> `intelligence/users/` 查的，而运行时根不在仓里。真身在
> `/Users/a77/.local/share/finance-workbench/users/default/perspectives/profiles/`：
> `sptfei.json`（SPT-Molmansk，4 篇，medium）与 `fengyuan.json`（风远，2026-07-17 写入）。
> 详见 `docs/handoffs/2026-08-16-sptfei-perspective-migration.md` 的「两根两身份」。
> **执行方注意**：本仓 `intelligence/users/`、`~/agent-memory/.foresight/linxiaoqi5111/`、
> canonical 根三处并存，读错根会得到相反结论。以 canonical 根 + 身份 `default` 为准
> （launcher 设 `FORESIGHT_USERS_DIR`、不设 `FORESIGHT_USER`，故 UI 身份是 `default`）。

- 两位 KOL 画像**存在**；缺的是 `user_framework`（canonical 根下无此文件）。
- `perspective_lab.py:626-627`：`mode == neutral` 或未选 id → 返回空串；API 默认即 `neutral`。
- `perspective_lab.py:109-122` 的 `user_framework` 内置画像是**占位符**（lens 描述写着「用户自己的阶段划分（可手工编辑 profile 定制）」），对照 `:123-149` 的 `kol_fengyuan`（5 个带权重的 lens + 3 条 reasoning_patterns + 4 条 risk_triggers）是填满的。

### 3.3 病灶：慢变量放在了滚动窗口里

- `corrections.py:158` `DEFAULT_RESIDENT_LIMIT = 5`；`:161-173` 按 `ts` 倒序取前 5。
- `ask_synthesis.py:825-830`：corrections **只有常驻一条路**，无相关性召回（对比 `:818-820` experience_cards 有 resident + relevant 两路）。
- 实测 27 条 corrections 全部带 `principle`，进入 prompt 的只有最近 5 条（2026-07-28 ~ 07-30），**全是工程/架构类**。用户 2026-06-29 写的三条金融判读原则（市场结构推演路径、反模板化、个股深挖第一性原理）排在 20 名开外，**已永久出局**。

结论：不是「用户没给过视角」，是**给过的视角被流水账冲走了**。补救方式不是扩大窗口（会连工程纠偏一起放大），是把方法论级内容迁到常驻容器。

## 4. 方案

### 4.1 三份画像，各司其职

| id | type | 内容 | 谁写 |
|---|---|---|---|
| `user_framework` | `user_framework` | 主坐标系：差分声明 + 用户自有判据 | **用户**（agent 只搭骨架） |
| `kol_fengyuan` | `kol_fengyuan` | 外部参考框架，可继续蒸馏 | 内置种子 + 蒸馏 patch |
| （未来）其他 KOL | `blogger` | 需 ingest 文章训练 | 蒸馏闭环 |

`user_framework` 是主坐标系，外部角色只能 challenge/supplement（`docs/learning/perspective-lab.md:151-153`）。

### 4.2 差分声明的三种形态

写进 `user_framework` 的每条继承内容必须落入一类，并在文本里自带标记：

1. `[采纳]` — 直接接受。例：证据分层顺序（盘面资金选择 > 涨价/订单/产能 > 第三方交叉验证 > 卖方观点 > 叙事传闻）。
2. `[结构采纳·阈值待定]` — 接受组织方式，拒绝未回测的数字。例：五维排序、三级信号体系 → 附「阈值以本地 `fact_*` 回测标定为准」。
3. `[自有]` — 用户独有、外部框架没有的。例：任何阈值未经本地回测不得写成硬判据；数据缺失必须显式标注、不得据以推断。

依据：用户自己在 `docs/learning/knevo-distill/q15-认知压力测试信号分层.md:176` 判定「单点阈值只是它按结构反推出来的，没有回测支撑」。整体照抄等于把未验证假设升格为主坐标系，与 `CLAUDE.md`「跑马策略处于假设验证阶段，禁止把单次观察写成定律」冲突。

### 4.3 迁移哪些既有内容

从 `corrections.jsonl` 挑出**方法论级**的条目迁入画像（原记录保留不删，画像里标注来源 ts）。候选（用户最终裁定）：

- 2026-06-29「个股判断必须先走市场结构推演路径：大盘量能与情绪 → 行业聚散度 → 板块承接与生命周期 → 同题材相对强弱 → 个股相对强度/筹码/位置 → L3 事实验证」→ `reasoning_patterns`
- 2026-06-29「反模板化：结构完整不等于高质量，必须有独立判断、非共识识别、权重排序」→ `anti_patterns`
- 2026-06-29「深挖个股必须先回答公司卖什么、解决什么产业瓶颈、处在哪一环、客户是谁」→ `reasoning_patterns`

## 5. 执行步骤

> **人机分工红线（最重要的一条）**
> agent 做**脚手架与搬运**：建画像、迁移候选、接线、测试、验收。
> agent **不得撰写或改写**用户框架的判读内容——`market_lenses` / `reasoning_patterns` / `evidence_hierarchy` 带结构与顺序语义，`docs/learning/perspective-lab.md:91-92` 明确规定这三个字段**只走人工编辑**。
> 遇到需要判断"用户会怎么读这个数据"的地方，**停下来问，不要生成**。凭空生成用户框架＝把幻觉写成主坐标系。

### 阶段 A：脚手架（agent 独立完成）

```bash
git checkout main && git pull && git checkout -b feat/user-framework-perspective

# A0 先确认根与身份（读错根会得到相反结论，见 §3.2 更正）
export FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users
ls "$FORESIGHT_USERS_DIR/default/perspectives/profiles/"   # 应看到 fengyuan.json / sptfei.json

# A1 建主坐标系画像（骨架，内容留空待用户填）——canonical 根 + default 身份
python3 -m intelligence.cli perspective init \
  --user default --id user_framework --type user_framework \
  --name "用户主框架"

# A2 确认落盘
python3 -m intelligence.cli perspective profile \
  --user default --perspective user_framework --json
```

落点：`$FORESIGHT_USERS_DIR/default/perspectives/profiles/user_framework.json`（`perspective_lab.py:196-198`），文章目录 `articles/<id>/raw/` 一并创建（`:302`）。

**已作废的原 A2 步骤**：初稿要求 `perspective init --type kol_fengyuan` 把内置种子落盘。
实际 `fengyuan.json` 已于 2026-07-17 写入 canonical 根，`init_perspective` 遇已存在会
报错不覆盖（`:298-299`）。**不要删档重建**——`docs/handoffs/2026-08-16-sptfei-perspective-migration.md:110`
明确「不要删 default 下的 fengyuan」。

**SPT 同理**：`sptfei.json` 已存在（type=`blogger`，4 篇原文，BM25 可召回），
继续蒸馏走 `perspective-workbench ingest --perspective sptfei ...`，不要重新 init。

### 阶段 B：迁移候选（agent 出稿，用户裁定）

- B1 从 `intelligence/users/linxiaoqi5111/corrections.jsonl` 逐条读，按 §4.3 标准分成「方法论级 / 单次纠偏」两堆，**输出候选清单给用户**（含原文与 ts），不直接写画像。
- B2 用户逐条裁定后，agent 按裁定结果写入 `user_framework` 画像对应字段，每条附 `（源：corrections.jsonl 2026-06-29）`。
- B3 清理占位行：`corrections.jsonl` 首行是模板占位（`"correction": "纠成什么（必填）"`）。**注意它今天并不进 prompt**（被 5 条窗口挡住），删除属卫生整理，不是修 bug——commit message 如实写。

### 阶段 C：差分声明（用户主笔，agent 只做录入与校验）

- C1 agent 生成一份**空白差分表**（三列：条目 / 分类 `[采纳]`/`[结构采纳·阈值待定]`/`[自有]` / 备注），把 `kol_fengyuan` 画像的 5 个 lens、3 条 reasoning_patterns、4 条 risk_triggers、evidence_hierarchy 逐条列出待用户勾选。
- C2 用户填完后，agent 按勾选结果写入 `user_framework`，格式遵守 §4.2 的标记前缀。
- C3 agent 校验：`user_framework` 中不得出现未标记来源的 KOL 原文整段复制（人工 review 时可 grep 对照两份 JSON）。

### 阶段 D：验收

```bash
export FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users

# D1 画像可加载、非空
python3 -m intelligence.cli perspective profile \
  --user default --perspective user_framework --json

# D2 视角能真的产出注入文本（single 模式非空、neutral 仍为空串）
.venv-workbench/bin/python -c "
from intelligence.userspace import user_space
from intelligence.services import perspective_lab as pl
us = user_space('default')   # 模块级函数，不是 UserSpace.for_user
p = pl.active_runtime_prompt(us, mode='single', perspective_ids=['user_framework'], query='双红题材怎么看')
n = pl.active_runtime_prompt(us, mode='neutral', perspective_ids=[], query='双红题材怎么看')
assert p.strip(), 'single 模式注入为空——画像没被读到'
assert n == '', 'neutral 不应注入'
print('OK 注入长度', len(p))
"

# D3 既有测试不红（解释器必须是 .venv-workbench，别用系统 python）
.venv-workbench/bin/python -m pytest intelligence/tests/test_perspective_lab.py -q
```

**D2 是本 spec 的核心断言**：它验证的是**生效值**（真的产出了注入文本），不是配置值（文件存在）。只检查 JSON 文件存在不算验收通过。

### 阶段 E：交接

- 更新 `docs/learning/perspective-lab.md`：在 §5 后补一节「用户主框架已落地」，写明差分声明约定。
- 回写 `.agent-memory/20_projects/finance-workspace-private.md` 交接记录。
- **不合并 main、不推送**，等用户确认（`CLAUDE.md` Git 红线）。

## 6. 风险与边界

| 风险 | 处置 |
|---|---|
| agent 凭空生成用户框架内容 | §5 红线；`market_lenses`/`reasoning_patterns`/`evidence_hierarchy` 人工独占 |
| 把 KOL 未回测阈值写成硬判据 | §4.2 强制三分类标记；阈值一律标「待本地回测」 |
| 建了画像但默认 neutral，仍不生效 | 属预期。启用是独立决策，见 §1.2；D2 只验证"选中时能生效" |
| 用户空间私有数据误提交 | `perspectives/` 属用户私有；提交前确认 `.gitignore` 覆盖，画像内容不含个股持仓 |
| 迁移后 corrections 与画像重复 | 画像为准，corrections 原记录保留作溯源；不做双向同步 |

## 7. 后续（不在本期）

- 视角选中的默认策略（用户级默认 vs 全局默认）——需单独决策，会动基线。
- 继续蒸馏：新文章 → `perspective ingest` → `extract-cards` → `propose-patches` → 用户 approve 时**追加判定"我采纳吗"**，采纳的往 `user_framework` 加一条差分。这是本 spec 结构的直接收益。
- P3 角色胜率分桶（`outcomes.jsonl`），依赖生产线稳定后再启动。
