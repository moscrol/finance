# Arena 探针过滤机制

## 背景
Arena 会随机路由到不同模型，`model_pin_probe` 可以探测当前会话是哪个模型。现在需要在 `intelligence/arena` 的应用里加一个过滤层，自动过滤掉非目标模型的回答。

## 已实现

### 1. `probe_filter.py`
- 复用 `model_pin_probe/fingerprint.py` 的风格特征提取（纯标准库，无 numpy）
- `style_features(text)` → 15维向量：len_log, avg_sent_len, cjk_ratio, fullwidth_punct_ratio, uses_header/bullet/numbered/bold/table/code, has_opener/closer, first_person 等
- `cosine_distance(a,b)` 余弦距离
- `ProbeFilter` 类：
  - `from_target_file(path)` 从 `target_profiles.json` 加载目标质心
  - `from_fingerprints(fps, name, threshold)` 从指纹列表直接创建
  - `is_target(text)` → (ok, target_name, distance)
  - `filter_answers(answers)` 批量过滤

### 2. `runner.py` 集成
在 `run_pair` 里，得到两个 agent 的 Answer 后：

```python
probe_filter = _get_probe_filter()  # 读环境变量
if probe_filter:
    filtered_out = []
    for idx, ans in enumerate(results):
        ok, tname, dist = probe_filter.is_target(ans.content)
        record["outputs"][idx]["_probe_filter"] = {"is_target": ok, "target": tname, "distance": dist}
        if not ok:
            filtered_out.append(...)
    if filtered_out:
        # 非目标模型，过滤掉整个对战，不发布
        store.finish_run(run_id, record, error=...)
        return run_id
```

环境变量控制：
- `ARENA_PROBE_FILTER_ENABLED=1` 开启过滤
- `ARENA_PROBE_TARGET_PROFILE=/path/to/target_profiles.json` 目标指纹文件，默认 `~/.local/share/finance-arena/target_profiles.json`

过滤后，`runs` 表的 `payload` 里会记录 `_probe_filter` 和 `probe_filter_blocked`，便于审计。

### 3. `generate_target_profile.py`
从 `model_pin_probe/data/log.jsonl` 生成目标配置：

```bash
# 先跑探针，收集目标模型的指纹
cd model_pin_probe
python probe.py run --adapter manual --sessions 5 --rounds 3 --tag my-target

# 生成目标配置，自动找最大簇作为目标
python ../intelligence/arena/generate_target_profile.py --log data/log.jsonl --tag my-target --out ~/.local/share/finance-arena/target_profiles.json --name target-model-v1 --threshold 0.08
```

输出 `target_profiles.json` 包含 centroid、threshold、source_sessions。

## 使用流程

1. **标定目标模型**：开 5-10 个新会话，手动用探针挑出你满意的模型（比如回答风格符合预期、知识截止2026），给它们打同一个 tag 跑 `probe.py run`
2. **生成指纹**：`generate_target_profile.py --tag my-target` → `target_profiles.json`
3. **开启过滤**：
   ```bash
   export ARENA_PROBE_FILTER_ENABLED=1
   export ARENA_PROBE_TARGET_PROFILE=~/.local/share/finance-arena/target_profiles.json
   python -m intelligence.arena --db ~/.local/share/finance-arena/arena.sqlite3 run --agents agents.json --task task.json
   ```
   非目标模型的对战会自动失败，不会进入 `matches` 发布池，leaderboard 不会被污染。

4. **调阈值**：`report` 会输出会话内/间距离分布，`suggested_threshold` 是簇内最大距离*1.5，建议从 0.08 开始，太严会误杀，太松会漏。

## 扩展
- 可以支持多目标：`targets` 数组里放多个 centroid，比如同时接受 A/B 两个好模型
- 可以改成软过滤：不直接失败，而是打标 `eligible=0`，让投票时忽略
- 可以把探针从风格指纹升级为知识探针：对 Answer 额外问 `identity` 探针，综合判断

## 文件位置
- `intelligence/arena/probe_filter.py` 过滤器
- `intelligence/arena/runner.py` 已集成过滤
- `intelligence/arena/generate_target_profile.py` 生成目标配置
- `model_pin_probe/` 原始探针库
