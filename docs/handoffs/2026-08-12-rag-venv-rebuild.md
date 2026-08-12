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

## 操作（未执行，等你确认）

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
