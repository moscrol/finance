# 离线量：finalize 写作时长（2026-09-02）

零 LLM。脚本：`scripts/offline_finalize_duration.py`。数字：`docs/verification/2026-09-02-finalize-duration-offline.json`。

**结论：20s 合成地板不够。生产上有时钟字段的成功写作 P95=24.7s，全量生产成功写作 P95=26.9s。15.9s 是中位数附近的单点，不是地板。P1 若把 reserve 借记到 20，会切掉大约三分之一的成功成稿。35s 盖住生产 P95 和时钟样本的全部成功写作。公式仍不动。**

## 怎么量

`agent_episode.py` 算了 `model_elapsed`，但没落盘。工具事件的 `at` 仍不可信。finalize 这条路径是：`finalization` 落盘 → 阻塞 `complete()` → `model_turn` 落盘。落盘差 ≈ 写作墙钟。标 [推断, 代码路径]；交叉核对：`timeout_asked ≈ remaining_seconds_at_entry`（差 ≤1s）才是合成窗。

根目录：`~/.local/share/finance-workbench/users` + `finance-base-ab/out/users`。820 份 episode；277 份有 `finalization`。生产用户 `linxiaoqi5111`：146 份。`timeout_asked` 从 2026-08-16 才有，所以「合成窗」子集更小（生产 44）。

## 读数 [实测]

| 队列 | n 成功 | p50 | p90 | p95 | max | >20s | >35s | 超时 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 生产 · 凡 finalization 后一条 model_turn | 140 | 17.5 | 25.3 | **26.9** | 46.8 | 51 (36%) | 2 (1.4%) | 6 |
| 生产 · 合成窗（asked≈remaining） | 42 | 12.0 | 21.0 | **24.7** | 25.4 | 5 (12%) | 0 | 2 |
| 全用户 · 凡 finalization 后 | 260 | 17.3 | 32.7 | 44.1 | 91.2 | 98 | 23 | 17 |

生产超时 6 次全部跑满约 60–68s，asked 能读到的两次是 59.95 / 64.53——撞的是当时给的合成窗，不是 20s 地板。不能拿它们证明「20s 够用」。

生产成功写作里 >35s 的两次（36.1s、46.8s）都在时钟字段出现之前（08-12 / 08-15）。08-16 之后生产成功写作没有超过 25.4s 的。

asked 能读到时，成功写作的授权额中位是 **60s**（min 59.7）。今天合成吃的是整段 reserve，不是 20s 地板。20 只出现在 opening borrow 之后的规划切法里。

## 对 P1 的含义

- 「借记到 `MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS=20`」：**证伪**。生产 P95 已经 >20，36% 的成功成稿 >20s。
- 「35s 地板」：盖住生产 P95，也盖住全部有时钟的成功写作。全用户 P95=44 被探针/实验臂拉高，不当生产地板。
- 15.9s 那条注释样本落在生产 p50（17.5 / 12.0）附近，当地板会欠。
- 这一刀仍然**不改公式**。它只回答「reserve 不可侵犯 vs 工具有地板」里合成侧的数：合成要的不是 20，是大约 25–35。工具地板另算。

## 没做

没烧配额。没改 Episode / 8792 / 档位。没把 `model_elapsed` 补进 `model_turn`（那会改收据形状，另开单）。
