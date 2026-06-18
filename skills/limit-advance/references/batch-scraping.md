# limit-advance 批量抓取与覆盖检查

> 本文件由 `skills/limit-advance/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

## 批量抓取某月

**核心约束**：写入必须从旧到新串行，确保字段追加顺序正确。

### 方式一：子 agent 并行抓取 + 主 agent 串行写入（推荐）

```
子 agent（并行）           →    主 agent（串行）
  scrape.py --json DATE        接收所有 JSON，按日期排序
  只返回数据，禁止写表          从旧到新逐日 pipe 到 write.py
```

- 子 agent 每批 3-5 个，完成后启动下一批
- 主 agent 收到所有结果后按日期正序写入

### 方式二：纯串行（备选）

```bash
for d in 01-05 01-06 01-07 ...; do
  python3 scripts/scrape.py --json $d | python3 scripts/write.py
done
```

### 流程

```bash
# 1. 检查覆盖
python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/check_coverage.py [月份]

# 2. 抓取写入（方式一或方式二）

# 3. 全部完成后再次检查覆盖
python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/check_coverage.py [月份]
```

## 覆盖检查与漏抓处理

覆盖检查发现缺失日期时：

1. 先确认该日期是否为节假日（元旦 01-01~01-02、春节 02-16~02-20、清明 04-06、五一 05-01~05-05 等）
2. 非节假日缺失，先用 scrape 检查该日期是否有 3 板+ 晋级数据：
   ```bash
   python3 scripts/scrape.py --json MM-DD
   ```
3. 无 3 板+ 输出 → 该日期确实无数据，不算漏抓
4. 有数据 → 补抓写入
