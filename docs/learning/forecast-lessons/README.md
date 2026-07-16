# 双盲预测学习回流

这里是 `forecast-review-ledger` 的学习投影，不是第二份 verdict 台账。

数据流：

```text
answer + verdict(miss/partial)
  -> reflections/*.json（LLM 候选，pending）
  -> 人工 approve-reflection
  -> lessons.jsonl（approved）
  -> 次日双盲答卷 prompt

§8 用户批注
  -> rule_candidates.jsonl（pending）
  -> 人工 approve-rule / reject-rule
  -> 次日双盲答卷 prompt（仅 approved）
```

常用命令：

```bash
python3 -m scripts.forecast_learning_loop sync-reflections
python3 -m scripts.forecast_learning_loop sync-annotations
python3 -m scripts.forecast_learning_loop approve-reflection \
  docs/learning/forecast-lessons/reflections/<file>.json --id <hypothesis-id>
python3 -m scripts.forecast_learning_loop approve-rule <rule-id>
python3 -m scripts.forecast_learning_loop reject-rule <rule-id>
python3 -m scripts.forecast_learning_loop prompt --limit 5
```

审批原则：

- `pending` 永不进入 prompt。
- 只有能说明“当时可见却漏看了什么”或“哪段推理可重复修正”的 lesson 才批准。
- A1 随机性不应强行沉淀硬规则，防止事后过拟合。
- 规则与当前证据冲突时，答卷必须说明冲突，不能机械套用历史经验。
