# 重建 .rag_venv：依赖清单与操作（2026-08-12 实测）

## 现状（都是实测）

- `~/knowledge-base-private/.rag_venv` → `~/知识库/.rag_venv` 是**悬空符号链接**，
  目标目录不存在 → `kb_search` 每次 7ms `FileNotFoundError`
- 生产 8792 与 canary 8801 导出的都是这个路径，**两边的 kb_search 都是死的**
- health 报 `vector_index: true`（只判索引目录），已加 `rag_runtime` 判据（`f43ab07e`）

⚠ **断裂窗口 ≤6 天**：索引 2026-08-06 22:20 用 bge-m3 成功建成、当天 kb_search
还返回过真 `empty`，证明那时 venv 可用。历史 14 次 `无命中（error）` 集中在
07-28/29，属另一次故障，不要混为一谈。

## 依赖（`~/knowledge-base-private/requirements-rag.txt`）

```
numpy>=1.26
rank_bm25>=0.2.2
PyYAML>=6.0
FlagEmbedding>=1.2.10     # 带出 BGEM3FlagModel
```

`skills/lib/rag/` 还直接 import：`torch`、`transformers`
（`AutoModelForSequenceClassification` = 跨编码器重排器）。二者通常由
FlagEmbedding 带出，但值得装完后显式验证。

## 好消息：不用重下 2GB 权重

HF 缓存里两个模型都在（`~/.cache/huggingface`，共 7.9G）：
- `models--BAAI--bge-m3` —— 稠密嵌入，索引就是它建的
- `models--BAAI--bge-reranker-v2-m3` —— 跨编码器重排

## 必须对齐的约束

现有索引 `meta.json`：**`model: bge-m3`、`dim: 1024`**，建于 2026-08-06 22:20。
**查询侧必须用同一个模型**，否则向量维度对不上。换模型就得重建索引。

## ✅ 已执行（2026-08-12），实测结果见文末

## 操作

```bash
cd ~/knowledge-base-private
rm .rag_venv                          # 先删悬空链接（它是 symlink 不是目录）
python3 -m venv .rag_venv             # 或用 uv
.rag_venv/bin/python -m pip install -U pip
.rag_venv/bin/python -m pip install -r requirements-rag.txt
```

验证（三步，缺一不可）：

```bash
# 1 解释器可执行（health 的新判据用的就是这条）
.rag_venv/bin/python -V

# 2 依赖真的能 import（装上 ≠ 能用，torch 在 mac 上常见 ABI 问题）
.rag_venv/bin/python -c "import numpy,yaml,rank_bm25,torch,transformers;from FlagEmbedding import BGEM3FlagModel;print('ok')"

# 3 端到端：真的能检索出东西（前两步过了仍可能索引不匹配）
.rag_venv/bin/python scripts/rag_index.py query "光模块" --k 3
```

⚠ 第 3 步才是判据。前两步只证明「装好了」，不证明「检索得出来」——
这正是本轮那条审查项（广告值 ≠ 交付值）。

## 装完之后

1. 重启生产：`launchctl kickstart -k gui/$(id -u)/com.a77.finance-workbench`
2. `curl -s localhost:8792/api/health` 看 **`rag_runtime: true`**（新判据）
3. 届时 kb_search 才真的活，验收台账的 before/after 对照才有意义


---

# ✅ 执行结果（2026-08-12 实测）

## 装了什么

`python3 -m venv` → **Python 3.14.5**（比主工作台的 3.12.13 新，但解析与安装均通过）。
`requirements-rag.txt` 只写下限，实际落地版本值得记下来：

| 包 | 装到的版本 |
|---|---|
| torch | 2.13.0 |
| transformers | **5.15.0**（大版本，索引是 08-06 用旧版建的） |
| FlagEmbedding | 1.4.0 |
| numpy | 2.5.2 |
| sentence_transformers | 5.7.0 |

**没有重下权重**——`Fetching 30 files: 100%` 瞬时完成，走的是 HF 缓存。

## 三步验证全过

1. 解释器可执行：`Python 3.14.5`
2. import：`torch 2.13.0 | transformers 5.15.0`，`BGEM3FlagModel` 可导入
3. **端到端检索**（唯一真判据）：
   ```
   # query='光模块' mode=hybrid k=3
    1. 0.1962  wiki/concepts/光模块.md
    2. 0.1945  wiki/sources/光模块产业新变化和新格局研究分析报告.md
    3. 0.1871  wiki/sources/光模块2026研究报告.md
   ```
   `mode=hybrid` 说明 BM25 + 稠密 + RRF 三路都在跑。
   transformers 5.x 的大版本跳跃**没有**破坏兼容。

## 产品层验证（`probe_tool.py kb_search`）

```
[1/2]  25.14s  status=success  evidence=5   光模块
[2/2]  27.49s  status=success  evidence=5   固态电池
```

对比历史：22/22 空手、20 次 error/timeout。耗时与已知的「冷调用约 28 秒」吻合。

## 生产不用重启

`_DENSE_FAILURE_TTL_SECONDS = 600`——稠密失败只缓存 10 分钟。生产进程已跑
3 天 23 小时，一直在「失败→缓存→过期→再失败」的循环里；venv 就位后，
下一次缓存过期即自愈，**无需 kickstart**。

⚠ 但生产仍**没有** `rag_runtime` health 判据（那在未合并的分支上）。
合并部署后 `curl localhost:8792/api/health` 才能看到这一项。
