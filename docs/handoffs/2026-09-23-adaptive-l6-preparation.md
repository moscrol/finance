# 2026-09-23 #76 L6 自然验收准备快照

## 背景
用户已批准在合入前固定候选 `31f1b40dd788d36c71da249d59fb769c50d7cd30` 上先做 #76 L6，再做 #75 独立终审；范围是三道原题各首发一次，不重发、不续问、不扩成 semantic judge on/off 两组，不合入、不部署、不改生产。判官差异核对后，本轮沿用终稿 `ASK_SEMANTIC_JUDGE=llm`、`glm-5.3-flash`，并显式保留独立的 `ASK_EVIDENCE_JUDGE=auto`；`adaptive_arm=off` 不是判官开关。

## 发现顺序与决策
1. 旧 live 启动器使用禁用端口，且不能证明数据和身份隔离，所以新建加锁 detached checkout 与专属证据根；固定候选未改变。
2. `diagnose_llm_timeout.py --assert-deadline` 在候选树通过 13 个本机模拟场景，`deadline_violations=[]`。`judge_window_stalls` 和 `judge_late_report` 都记录报告未收到/不可用；这只是传输机制证据，不能充当自然金融验收。
3. 旧 Q3 样本只作为失败阳性夹具。逐句绑定原 episode SHA256 与 evidence content hash 后，确认 09-10 成交额 `1295.9673`（单位“亿”）四舍五入为 `1295.97 亿`，对应的“跌破则退潮确认”条件被删除。审计器返回 `NOT_PASSED`，因此没有把 `semantic_verifier.judge_status=repaired` 当成质量通过；其余删除项没有在本轮一并定性。
4. 用写时复制冻结了 DuckDB 与 market snapshot/export 文件，manifest 不变，生产 health 七项前后不变。市场/个股资料及 JSON snapshot 到 2026-09-22，published 板块及成分 VIEW 到 2026-09-18；没有补库凑齐，KB/外部来源没有被声称冻结。
5. 离线加载知识库自己的 BGE-M3 embedder 失败：固定 snapshot 缺 `pytorch_model.bin` 与 `model.safetensors`。另一个进程持有 `.incomplete` 下载文件，所以本轮没有下载、杀进程、换模型或降级检索。协议状态改为 `BLOCKED_RETRIEVAL_DEPENDENCY`，`can_execute=false`。

## 方案对比
| 方案 | 评价 | 结果 |
|---|---|---|
| 等权重可用后按原协议 live 跑 | 保持题面、判官和数据口径，仍需补 controller 收尾 | 选择 |
| 换 hash/BM25 或关闭检索判官 | 改变验收变量，无法回答原协议的检索质量问题 | 否决 |
| 直接联网下载权重 | 会触碰别的任务下载过程，且增加不可冻结依赖 | 否决 |
| 复用旧 runner/旧样本 | 端口与数据冻结契约不合，旧样本不能代表候选 | 否决 |

## 收据与边界
- 证据根：`~/.finance-runtime/reviews/pr868-l6-natural-20260923-1315/`。
- 预检/冻结/审计工装提交：`d67a2828e29bcfe47370eb05f94171b519cf821e`；定向测试 `27 passed`，ruff 和提交钩子通过。
- `positive-control-audit-final.json` 的 `NOT_PASSED` 是故意的失败阳性，不是三题结论。
- 没有真实模型请求，未记录实际 live served model；自然迟到判官、400/429 停批、旁车停止/锁释放和三题逐句金融审查均未执行。
- 既有 #72 九项全量收据仍只绑定 `7ad61a0d3`，不移绑到 `d67a2828e`。

## 下一步与不要做
权重可用后先复核 readiness 和 manifest，再补齐独占端口、额度预占及收尾控制，最后只在 `31f1b40dd` 上首发三题。不要删除冻结副本，不要修改生产 8792，不要复用禁用端口，不要把“判官未调用/报告未收到”签成判官路径通过，也不要在用户新授权前合入 PR #868。
