# 轨道 E：验证器消融（2026-08-19）

> 代码：生产快照 `441c60f2`（#224 已上线）  
> sidecar 对照 `:8796` / 关裁剪 `:8798`；隔离用户 `verifier-ablation-ctrl` / `verifier-ablation-off`  
> 生产 `:8792` 只读 health，未切（`441c60f2` / `source_dirty=false` / pid 5199 全程未换）  
> 入口：**`POST /api/conversations` → `.../messages`**（`execution_kind=continuous_episode`）  
> 原始读数：`~/.finance-runtime/verifier-ablation-0819/`  
> 派单：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md` 轨道 E

## 题目

「基于周二的盘面数据，你认为主线是什么。今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会」

（R5 同题。第六轮对照 `110003`「昨天的反弹能持续多久」只作无据阈值活样本，不另开第二题。）

## 判定

**不回改 R5 §二第三层。** 关掉 repair 裁剪后多出来的不是闪迪 / 美光结构。领跌在裁剪开着时已经进公开稿（Yahoo 绑定 E17–E21）。本发对照臂被裁掉的是一句失效条件，不是领跌表，也不是「约2.2万亿」。

第三层「无据数字触发线是负资产，深度本身不是」仍立。本发没有放出新的发明阈值，所以「预期多出的是无据阈值」只得到方向支持（多出的 ≠ 领跌），没有再复制出 `110003` 那条 2.2 万亿。

## 方法

消融（ablation）= 只关一个零件，看少了什么。这里关的是语义核验之后的 **句子裁剪**（`_drop_rejected_sentences`），不是整条验证器，也不是 `_sanitize_public_answer`（那一层只剥工具名 / 哈希）。

最干净的对照是 **同一发的首稿 vs 公开稿**（单变量、无模型抽样差）。跨发对照会把「模型这次没写闪迪」误读成「裁剪删了闪迪」。

| 臂 | 树 | 端口 | 用户 | 裁剪 | run |
|---|---|---|---|---|---|
| 对照 | 生产快照 `441c60f2` 干净 | 8796 | `verifier-ablation-ctrl` | 开 | `run_20260819_152746_838420` |
| 关裁剪 | `~/fwp-wt-verifier-ablation` 本地补丁（未提交） | 8798 | `verifier-ablation-off` | 核验失败时直接发首稿 | `run_20260819_153251_481832` |

关裁剪补丁只改 `episode_semantic_verifier`：judge 驳回后不再 `_repair` 丢句，改为 `_completed_public` 发原稿。**零合并。**

## 对照臂（裁剪开）

- `execution_kind=continuous_episode`，`question_type=market_forecast`
- 授权：`market_data / mainline_context / news_search / web_search / finance_query / evidence_search`（与第六轮主发同形）
- 工具：`market_data` + `mainline_context` + `finance_query` + `directional_news`；证据 52 条
- `repair_attempts=0` / `repair_cycles=0`（模型修复轮没进）
- `judge_status=unavailable`（`TimeoutError`）+ issue `unsupported numeric condition without bound evidence`
- 公开稿 **保留** 领跌：`SOX -4.98%` / 英伟达 `-2.34%` / 美光、海力士、闪迪（E17–E21）
- 公开稿 **无** 2.2 万亿 / 涨停≥60 / 电子 27%
- 首稿有、公开稿没有的句子只有：

  > 失效条件：高位科技股普遍放量下杀，主线抱团瓦解，或防守方向也无法承接[E2][E6]。

  与 `answer_marker_coverage.absent = [invalidation_conditions]` 对齐。

## 关裁剪臂

- 同入口、同题、同模型 `glm-5.2`
- `judge_status=unavailable`（又一次复核超时）。这条路径 **没有走到** 补丁里的「驳回后发原稿」，issue 里也没有 `repair clip skipped`
- 公开稿 ≈ 首稿（失效条件留下）；领跌只写到「存储链弱于英伟达」，没点名闪迪 / 美光——这是 **另一发模型写法**，不能当成裁剪删了领跌
- 无 2.2 万亿

结论仍以对照臂的同发 diff 为准。关裁剪臂只证明：judge 超时路径本身已经接近「不裁」。

## 历史样本（不重跑，只引用已存在产物）

| 样本 | 裁掉了什么 | 留下了什么 |
|---|---|---|
| P0-A `011622_893108`（绑定前） | 标题里的费半 / 闪迪数字 + 部分失效条件 | 本地盘面 |
| 第六轮主发 `105845_919694`（P0-B 后） | 无领跌可裁 | 闪迪 / 美光绑定进公开稿 |
| `110003`「昨天的反弹能持续多久」 | 闸看见了 `unsupported numeric`，**没裁掉** | 公开稿仍有「约2.2万亿」 |

`110003` 说明：无据阈值是活样本，但「闸响了 ≠ 公开稿一定删掉」。本发对照臂删的是失效条件，不是 2.2 万亿。

## 作废读数（不算进结论）

1. `scripts/live_probe.py ask` → `POST /api/runs`（`run_20260819_152600_277298`，11s）：走 B 引擎 `ask_retrieve_compose`，GLM 429 降级模板。第六轮收据已写明这条泳道不算 continuous。sidecar 工具只用 `start-sidecar` / `stop-sidecar`。
2. 关裁剪首发 `run_20260819_153144_616624`：曾把 `max_repair_cycles` 硬置 0，32s `deadline_exhausted`、空稿。已改回原函数并重启 sidecar 后重跑。

## 对 R5 的含义

- 第三层机制收窄 **不改**。
- 用户拍板点 4（证伪才改 R5）**未触发**。
- 复核服务本发两次超时；裁剪是否稳定仍受 judge 可用性影响。这不是本轨道的施工项。

## 产物（写路径前已 `ls`）

- 对照 episode：`~/.finance-runtime/verifier-ablation-0819/users/verifier-ablation-ctrl/runs/run_20260819_152746_838420/continuous-episode.json`
- 对照公开稿：`.../answer.md`
- 关裁剪 episode：`~/.finance-runtime/verifier-ablation-0819/treatment/users/verifier-ablation-off/runs/run_20260819_153251_481832/continuous-episode.json`
- 收据：`~/.finance-runtime/verifier-ablation-0819/receipt.json`
- 本地补丁树：`~/fwp-wt-verifier-ablation`（`docs/verifier-ablation-e`，脏、勿合）
