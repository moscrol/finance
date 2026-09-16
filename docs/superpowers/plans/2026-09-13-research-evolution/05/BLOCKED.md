# 05｜阻塞与依赖

两类分开记：**工程依赖**（需要别的 owner 动手）与**真人试点未开展**（不是工程缺陷，不阻塞工程交付）。

## 工程依赖（交 06）

| 项 | 需要 06 做什么 | 05 侧现状 |
|---|---|---|
| 生产写入 | `UserSpace.root/research_evolution/product_value_events.jsonl` 等由 06 单 writer 落盘；05 CLI 只写显式 `--out-dir` | 合同与纯函数已给，见 `docs/research-pilots/research-evolution/06-integration-contract.md` |
| 可信来源判定 | 06 按接收入口给事件盖 `source_channel`（frontend / server / manual_import）与 `provenance.kind`；客户端不能自选 | `validate_event` 只校验白名单，不判定来源真伪 |
| 真实 run 解析 | 06 注入 `RunStoreEvidenceReader(store_for_owner=...)`，其中 `store_for_owner` 返回该 owner 的 `RunStore` | 05 提供适配器与内存版；不从 cwd/环境变量推断用户根 |
| 到期回检清单 | 01 的到期判断列表由 06 以 `due_rechecks=[{object_ref, due_at, accessible}]` 传入 `summarize` | 缺清单时回检指标 `unknown(reason=due_list_unavailable)` |
| ledger-map 登记 | 新台账（原事件 / 协议 / 收据 / 总结）由 06 在 `docs/learning/ledger-map.md` 登记后才启用 | 05 不改该文件 |

## 真人试点未开展（不阻塞工程）

- 没有外部参与者：`field_status=pending`，`commercial_status=unstarted`，所有真人分母为 0、值为 null。
- 邀请、收费、招募、访问第三方私有资料须执行人另获用户授权；本轨只准备材料，不外发。
