# V7 输入侧 KB 传感器：金标 + 量纲诚实（2026-08-21）

> spec：`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md` §V7
> 脚本：`scripts/audit_ceiling_sensors.py`（只读 `continuous-episode.json`，零配额）
> 树：`/Users/a77/fwp-wt-v7-inputside-sensors` @ `feat/v7-inputside-kb-sensors`（基线 `gitea/main=dd6ca952`）
> 不立预测行（工具单，沿 W5）。

形状 I = 题形 × KB 调用率三层（authorized / planned / called）。
形状 III = kb_search 送达字符数 / 条数；telemetry 补齐前的历史 run 报「不可判」，不报 0。

题形取 `contract.question_type`（机器字段）。R-11 手工表的「板块发酵 / 个股走势复盘」是人话标签，对账用三层布尔，不用那两个中文名：

| 人话（dark-asset §1） | `question_type` |
|---|---|
| 板块发酵（减肥药） | `general_finance_qa` |
| 板块发酵（CXO A/B、钙钛矿） | `theme_analysis` |
| 个股走势复盘（皇氏集团） | `stock_deep_dive` |

## 金标（R-11 五案例 run 重放）

复算命令（与 `docs/verification/2026-08-21-inputside-kb-dark-asset.md` §5 同一批 run）：

```
python3 scripts/audit_ceiling_sensors.py \
  --runs-dir ~/.local/share/finance-workbench/users/probe-ledger-0821/runs/run_20260821_165210_889002 \
  --runs-dir ~/.local/share/finance-workbench/users/probe-ab-0821-post/runs/run_20260821_164659_624916 \
  --runs-dir ~/.local/share/finance-workbench/users/probe-tracediff-0821/runs/run_20260821_152044_472523 \
  --runs-dir ~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260821_171744_929436 \
  --runs-dir ~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260821_171744_955225 \
  --since 2026-08-21 --until 2026-08-21
```

| run | 题形 | authorized | planned | called | III |
|---|---|---|---|---|---|
| `run_20260821_165210_889002` 减肥药 | `general_finance_qa` | ✅ | ❌ | ❌ | no_call |
| `run_20260821_164659_624916` CXO B 臂 | `theme_analysis` | ✅ | ❌ | ❌ | no_call |
| `run_20260821_152044_472523` CXO A 臂 | `theme_analysis` | ✅ | ❌ | ❌ | no_call |
| `run_20260821_171744_929436` 钙钛矿 | `theme_analysis` | ✅ | ❌ | ❌ | no_call |
| `run_20260821_171744_955225` 皇氏集团 | `stock_deep_dive` | ✅ | ❌ | ❌ | no_call |

聚合：`n=5 authorized=5 planned=0 called=0`；`theme_analysis` 3/3 授权零计划零调用；III `judgeable=0 不可判=0 no_call_runs=5`。

与 dark-asset §1 手工扫描逐字一致：**5/5 授权躺着、计划不含 KB、零实调**。没调 KB 记 `no_call`，不是送达 0——否则历史窗会把「从未调用」读成「送达了 0 字符」。

退出码 1 来自既有 W5 的 B/C（钙钛矿 / 皇氏 / CXO A 的 marker_loss 等），不是本单回归。输入侧只记账，不单独红。

`called` 不按 `trace.capability` 分组：成功路 capability 是 `agent_loop`、真名在 `provider=agent:kb_search`。按 capability 会把成功调用漏掉。钉在 `test_shape_i_called_uses_provider_not_capability`。

## 量纲诚实

V7 补齐前的历史 run，`tool_result.telemetry` 缺字段或是空 dict（R-12 现状）。形状 III：

- 有 kb_search 调用但缺 `delivered_chars` / `hit_count` / `source_pages` → **不可判**
- 空 dict `{}` → **不可判**（不是 0 字符）
- 零调用 → `no_call`（不是 0 字符）

把缺字段当成 0，夜检会假绿：历史窗全是「送达 0」，看起来像管道没坏。

## TDD 红绿

先钉后写。红输出（`dd6ca952`，实现未落地）：

```
18 failed, 19 passed
KeyError: 'I' / 'III' / 'inputside'
ImportError: cannot import name 'kb_delivery_telemetry'
test_kb_tool_result_persists_delivery_telemetry: assert False
收据：~/.finance-runtime/test-receipts/20260821T161647Z-dd6ca952.json
```

绿：同文件 37 passed（原 W5 19 + 本单 18）。实现提交 `a7b9de8a`。

## 变异

先提交 `a7b9de8a` 再改（`git checkout --` 只能回到已提交态；W1 事故：未提交树上它是删除器）。

1. 缺字段当 0（`tel.get("delivered_chars", 0)`，空 dict 当完整遥测）→ **3 红**：
   - `test_missing_kb_telemetry_is_unjudgeable_not_zero`（`judgeable` == `unjudgeable`）
   - `test_empty_kb_telemetry_dict_is_unjudgeable_not_zero`
   - `test_audit_shape_iii_unjudgeable_not_counted_as_zero`（`unjudgeable` 0 == 1）

还原后本文件诚实钉 3 passed。击杀收据 `~/.finance-runtime/test-receipts/20260821T162509Z-a7b9de8a.json`（dirty 变异树，只作击杀证据）。

## telemetry 落盘

写入点：`intelligence/services/agent_research.py` 的 `kb_delivery_telemetry`（`_kb_search` 邻域）+ `research_tool_registry` 在 cutoff 改写后按**实际送达**再算一次 + `agent_episode` 写入 `tool_result.telemetry`。

字段：`delivered_chars`（`len(observation)`）、`hit_count`、`source_pages`（`internal_locator` 优先，否则 title）。

按实际字符计，不写死 800——V3 把 `_kb_search` 接到 `llm_evidence` 粗管道后，读数自动上去。telemetry 只进 ledger，不进模型上下文。

## 落点

- 审计件：本仓 `scripts/audit_ceiling_sensors.py`（W5 四形状保留，输入侧另栏）
- 验证文档：本文件
- 不立 `docs/prediction-ledger.md` 行
