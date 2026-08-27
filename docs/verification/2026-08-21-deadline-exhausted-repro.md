# W4 观测单：deadline_exhausted 主稿归零路径——复现与归因（2026-08-21）

> 任务书：[`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md`](../superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md) §W4。
> 判据（spec 预注册）：采样 `deadline_exhausted && carried_draft_chars=0`，n≥3；归因二选一（可证伪）——**provider 暂态**（超时聚集特定时段）vs **结构性**（任何时段必现）。
> 纪律：观测单，不改代码、不改预算参数（R-20260816-07「无实测不得抬 T」在案）。
> **结论：结构性成立，暂态排除。且量级远超立案预期——deadline_exhausted 不是探针偶发，是生产常态终止方式（79%）。**

## 1. 扫描口径

- 数据源：`~/.local/share/finance-workbench/users/*/runs/run_*/continuous-episode.json`（全部用户目录，含主用户/探针/eval 批跑）
- 日期窗：`run_20260814` 起（近 8 日），共 **410** 个含 `finish` 事件的 run
- 字段路径（本次核明，供 W5 传感器复用）：
  - 终止方式：`events[kind=finish].payload.stop_reason`
  - 携带草稿：`events[kind=finish].payload.carried_draft_chars`
  - 每轮预算：`events[kind=model_turn].payload.timeout_asked / timeout_configured`（**08-16 晚之后才普遍埋点**，更早的 run 该字段缺失——按量纲诚实原则计「不可判」，不计 0）
  - 超时轮：`model_turn.payload.error` 含 `TimeoutError`
  - 修复窗：`events[kind=repair_reentry].payload.timeout_asked`

## 2. 读数

### 2.1 总量与终止方式分布

| stop_reason | n | 占比 |
|---|---|---|
| `deadline_exhausted` | **323** | **79%** |
| `model_finish`（模型自然写完） | 70 | 17% |
| `model_unavailable` | 17 | 4% |

「模型自然完成主稿」在当前预算制下是**例外不是常态**。

### 2.2 时段分层（归因判据本体）

按天：de 率 69–100%（08-14: 80%、08-15: 85%、08-16: 78%、08-17: 10/10、08-19: 69%、08-20: 70%、08-21: 71%）。
按小时（0–23 时全覆盖）：绝大多数小时段 de 率 >60%，无聚集时段、无豁免时段（唯一例外 21 时 0/4，样本过小）。

**暂态假设要求超时聚集在特定时段/provider 窗口——数据否证。结构性假设要求跨时段稳定——数据支持。归因：结构性。**

### 2.3 deadline_exhausted 内部分层

| 子类 | n | 含义 |
|---|---|---|
| `carried_draft_chars=0` | **276**（de 的 85%，全部 run 的 67%） | 主稿阶段颗粒无收 |
| `carried_draft_chars>0` | 47 | 超时但带稿走（如 CXO B 臂 `run_20260821_164659_624916` carried=1259——**满分稿也是 de 终止**） |

**carried=0 的 276 个 run 全部有 `repair_reentry`**：「全稿一发成于修复窗」不是两个换形探针的怪事，是 276 个 run 的常规路径。生产答案的实际生成预算 = 修复窗（30s，08-17 后调为 40s），主稿多轮是纯消耗零产出。

### 2.4 机制链（以 `run_20260821_171744_929436` 为例，模式在有埋点样本中普遍）

```
model_turn#1  asked=69.9/75  成功（工具规划轮）
tool ×2       granted=23.2
model_turn#2  asked=22.6/75  成功（继续工具）
tool ×1       granted=17.8
model_turn#3  asked=17.8/75  ← 写稿轮只剩残值 → LLM TimeoutError
finish        stop_reason=deadline_exhausted, carried_draft_chars=0
repair_reentry asked=40.0    ← 独立新授，全稿在此一发写成
```

- deadline 全链共享绝对时刻（这是设计内的正确做法），每轮 `asked=min(剩余, 75)`；**但成稿轮没有保留量**——工具轮吃掉多少，写稿轮就只剩多少。
- 超时轮剩余预算分布（有埋点样本 n=39）：**median 13.0s，82% 不足 20s，92% 不足 40s**。千字级全稿在该窗口内不可能完成。
- 修复窗独立新授 30–40s > 写稿轮残值中位数的 2–3 倍——修复窗反而是全链里唯一够大的生成窗口，于是它成了事实上的主生成窗。

## 3. 诚实边界

1. **窗口大小非唯一因子**：对照组 `model_finish` 的末轮 asked 多在 12–26s 也成功了。差异可能在末轮输出长度（短补充 vs 全稿）与提示体积，本单未逐 run 拆输出长度——归因「结构性」指的是**预算分配结构把成稿轮系统性压到临界之下**，不是「小窗必死」。
2. 08-14/15/16 的大样本多为 eval 批跑用户（smoke-quality/longtail-ab/outlook-ab），与 live 混合；但 live 子集（linxiaoqi5111 与 probe-* 用户，08-19 之后）同形（de 率 69–71%），形状不随用户/题形变。
3. `timeout_asked` 埋点 08-16 晚之后才全，更早 run 的每轮预算不可判（不影响 stop_reason/时段分层的分母）。
4. `timeout_configured=75` 的配置出处本单未查（观测值口径，不猜配置名）；修复窗 30→40s 的调整时点（约 08-17）从数据观测，未查对应 PR。

## 4. 影响与后续（不在本单修）

- **放大形状 C 暴露面**：276 个 run 的稿是修复窗单点产出，此后任何判官删除即终态（无第二修复窗）——W1（判官降级权）落地后此暴露面收窄，但预算结构本身未变。
- **成本结构**：主稿 2–3 轮 LLM 调用（每轮最长 70s 计费时间）产出为零的比例占全部 run 67%——纯烧钱轮。
- 修法方向（**另行立项，须实测**，受 R-20260816-07 约束）：① 成稿轮保留预算（reserve）——台账 R-20260816-09 已有「60s reserve 杠杆须实测」在案，本读数是它等的实测证据的一半（还差 reserve 实验组）；② carried draft 门槛（工具轮强制携带中间稿）；③ 把修复窗正名为二段生成并给它配足预算。三者取舍需要实验组对照，不拍脑袋。
- **W5 传感器补充建议**（给 W3+W5 执行方）：本文 §1 的字段路径可直接复用；建议传感器加一项「`stop_reason=deadline_exhausted && carried=0` 计数」，它是形状 C 暴露面的分母。

## 5. 复算命令

```bash
python3 - <<'EOF'
import json, glob
from collections import Counter
rows=[]
for p in sorted(glob.glob('/Users/a77/.local/share/finance-workbench/users/*/runs/run_*/continuous-episode.json')):
    rid=p.split('/runs/')[1].split('/')[0]
    if rid < 'run_20260814': continue
    try: d=json.load(open(p))
    except Exception: continue
    fin=[e for e in d.get('events',[]) if e.get('kind')=='finish']
    if fin: rows.append((fin[0]['payload'].get('stop_reason'), fin[0]['payload'].get('carried_draft_chars')))
print(Counter(r[0] for r in rows))
print('de & carried=0:', sum(1 for r in rows if r[0]=='deadline_exhausted' and r[1]==0))
EOF
```
