# 工单：批次门禁与台账完整性（2026-08-27 质检产出）

- 状态：**待认领**（三件互相独立，可各自领单；P0 是真缺陷已实证，P1-a/P1-b 是门禁把不住的形状）
- 来源：2026-08-27 对 `main..gitea/main` 29 张合并 PR（#413…#444）+ 8/24–8/26 spec 批的独立质检
- 基座：`gitea/main@35e1b291`（本单在干净树 `/Users/a77/fwp-wt-qc-0827` 上写，未动主检出脏树、未动 8792/8796/8802）
- 本轮实测收据（不是推断）：
  - 全量 pytest @`35e1b291` = **6681 passed / 0 failed / 12 skipped**，收据
    `~/.finance-runtime/test-receipts/20260826T192253Z-35e1b291.json`（`env -i` + `umask 022` + `.venv-workbench`）
  - ruff @`35e1b291` = 绿
  - 身份门绕过探针：见 §P0「复现」，两条断言一红一绿
- 台账：本单**不预占号**。三件的 `R-` 号由实施方在动手当天现取，且**必须与实施 PR 同一提交写进
  `docs/prediction-ledger.md`**——理由见 §P1-b（本单报的正是「spec 引了号、台账没行」这个形状，
  不能自己再犯一遍）。

---

## P0 · 身份门的 body 改写门比 FastAPI 的 JSON 口径窄，`+json` 子类型可冒充他人身份

**这是一处真缺陷，不是流程问题。**

**事实（实证）**：`intelligence/api/auth.py::IdentityRewriteMiddleware.__call__` 判定要不要改写请求
体的条件是

```python
if "application/json" in content_type.lower():
```

而 FastAPI 0.139.0 `routing.get_request_handler` 决定要不要把 body 当 JSON 解析的条件是

```python
message.get_content_maintype() == "application" and (
    subtype == "json" or subtype.endswith("+json")
)
```

两个口径不等价。`application/vnd.api+json` 落在差集里：**FastAPI 会把它解析成 JSON 交给端点，
中间件却不改写它**。于是客户端 body 里自报的 `"user"` 原样到达端点。

复现（本轮实跑，夹具照抄 `intelligence/tests/test_api_auth.py` 的 `auth_client`）：

| 请求 | Content-Type | 结果 |
|---|---|---|
| alice 的 token + body `{"title":..., "user":"bob-beta"}` | `application/vnd.api+json` | **200，`user_id=bob-beta`** ← 身份门被绕过 |
| 同上 | 缺 Content-Type | 422（FastAPI `strict_content_type` 挡住，**不可利用**） |
| 同上 | `application/json` | 200，`user_id=alice-beta`（既有用例 `test_json_body_user_impersonation_is_overridden` 覆盖） |

**为什么现有 27 条用例没抓到**：`test_api_auth.py` 全部用 `client.post(..., json=...)`，httpx 固定发
`application/json`。夹具只走了口径相同的那一格，差集从未被触达——「夹具比现实简单」的同族形状。

**暴露面（据实写，不夸大）**：`WORKBENCH_AUTH_MODE` 默认 `off`，生产 8792 当前未开身份门，
**今天没有被利用的路径**。但这张 PR 的存在理由就是 Hosted Alpha 内测的身份门，开门那天这个洞
就在承重位上；且它是 fail-open 方向（认错身份并放行），不是 fail-closed。

**修法**：把中间件的判定换成与 FastAPI 同源的口径，不要再写第二套字符串匹配。

```python
import email.message

def _is_json_content_type(raw: str) -> bool:
    message = email.message.Message()
    message["content-type"] = raw
    if message.get_content_maintype() != "application":
        return False
    subtype = message.get_content_subtype()
    return subtype == "json" or subtype.endswith("+json")
```

同时把「无 Content-Type」这一格显式写进代码与注释：现在挡住它的是 FastAPI 的
`strict_content_type` 默认值，**不是本模块**——那是别人家的默认值，升级 FastAPI 就可能变。
建议本模块自己也把无 Content-Type 的 body 当 JSON 尝试改写（改写失败原样透传，行为不变）。

**验收**：
1. 参数化用例覆盖 `application/json`、`application/json; charset=utf-8`、`application/vnd.api+json`、
   `application/hal+json`、`APPLICATION/JSON`（大小写）、`text/plain`、缺 Content-Type 七格；
   前六格中凡 FastAPI 会解析成 JSON 的，`user_id` 必须 == token 身份。
2. **变异必红**：把 `_is_json_content_type` 换回 `"application/json" in raw.lower()`，
   `application/vnd.api+json` 那格必须红。变异前先提交实现（这条踩过两次）。
3. 同一组用例对 `_force_user_param`（query 侧）跑一遍回归，确认没顺手改坏已绿的格。

**规模**：S（一个函数 + 一组参数化用例）。**优先级**：先于任何 Hosted Alpha 开门动作。

---

## P1-a · 「收据树 SHA == main tip」是规程文字，不是可执行门禁

**事实**：`docs/workflows/acceptance-workflow.md` §3 写死了完成判据——「四件套全绿 + 收据树 SHA ==
main tip」。#444 违反了它，而没有任何东西报警：

- `feat/hosted-alpha-gate` 的基座是 `3df795cd`（#412，8/26 14:53），**不含 #413…#442 共 27 张**。
- 它的全量收据跑在分支尖 `ebca3c6b` 上：**6579 passed**。同期 main（`547653c4`）是 **6654**。
  分支基座比 main 少约 100 条测试——收据是真的，只是**证明的是另一棵树**。
- 合并后 `35e1b291` 上**没有任何收据**（`~/.finance-runtime/test-receipts/` 无该 SHA），
  批次门禁那一格是空的。本单补跑得 6681P/0F/12S（= 6654 + #444 新增 27），
  **结论是干净的**——但这份绿是事后补的，合的时候没人知道。

同族先例已在案：`acceptance-workflow.md` §4 那条 `git fetch` 注释写过一模一样的教训——
「三项验证全会通过，因为它们只校验『加载的代码 == 那个 sha』，不校验『那个 sha == 主干最新』」。
门禁这一层是同一个洞的另一半：**收据只自证跑在哪棵树，不自证那棵树是不是要合的树**。

**修法**（两件，都不改产品代码）：

1. `scripts/check_test_receipt.py` 增一个 `--expect-revision <sha>` 模式：收据里的 `revision`
   与传入 SHA 不等即非 0 退出，并把差额（收据 SHA 落后 main 几张 PR）打进错误正文。
   合并流程与 `acceptance-workflow.md` §3 都改成调它，判据从「人眼比对」变成 `exit 0`。
2. 同脚本增 `--base-drift-max N`：分支基座落后 `gitea/main` 超过 N 张合并（建议 N=5）时，
   **拒绝把分支尖收据当作合并前置**，要求 rebase 后重跑。#444 的 27 张就是这条要拦的形状。

**验收**：
1. 拿 `ebca3c6b` 的收据 + `35e1b291` 作期望 SHA 跑脚本 → 非 0，错误正文点名 revision 不匹配。
2. 拿 `20260826T192253Z-35e1b291.json` + `35e1b291` 跑 → exit 0。
3. **变异必红**：把 `--expect-revision` 的比较改成 `startswith`（只比前 4 位）→ 第 1 条转绿即视为门禁被削。
4. `acceptance-workflow.md` §3 完成判据改写为该命令，并注明 exit 0 对哪个 revision 成立。

**规模**：S-M。**注意**：这条只治「收据对不对得上树」。**不治**「合并前该不该 rebase」的判断本身——
那仍是人的裁决，脚本只负责在没 rebase 时不让分支收据冒充批次门禁。

---

## P1-b · spec 引用的台账号在 `prediction-ledger.md` 里不存在，无人报警

**事实（逐条核过 `gitea/main@35e1b291`）**：

| spec | 声明的台账号 | 台账实际行数 |
|---|---|---|
| `2026-08-24-personalized-join-kernel-design.md` §8 | `R-20260824-25` / `-26` / `-27` | **0 / 0 / 0** |
| `2026-08-24-workbench-quality-residual-ux-design.md` §9 | `R-20260824-28` / `-29` | **0 / 0** |

`-25…-27` 对应的实施 PR **#359 已于 8/24 合并**（`ada882c6`）。也就是说：一个已上主干的功能，
它 spec 里写明的三条验收判据在台账里没有落点，live 验收状态无处可查、也永远不会被「pending 太久」
这类扫描捞出来——它不是 pending，它不存在。

`workbench-quality-residual-ux` spec 第 278 行还写着「台账 `R-20260824-28`…`30` 保持 `pending`」——
`-30` 确有其行且为 pending，`-28`/`-29` 无行。**解说层在陈述一个台账层不存在的事实**（
「台账层真、解说层漂」的同族）。

另有一处重号：`R-20260821-03` 在 `prediction-ledger.md` 里**有两行**（118 行与 121 行），
内容不同、状态一 `confirmed` 一 `pending`。任何按号取状态的读法都会拿到不确定答案。

**修法**：加一个双向对账脚本 `scripts/audit_ledger_spec_crosswalk.py`，与 `registry-check` 同档
（合并前置、exit 0 自述对哪个 revision 成立）：

- **正向**：扫 `docs/superpowers/specs/**` 里所有 `R-\d{8}-\d{2}` 引用，逐个要求 `prediction-ledger.md`
  有且仅有一行同号。缺行 → 红，附「哪份 spec 第几行引的」。
- **反向**：台账每行必须能回指至少一份 spec 或 handoff（防孤儿行）。反向先跑 warning 一周，
  存量清干净再升 error——**升 error 那天要在脚本里写明生效 revision**，不要让它长期停在 warning
  （降 severity = 把决定权交给下游，下游没下限就等于没门）。
- **重号**：同号多行直接红，不给 warning 档。

**存量清理（属本单，不推给下一个人）**：
1. `R-20260824-25/-26/-27` 补行，状态照实写——#359 已合、live 未回读则为 `pending`，
   不得因为「PR 早合了」就写 confirmed。
2. `R-20260824-28/-29` 补行，`pending`。
3. `R-20260821-03` 两行判定：留后继那条、另一条改号或标注被取代，并在两处留指针。

**验收**：
1. 脚本在当前 `gitea/main` 上跑 → 红，且点名上述 5 个缺号 + 1 个重号（= 先红）。
2. 补完存量后再跑 → exit 0（= 后绿）。
3. **变异必红**：从任一份 spec 里删掉一个 `R-` 引用不该让脚本转绿（它查的是引用→行，
   不是行数总量）；反过来，往台账里塞一行谁都没引的孤儿号，反向档升 error 后必须红。

**规模**：M（脚本 S，存量对账 M——`-25…-29` 五条的判据文本要从两份 spec 里逐条抄回台账）。

---

## P2 · 记在案，本单不动手

这两条是**观察项**，写下来是为了将来出问题时能查到「当时是知道的」，不是待办：

1. **#421 把两根轴从闸降为报告**：`inherited_golden` 把「免责声明」与「概念召回」列为
   report-only，理由是免责声明属展示层全局行为（两份 28 题工件 60/60 turn 实证为 0）。理由成立。
   但代价是：**将来展示层真的开始渲染免责声明、又回退了，B1/B2/B3 不会红**。
   若展示层后续改为渲染免责声明，这条要回来重判。
2. **#444 配额的两个自陈边界**：`RunQuota` 互斥范围是单进程（模块 docstring 已自陈，
   多 worker 部署必须换共享存储）；另外 `_read_used` 对损坏 JSON 返回 0，
   即**配额文件损坏 = 当日额度清零重来**（fail-open 方向）。内测期可接受，
   开放注册前要判一次。

---

## 不要做

- 不要顺手把 `test_api_auth.py` 的既有 27 条改写成参数化——P0 只加差集那几格，
  改动面越小越容易看出变异测试杀的是哪一条。
- 不要把 P1-a 的脚本做成「自动 rebase 后重跑」。合不合、要不要 rebase 是人的裁决，
  脚本只负责在判据不成立时拒绝发绿。
- 不要在补台账存量行时顺手改别人那几行的 `status`。判据没自己复算过就别动状态列——
  这正是 `acceptance-workflow.md` §2.3「不抄执行方数字」那条。
- 不要动 8792 / 8796 / 8802。本单三件全部离线可验，没有任何一条需要切生产。
