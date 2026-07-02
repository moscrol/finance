# 金融 agent 学习层

这里放“人读”的学习说明和摘要；机器可读运行时数据默认放在
`intelligence/users/<user>/`，并通过 `.gitignore` 排除。

## 分层原则

- `intelligence/users/<user>/experience_cards.jsonl`：机器读的经验卡片，记录问题、回答得分、扣分维度、修正原则和下次提示规则。
- `docs/learning/*.md`：人读的学习摘要、机制说明和阶段复盘，可入库。
- `docs/learning/daily-market-forecast-ledger.md`：日度市场前瞻台账，记录“盘前假设 -> 收盘验证 -> 经验修正”的学习闭环。
- `docs/learning/stock-analysis-entrypoint-framework.md`：个股与题材完整分析路径，固定公司本体、产业链暴露、证据层、盘面结构、生命周期四问、二阶导和条件化结论。
- `docs/learning/high-position-mainline-rebuttal-framework.md`：高位主线反证与生命周期框架，记录“边际预期、产业瑕疵、事件锚点、拥挤度、顺势到分歧”的分析动作。
- `docs/learning/answer-self-review-framework.md`：回答输出前的质检器与用户影子反驳，防止漏视角、模板化和孤立看个股。
- `/Users/a77/agent-memory`：跨 agent 共享的长期 Obsidian 记忆库，存放被确认后的方法论。
- 知识库 repo：只放公司、产业、公告、互动易、年报、研报等事实证据。

## 最小闭环

1. 正常回答问题。
2. 用 `answer-score` 对回答打分。
3. 对低分/高价值回答加 `--save-card`，沉淀经验卡片。
4. 下次 `ask --compose` 会按问题相关性读取经验卡片，把规则注入 LLM 合成提示。
5. 反复验证有效的规则，再升级到 `intelligence/foresight_methodology.md` 或 `/Users/a77/agent-memory/10_knowledge/`。

## 示例

```bash
python3 -m intelligence.cli answer-score \
  --question "科技细分里哪个方向还有上涨空间" \
  --answer-file /tmp/answer.md \
  --local-source market_feature_store \
  --save-card \
  --user linxiaoqi5111 \
  --applies-to 题材方向判断 \
  --applies-to 上涨空间判断 \
  --corrected-principle "泛方向判断必须先定市场阶段，再看容量/双红/扩散，再拆 L1-L4，最后给反方和证伪条件" \
  --prompt-rule "回答板块空间问题时，不得只给排序；必须说明阶段、资金容量、证据层、反方、验证指标。"
```

之后同类问题：

```bash
python3 -m intelligence.cli ask "科技细分里哪个方向还有上涨空间" \
  --compose --user linxiaoqi5111
```

## 选型说明

第一版使用 JSONL，而不是 DuckDB 或向量库。JSONL 适合追加写、便于审计、可手工删除坏样本；
等卡片数量变大后，再考虑加 BM25/向量混合检索和 rerank。
