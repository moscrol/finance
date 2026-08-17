# T-F 判别力评估 + 新 pin 复烟测（**不开 900**）

- 日期：2026-08-17
- 指令：`2026-08-17-dispatch-f-addendum-pins-and-power.md` §5
- 正本：`2026-08-17-dispatch-f-arm-a-aprime-window.md`
- 状态：三件已做。900 未开。5pp 未放宽。

## 0. 一句话

`83e83b42` 能跑，两臂 `task_frame_hash` 仍相同。冻结 30 没有 live 产物，离线表扩不出去。
官方锁的 450/臂 **在 #69 自己的口径下刚够压住 5pp**；若把「semantic 可用」或「剔基础设施」
当成有效底数，450 **压不住**。选项是加样本 / 改分母 / 先修噪声，**不是拧松 5pp**。

## 1. 新 pin 复烟测（§5.1）

唯一目的：确认 `83e83b42` 跑得起来、两臂 hash 仍相同。n=1，**不读延迟排序**。

| | Arm A | Arm A′ |
|---|---|---|
| pin | `83e83b42`（`2a2523f7^1`） | `2a2523f7`（#61 merge） |
| 树 | `/Users/a77/fwp-wt-tf-arm-a-83e83b42` | `/Users/a77/fwp-wt-tf-arm-aprime-2a2523f7` |
| dry-run | exit 0，dirty=false，8792 untouched | 同左 |
| `task_frame_hash` | `beb73ad53210cf8138be545ec12c24b35ec4e408fa47daf2614b240c6f67a437` | **相同** |
| live | exit 0，`gpt-5.6-terra`，degraded / unavailable / `numeric_lineage_gap` | 同左（llm_calls 3 vs 4，不当结论） |
| 产物 | `~/.finance-runtime/tf-smoke-20260817/arm-a-83e83b42-{dry,live}.json` | `arm-aprime-2a2523f7-{dry,live}.json` |

题：冻结 30 的 `A1-market-overview`。Provider 只 terra（未挂 GLM 链）。
生产 rag `model_load_count` 烟测前后都是 1。

⚠ 墙钟 51.4s vs 44.1s **不得读成「A′ 更快」**。n=1，延迟是噪声。

## 2. 冻结 30 离线统计（§5.2）

**先找产物：没找到 live 窗。**

搜过：

- `~/.finance-runtime/evals/`（含 `arm-a-cal-20260816`、`dsh-arm-a-cal-20260816`、`arm-a-cal-smoke-20260816`）
- `~/.finance-runtime/**/frozen-thirty*`：只有题集夹具副本，没有 30 题 live artifact
- 冻结 30 多出来的 21 个 id（`A1-market-overview` 等）在 evals 里没有「≥3 个额外 id + live」的对照窗

现成能离线数的仍是 #68 那半段：九题 × 5，旧 pin，**不是**冻结 30，**不是**新 pin。
追加指令已声明：作基准率估计够用，不能当最终读数。**本页不建议为补这张表去跑冻结 30**——
那会跟 T-A 抢配额，且补出来仍是旧 pin。

亲手复算 #68（`~/.finance-runtime/evals/arm-a-cal-20260816/`，45 条）与追加指令 §4 一致：

| `stop_reason` | 次数 | 占比 |
|---|---|---|
| `numeric_lineage_gap` | 19 | 42% |
| `model_finish` | 9 | 20% |
| `repair_model_unavailable` | 6 | 13% |
| `deterministic_fast_path` | 5 | 11% |
| `runner_exception` | 5 | 11% |
| `repair_model_finish` | 1 | 2% |

`status`：degraded 30 / completed 10 / failed 5。
`semantic_status`：unavailable 33（73%）/ passed 10 / repaired 2。
诚实闸双峰：`contextual-follow-up` 5/5、`current-mainline` 4/5；
`counterfactual-mainline` / `index-rebound-space` / `unfamiliar-methodology` 0/5。

## 3. 判别力（§5.3）

公式与 #69 相同：`half_width = 1.96 × √(2v / (n×r))`，门槛半宽 < 5pp，**不放宽**。
官方 `v=0.1375`（#68 八题 informative 池，已排除 `index-rebound-space` fast-path）。

`required_nr(0.1375) = 422.6`。锁 30×15=450 → 半宽 **4.85pp**，`can_resolve_5pp=true`。
**这是 #69 已经锁死的口径：对「全样本上的 evidence-bound rate」刚够。**

下面三列是「同一 v、不同有效底数」的投影。v 仍用 0.1375，是为了跟官方锁可比；
换底数后 v 自己也会变，§3.1 有实测。

| 底数怎么取 | 有效 n/臂 | 半宽 | 能否压住 5pp |
|---|---|---|---|
| 官方锁：450 全进 | 450 | **4.85pp** | 能（刚够） |
| 剔基础设施 24%（11/45） | 340 | 5.57pp | **不能** |
| 只留 semantic 可用 27%（12/45） | 120 | 9.38pp | **不能** |
| 只留 semantic=passed 22% | 100 | 10.28pp | **不能** |
| 剔诚实闸 42% | 261 | 6.37pp | **不能** |

把「semantic 可用」当唯一底数时，要在 **同一 v** 下压住 5pp，表面样本量要约
`423 / 0.27 ≈ 1570`/臂——不是放宽门槛，是加重复或加题。

### 3.1 不要把「诚实闸零判别力」套错指标

追加指令说：42% 停在同一个诚实闸，对 A/A′ 零判别力。
这对 **`stop_reason` 标签**成立。对 §9.4 主度量 **evidence-bound rate** 正好相反。

#68 上（informative 40 条）亲手数：

| 子集 | n | eb 均值 | 样本方差 |
|---|---|---|---|
| 全 informative | 40 | 0.30 | 0.215（池化 0.1375） |
| `numeric_lineage_gap` | 19 | **0.63** | 0.246 |
| 非诚实闸 | 21 | **0.00** | **0.00** |
| semantic=passed | 10（含 fast-path） | 0.00 | 0.00 |
| semantic=unavailable | 33 | 0.30 | 0.218 |
| 剔 infra | 29 | 0.41 | **0.251** |

几乎全部 eb 变异都住在诚实闸那 42% 里。把这部分从分母拿掉，剩下的 eb 全是 0，
§9.4 主度量没有东西可比。

剔 infra 后若用子集自己的 v=0.251：`required_nr ≈ 772`/臂，半宽要再压到 5pp
必须 **加样本**，不是松门槛。

### 3.2 判定

- **按 #69 字面（450 全进、v=0.1375）**：能把 5pp 和噪声分开，余量只有 0.15pp。
  冻结 30 / 新 pin 的 v 未知；九题旧 pin 只是 prior。
- **按「semantic 可用才算数」或「先剔 24% 基础设施」**：450 **不能**分开 5pp 与噪声。
- 两种解释不能同时当「已经锁好了」。开窗前用户要拍用哪一列当分母。

## 4. 选项（5pp 不动）

1. **认 #69 口径，等 T-A 收工再开 900。** 风险：新 pin + 冻结 30 的 v 可能比 0.1375 差，
   4.85pp 的余量不够。缓解：开窗后先看第一批 30×3 的 v，不够就按裁定加重复，不改门槛。
2. **分母去掉基础设施失败，单独记账。** 5pp 仍打在清洗后的 eb rate 上。
   先用 #68 子集重锁 n×r（当前投影 ≥772/臂），**加样本，不松 5pp**。
3. **先修 `repair_model_unavailable` / `runner_exception`，再开窗。**
   把 24% 噪声降下去，450 的有效底数才接近锁定期望。这是工程前置，不是改判定线。
4. **主度量仍是 eb rate，但诚实闸命中率改成并列读数、不进 5pp。**
   避免「两臂都 42% 诚实闸 → 看起来没差」盖住 bindings 上的真差。
   5pp 仍不放宽。

明确不做：自行把 5pp 拧成 8pp/10pp；把 #68 45× 当成新 pin 的 Arm A 基线；现在开 900。

## 5. 没做

- 没开 900。没切 8792。没动 T / 30 / 档位 / `ASK_TOOL_BATCH_TIMEOUT`。
- 没扩烟测题数。没把 51.4s / 44.1s 写成收益。
- 冻结 30 没有历史 live，没有为补表去跑。
