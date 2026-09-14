# feat/river-correction-hardness

## 这个分支做什么

补上时间长河 G-02 对象契约的**后半**：`hardness` / `expired_at` / `superseded_by`。此前
「纠正通过新对象表达、不覆盖旧记录」只能执行前半句——能 append-only 写，读的时候滤不掉
被取代的旧对象。基线 `gitea/main@1fef3d27`。

## 决策与被否方案

| 决策 | 否了什么 | 为什么 |
|---|---|---|
| `frozen_llm` 超 L1 时**封顶** | 否了构造时报错 | 契约说「封顶」不是「禁止标注」；报错会让上游为了过构造去改判据 |
| 两个 NULL 反向处置；失效判 `<=` 非 `<` | 否了统一按不可判滤掉；否了 `<` | 契约明写 `expired_at` null=现行，统一滤掉会让所有对象消失；`<=` 与 `recorded_at` 对齐，纠正与被纠正者不并存 |
| `HARDNESS_RANK` 下沉到 `river`，投影层删本地那份改 import | 否了两层各留一份 + 一致性测试 | 那是第二事实源；`river` 零 intelligence 依赖，是天然共同底座 |

## 当前状态

`1ee6a881` 已提交，未合 main。**只加载体，不给任何 track 填 `hardness` 值**。

## 下一步

1. **给各 track 填 `hardness`**（`_market_track` / `_opinion_track` 等构造点，逐轨判证据等级）。
   ⚠ `ProjectedBlock.hashed_dict()` 含 `hardness` 且进 `projection_hash`——填值后投影哈希会变。
   不是 bug（硬度本就是选择依据），但要预期到并重绑基线。
2. roadmap:130 映射表里依赖 `expired_at`/`superseded_by` 的三条（快照、证据边、`memory_status`）
   现在有载体了，可以接上。
3. G-02 验收 (i)「五种现有状态字段各有一条到契约的映射测试」**仍未做**。

## 未验证 / 已知边界

- **没有任何生产者填 `hardness`**，「硬度降序」今天仍全部平局。本轮只证明载体就位 +
  消费者读得到（`hardness_of` 的 `obj.get("hardness")` 分支此前永远取不到值）。
- `superseded_by` **只是指针，不参与过滤**；指向不存在的 ref 无检查拦截。各 track 构造点
  （`_market_track` 等）与 `river_frozen` 快照回放路径本轮未压到。

## 踩过的坑

**变异测试前必须先提交。** 拆门用 `git checkout -- <file>` 还原，而实现当时**未提交**，
还原点是 HEAD——连同实现一起清掉了。门 2/3 于是跑在原版代码上，读数无意义且差点被当成
「测试不承重」。重放、提交、再拆门才拿到三门全红。

## 已验证

- **全量 9628 passed / 0 failed / 77 skipped**，354s；`ruff check .` 全绿。收据
  `check_test_receipt.py --expect-revision 1ee6a881` **七项全过**（干净树、解释器与依赖指纹一致）。
- **三门变异各自见红、还原后树干净**：拆 `expired_at` 过滤 → 3 failed/8 passed；拆
  `frozen_llm` 封顶 → 1/10；投影层造本地常量副本（值同、对象不同）→ 1/10。后两门各红
  1 条是各自只有一条断言覆盖，不是门弱；第三门证明 `assertIs` 防的是**漂的起点**。
