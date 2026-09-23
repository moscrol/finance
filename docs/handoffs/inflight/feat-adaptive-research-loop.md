# feat/adaptive-research-loop 在途

## 这个分支做什么
研究回路传输层绝对截止与 #76 L6 自然金融验收准备；#72 / PR #868 保持 WIP。

## 决策与被否方案
- 工程收据继续绑定 `7ad61a0d3`，否了把 docs/预检 head 冒充全量重跑；代码与文档质量、合入授权分开。
- L6 固定候选仍为 `31f1b40dd`，否了直接用新增提交 `d67a2828e` 宣称 live 验收；新增提交只是预检/审计工装。
- 终稿判官固定 `llm`、模型 `glm-5.3-flash`，检索判官 `auto`；否了 off 对照和降级 hash/BM25，因本次授权只含一组真实三题。
- BGE-M3 权重缺失时阻断，否了换模型、联网下载或把检索依赖缺失伪装成答案质量结论。

## 当前状态
`d67a2828e` 已提交，工作树干净；PR 未合入、未部署。三题真实请求数 0，旁车/端口锁数 0。数据已冻结但 KB/外部输入未冻结。协议为 `BLOCKED_RETRIEVAL_DEPENDENCY`、`can_execute=false`。

## 已验证
独占锁定候选 `31f1b40dd` 并核对干净。严格截止探针 13 场景 `deadline_violations=[]`。历史 Q3 失败阳性逐句核对一条有证据的数值条件被删，审计结论 `NOT_PASSED`，没有把 `repaired` 当通过。新增/既有定向回归 `27 passed`，ruff 与提交钩子通过。冻结库 SHA256 `75ff8d41...975c941`；市场/个股到 2026-09-22，板块 VIEW 到 2026-09-18；生产身份、冻结 manifest、候选代码前后不变。

## 未验证 / 已知边界
本地 BGE-M3 snapshot 没有 `pytorch_model.bin`/`model.safetensors`，离线 readiness 失败；另一个进程持有 `.incomplete` 下载文件，未触碰。故三题、实际 served model、真实迟到判官、400/429 停批、完整 live 收尾均未执行。严格模拟不能代替自然路径；`is_cancelled` 存活变异和 5 处 timeout 来源仍是旧边界。

## 下一步
1. 权重可用后重新做离线 readiness，保持冻结 manifest 不变。
2. 另行验证 live controller：19897/19898 独占、单次提交预占、400/429 立即停批、停止/锁释放。
3. 在固定 `31f1b40dd` 上三题各首发一次，不重发、不续问；逐句审计后才可推进 #75。
4. 用户另行明确合入授权前始终保持 WIP，不合 main。

## 踩过的坑
旧 `compare_adaptive_research.py` 端口在禁用区间；生产 8792 的 dirty 状态是基线，不得擅自修正。测试收据的 revision 必须精确绑定，新增工装收据不替代 #72 全量门禁收据。
