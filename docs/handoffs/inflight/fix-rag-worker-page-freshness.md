# fix/rag-worker-page-freshness

## 这个分支做什么
常驻 RAG worker 的页级新鲜度判定 + 缓存键/store cache 时序修正。三个提交领先 main。

## 决策与被否方案
- 选逐页 verdict（`page_freshness`）/ 否整库 manifest 一票否决（99.7% 无辜页连坐）
- 选 identity 当缓存键首段 / 否 freshness 进键（翻转即 miss → 重建模型）
- 选 store cache 单槽自失效 / 否驱逐时清槽（清完下次又读一份，两份同驻）
- 选绑签名归一实参 / 否只认 kwargs（位置传参的配置丢掉会撞键）

## 当前状态
三个提交已推 gitea，领先 main 3 个，main 没动。**Gitea 上还没有 PR**，需要新建。树干净。

## 未验证 / 已知边界
- 全量 pytest 7613P/5F，5 红全在 `test_dream_mine.py`（日历时间炸弹，main 同红，与本分支无关）。
- 未跑 live / 未切 8792。KB 侧 `fix/rag-page-level-freshness` 独立可合。
- 共享 embedder 按原始名缓存，KB `get_embedder` 会归一 bge/bgem3/bge-m3；生产 want 恒为 meta["model"]，不会撞。
- `model_load_count` 实际数 retriever 构造次数（embedder 已共享），换索引时跳到 2 但权重不重载。

## 下一步
1. Gitea 开 PR（`fix/rag-worker-page-freshness` → `main`）。
2. dream_mine 时间炸弹须另开分支修（`CollectOptions` 加 `now` 穿透），否则合并闸红。
3. 合入后切 8792。

## 踩过的坑
- e2e 夹具直接 `RagStore()` 构造绕过了 `_install_store_cache`，store cache 时序完全没测到。改成 classmethod `load` + `config.index_dir()` 才对齐生产形状。
- `_evict_other_indexes` 清 store cache 的时序：cmd_query 已把新 store 换进槽，驱逐再清一次，下次只能再从盘上读→两份同驻。

## 已验证
test_rag_worker.py 36 绿。ruff check 绿。pre-commit 九道门禁全过。
