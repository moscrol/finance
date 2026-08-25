# 实施计划：披露扫描 P1-①——残差写手（只解释、不增删名单行）

- 日期：2026-08-25
- 母稿：`docs/superpowers/specs/2026-08-25-sector-disclosure-scan-design.md` v1.2 §8 P1 第一件
- 基线：`gitea/main@08cf07e1`（P0 #387 + P0.5 #392 已合已切 8792=`54a6f096`，冻结题两发全过）
- 同构先例：盘面包 §6.3「残差写手与 `compose`」——复用 `AskOptions.compose`，不另造 `residual_enabled`
- P1 另两件（本刀不做）：巨潮详情/PDF 抽品种金额（P1-②，先探 detail API 再立小节）；问句自定义窗口（P1-③，小刀）。P1-b（0 工具降级 vs 研究缺口分列）另单。

## 0. 一句话

名单仍由扫描包确定性给出并置顶；`status=hit` 时放模型上场**只写残差**（分层含义、集采双重性、反证、预算边界），出稿过闸：出现包外六位代码或名单行形状→整段丢弃回 P0 形状，fail-closed。

## 1. 座位（全部走现役缝，不开新洞）

| 环节 | 落点 | 现状 → 改后 |
|---|---|---|
| 开关 | `ask.py::bind_disclosure_scan_pack` | 恒 `compose=False` → `pack.status=="hit" and pack.rows` 时保留 `options.compose`，其余维持 False（partial/empty/unsupported/error 都是 P0 形状） |
| 残差输入 | `prepare_disclosure_residual_answer`（ask.py 新 helper） | 建 AskResult（`synthesis=None`）+ answer_spec（evidence=包渲染）+ 预置 `prepared_synthesis_messages`（`llm_refine.build_synthesis_messages(..., contract_guidance=残差契约)`）——prepare_existing_answer 只在 messages 为 None 时才自建，预置即生效，零签名改动 |
| 残差契约 | `disclosure_scan_pack.DISCLOSURE_RESIDUAL_CONTRACT` | 注入 system 的 contract_guidance 槽（强制契约语义；「贴错标签遵守率极低」教训在案） |
| 编排 | `conversation_orchestrator` 披露分支 | `compose=False`→现状短路（P0 纯包）；`compose=True`→走 helper，落合成路径（3079 `synthesize_prepared_answer` + `_revise_synthesis_on_warn`） |
| 出稿闸 | `gate_disclosure_residual(body, pack)`（服务层新函数） | 合成/修订后、终稿渲染前跑；违规→`result.synthesis=包渲染`（借 merge 幂等去重回 P0 形状）+ degrade + 活性 trace（零删也留痕，R-20260825-08 先例） |
| 名单保护 | 既有「裁判后合并」两点（draft/终稿） | 不动。残差=正文可被削；名单行合并在其后，天然免削 |

## 2. 闸的判据（fail-closed，宁可整丢不逐句删）

1. **包外码**：残差里的六位代码（`(?<!\d)\d{6}(?!\d)`，防公告 ID 内嵌匹配）必须 ⊆ rows∪excluded∪counter 的码集，否则整丢，`disclosure_residual_dropped:unknown_code`。
2. **名单行形状**：残差含 `^\d{6} 【` 行（复写名单/造双名单）→ 整丢，`disclosure_residual_dropped:roster_line`。
3. **预算**：>1600 字符→声明式截断（截断说明排在被截内容之前不可行——残差是尾段，改为截断处留「（残差超预算，已截断）」）。
4. 空残差不是违规：合成失败/空 → 正文回包渲染，走现役 fallback，不加新 degrade（synthesis fallback 已有账）。

为什么整丢不逐句删：逐句删会留下指代断裂的残句（删句闸只对已注册词面负责），而残差整段的价值密度不足以值得句级修复；回 P0 形状是已验证的安全态。

## 3. 残差契约文本（要点）

- 名单已由确定性扫描包给出且会原样置顶：**不要复述名单行**。
- 只解释：各档含义（临床≠上市、合同/中选金额标题未写则未知）、集采中选量价双重性、反证行、附录词截断边界（不得把没查完说成没有）。
- 禁止：包外股票代码/公司、买卖建议、新增事实、把 excluded 升格为利好。
- 篇幅 ≤500 字，直接给解读正文。

## 4. 行为反转清单（照 P0.5 反转 G8 的先例，改测试要在计划里点名）

- `test_bind_always_disables_compose` → 改名 `test_bind_opens_compose_only_on_hit`：hit+rows 保留调用方 compose；partial/empty/unsupported 仍 False。
- 编排短路测试（源码级 `test_orchestrator_binds_pack_before_owner_fork`）不反转，补充断言 gate 调用在合成之后。

## 5. §11 五条对账（母稿核稿小注）

| # | 条款 | 状态 |
|---|---|---|
| 1 | 合并单开函数、空窗必合并 | P0 已落（`merge_disclosure_into_public_answer`），本刀不动 |
| 2 | `DO_NOT_LENGTHEN` 与 `DETERMINISTIC_OWNER_TYPES` 同步 | P0 已含 `disclosure_scan`（forecast_residual_budget.py），本刀不移出——残差走的是确定性 lane 合成，不是 episode 加长 |
| 3 | 别名表两行 + 精确板块名单板块宇宙 | P0 已落，本刀不动 |
| 4 | JOIN 取前 6 位 | P0 已落 |
| 5 | 无外呼红线 | 本刀零新增外呼（残差只读包收据；PDF 详情抓取属 P1-②，届时单独论证预算） |

## 6. 验收

| # | 判据 | 反例（挂了说明什么） |
|---|---|---|
| R1 | hit：`bound.compose == options.compose`；partial/empty/unsupported：恒 False | 空窗也开残差=模型对着空名单编 |
| R2 | 闸：包外码整丢+degrade；名单行形状整丢；干净解读原样过；超预算声明式截断 | 逐句删或静默丢 |
| R3 | 违规丢弃后终稿=纯包形状（merge 幂等不出双名单） | 双名单=合并或回退错位 |
| R4 | 残差消息的 system 含契约文本（contract_guidance 槽） | 塞进经验卡片槽=遵守率崩 |
| R5 | live（合并切码后）：冻结题公开稿名单在顶、名单行零增删、尾段出现集采双重性/反证解读 | 残差改写名单=闸漏 |

live R5 属切码后验证，不挡本刀合并；R1–R4 离线夹具全绿才可交。

## 7. 排刀

本刀（P1-①）→ 合并切码 + R5 live → P1-③ 自定义窗口（小）→ P1-② PDF 品种金额（先探 detail API 与预算）→ P1-b 分列（与品质残差线对齐后）。
