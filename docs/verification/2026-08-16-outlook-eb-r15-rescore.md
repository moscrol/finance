# R-15 十题窗分层 evidence_bound：离线重算（未结案）

- 日期：2026-08-16
- 案号：`R-20260816-15`
- 状态：**部分验证；outcome 保持 pending**
- 被审 runtime：8792 全程 `6cd0756e` 未切；未翻 ASK_*；未动 #72 / T / 30 / 档位
- 冻结计分：`~/.finance-runtime/outlook-ab-20260816/score.json`
  （`scored_at=2026-08-16T12:19:27+00:00`，本机 mtime **2026-08-16 20:19:27**，本轮未覆写）
- 夹具 sha256：`ac464158a724c6312b373b59a4bae2ebc1f81925b5c6e284e85c22547bc7d608`
- 量具：`intelligence/eval/episode_bindings_rate.py`
- 重算脚本：`scripts/rescore_outlook_eb_r15.py`（拒绝写 `score.json`）
- 机器产物：`docs/verification/2026-08-16-outlook-eb-r15-rescore.json`

## 0. 预注册判据（逐字，未改）

> 用冻结三对离线重算：`_bindings_rate` 把 `grounding_mode=model_reasoning`
> 槽移出分母（或另报 `judgment_hash_rate`）后，`post:L01:r3` / `L03:r2` /
> `L05:r2` 的 evidence 槽 eb=1.00，窗级 `evidence_bound_pp` 回到 ±5pp 内；
> 生产 episode / #72 / T / 30 / 档位不变。

部分验证不得写 `confirmed`。本收据不改预测原文。

## 1. 口径

| 口径 | 分母 | 绑定 |
|---|---|---|
| 旧（legacy / 十题窗 `_bindings_rate`） | 全部 binding | `hashes and not gap` |
| 分层（stratified） | 排除 `grounding_mode=model_reasoning` | 同上，只评剩余 evidence 槽 |
| `judgment_hash_rate` | 只评 `model_reasoning` 槽 | 同上；无判断槽 → `None` |

缺 episode 文件 → `None`，**不进窗均值**（L04 四槽保持 `None`）。
有 episode 但 bindings 空 → `0.0`（`pre:O09:r1`）。
排除后分母为空 → `None`。把缺文件当成 `0.0` 会造出假的 +4.8pp，禁用。

长尾 `scripts/score_longtail_live_ab.py` 仍走旧口径（`exclude=()`），数字不变。
仓外十题窗 scorer 的 `main()` 会覆写 `score.json`，本轮不跑。

## 2. 单测

`intelligence/tests/test_episode_bindings_rate.py`：**6 passed**。

钉住形状：判断槽 0-hash + 旁槽 hashed → 旧口径 0.5、分层 1.0、`judgment_hash_rate=0.0`。
pre 臂判断槽仍是 `evidence` 时两口径都是 1.0。缺 episode → `None`。

## 3. 冻结三对

| slot | pre run | post run | pre L/S | post L/S | post `judgment_hash_rate` |
|---|---|---|---|---|---|
| L01:r3 | `run_20260816_184616_575486` | `run_20260816_184718_305950` | 1.00 / 1.00 | 0.50 / **1.00** | 0.0 |
| L03:r2 | `run_20260816_185728_883724` | `run_20260816_185901_871285` | 1.00 / 1.00 | 0.50 / **1.00** | 0.0 |
| L05:r2 | `run_20260816_190515_806994` | `run_20260816_190657_142513` | 1.00 / 1.00 | 0.50 / **1.00** | 0.0 |

三对分层 evidence 槽 = 1.00：**PASS**（预测前半句兑现）。

## 4. 窗级分层

分母与冻结 `score.json` 相同：outlook 槽 19/21（L04 四格 `None` 除外）。

| 层 | 旧 pre → post | 旧 pp | 分层 pre → post | 分层 pp |
|---|---|---|---|---|
| main42 | 0.947 → 0.772 | **−17.5** | 0.947 → 1.00 | **+5.3** |
| L01 | 1.00 → 0.667 | −33.3 | 1.00 → 1.00 | 0.0 |
| absorbed | 1.00 → 0.771 | −22.9 | 1.00 → 1.00 | 0.0 |
| core_unabsorbed | 0.909 → 0.773 | −13.6 | 0.909 → 1.00 | +9.1 |
| guards（F01，不进 main42） | 1.00 → 0.50 | −50.0 | 1.00 → 0.50 | −50.0 |

- 「修后不降」成立（分层 post ≥ pre）。
- 预测后半句「窗级回到 ±5pp」**未入**：+5.3 比 5.0 多 0.3pp。
- +5.3 不是「证据绑得更好」。post 不再为合法 0-hash 受罚（分层 post=1.00）；
  pre 仍含 `pre:O09:r1` 空 bindings（0.0），所以均值停在 0.947，差值翻成正的。

相对旧口径发生变化的槽（均为 post 判断槽 0-hash）：
`L01:r2` / `L01:r3` / `L03:r2` / `L05:r2` / `O06` 两槽 / `O07` 两槽 /
`O08` 两槽 / `O09:r1`。`pre:O09:r1` 两口径都是 0.0（无判断槽可排除）。

## 5. 账本

| 子句 | 结果 |
|---|---|
| 三对 evidence 槽 = 1.00 | 兑现 |
| 窗级 ±5pp | 未入（+5.3） |
| 生产 episode / #72 / T / 30 / 档位不变 | 兑现（本 PR 只动 eval/docs） |
| 总体 | **pending** |

`R-20260816-07` 未触线。不代结 R-10 / R-13。不切 8792。

## 6. 陷阱

分层 main42 是 **+5.3pp，不是 ±5 内的 0pp**。不要把「修后不降」写成「窗级已回到带内」。
L04 必须保持 `None`。
