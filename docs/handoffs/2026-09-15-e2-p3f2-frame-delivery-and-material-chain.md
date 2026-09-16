# 2026-09-15 · E2 P3f2：基底缺失送达 controller + 材料链续问不丢 + flaky 根因

分支 `fix/e2-boundary-closeout`，提交 `e1fc53a7`。前一片 P3f1（a819ecde，材料历史从权威消息记录绑定）见 `2026-09-15-e2-p3f1-source-binding.md`。

## 背景（不读会误判后面每个决定）

E2 材料边界按 v10 分片收口。P3f2 的范围是三件事：controller 历史提示词、Episode 正文送达、基底（task frame）缺失时的前置澄清。独立审查这个可选步骤已被用户明确关闭（纠正 04834c55d72b），所以本片的收口标准是**作者自验**：真实入口反例 + 计数 + 保留失败，不再等任何审查服务。接手者不要把「没有独立 QC」当成本片的未完成项——那是用户拍的范围决定，且用户拍板时已知前三次审查全部因服务中断无报告。

「真实入口」的含义：反例必须走 `run_turn → 真实 decide_turn → Episode 装配` 全链，不允许 mock controller 或手搓 frame 绕过装配层。P3f1 的教训是 mock 层反例全绿、真实入口一跑就漏。

## 按发现顺序

1. **接续点校验**：上一 session 的 7 个未提交文件先重跑旧回归，241 passed + Ruff 通过，确认接续点干净后才动新代码。
2. **补 7 个真实入口反例**（`test_e2_material_turn_delivery.py`）：注入旧 frame、基底缺失五态、补贴材料链。首跑 7F/16P，抓到两个真 bug（见决策 1、3）。
3. **顺带补齐 D4 同源过滤**：material_only / 待澄清轮不再做昵称解析与日历先验注入——这两个注入是给「真问题」轮准备的先验，在材料轮上只会引入无关上下文。
4. **flaky 定位**：`[injected_frame=True]` 用例间歇性 `ValueError: root budget already exists`。根因不在产品代码：两个参数化用例共用硬编码 `task_id="real-entry"`，而根预算注册表是 `WeakValueDictionary`（条目随对象被 GC 回收而消失），是否撞号取决于上一个用例的 traceback 何时被回收——traceback 持有异常对象、异常对象持有栈帧、栈帧持有预算对象。修为每用例唯一 id。
5. **接手 session 复核 + 提交**：Ruff 8 文件通过；两个测试文件 48P；e2 + 全部改动模块测试集 683P/4S/0F（收据 `20260915T095004Z` / `20260915T095034Z-6278caea`）；pathspec 提交 e1fc53a7，11 道 pre-commit 全过（层级审计 ERROR 0、路径/字段/工具可达性均无新增违规）。

## 决策与被否方案

### 决策 1：已知缺失的基底怎么送达

| 方案 | 评价 | 结果 |
|---|---|---|
| 运行时不丢「已知缺失」状态，送达默认 controller，由它在 resolver/模型前发起澄清 | 澄清职责留在 controller 一处；五态中不可恢复态有了唯一出口 | **选** |
| 运行时直接回落普通解析器/模型路径（原行为） | 用户拿到一个装作没缺材料的答案，不可恢复态被静默降级——这就是反例抓到的 bug | 否 |
| 在运行时层直接生成澄清文案 | 澄清逻辑出现两份，controller 的对话职责被绕过 | 否 |

### 决策 2：旧签名 controller 兼容

| 方案 | 评价 | 结果 |
|---|---|---|
| 签名探测：新参数只传给声明了它的 controller | 注入式旧 controller（测试/外部装配）零改动继续工作 | **选** |
| 给 controller 协议加必需参数 | 所有注入式旧 controller 立刻破；这是公开注入点，不是内部接口 | 否 |

### 决策 3：材料链什么时候重置

| 方案 | 评价 | 结果 |
|---|---|---|
| 只有「带来新材料、或不指代材料的新问题」才重置；material_only 留在链内 | 「这篇怎么看」式续问保住已有链 | **选** |
| 任何新问题都重置（原行为） | 指代式续问被误判换题、链被丢——反例抓到的第二个 bug | 否 |
| 永不重置 | 真换题后旧材料继续污染新题 | 否 |

### 决策 4：flaky 修在哪一侧

| 方案 | 评价 | 结果 |
|---|---|---|
| 测试侧：每个参数化用例唯一 task_id | 产品语义本来就是「活跃预算对象存在期间禁止同 id 重建」，弱引用是特性 | **选** |
| 产品侧：WeakValueDictionary 换强引用 dict | 会把「检测并发重复」改成「永久占号」，改掉的是设计而不是 bug | 否 |

## 验证与收据

- 上一 session（作者机上）：聚焦三文件 ×10 连跑 50/50；E2 相关 16 文件 446P/4S；审计启动器（禁止 IO 计数）50P、禁止尝试 0。
- 本 session 提交前复核：Ruff 8 文件通过；`-k 'e2 or turn_controller or task_frame or conversation_materials or episode_factory or material_contract or conversation_orchestrator'` 683P/4S/0F，收据 `~/.finance-runtime/test-receipts/20260915T095034Z-6278caea.json`。
- 不成立的读法：683 与 446 是两个不同选集（本次 -k 口径更宽），不可跨口径比数；作者自验不等于独立 QC；以上均不覆盖最终答案质量（P4/P6）、正式 T2→T3/Knevo、全仓 pytest / 前端 / E2E 合入门禁。

## 可迁移知识点

用弱引用注册表（`WeakValueDictionary`）做「并发重复」检测时，测试里的固定 id + 异常 traceback 滞留会让结果依赖 GC 时机——这类 flaky 的排查入口是「先让被吞的异常带着 traceback 打出来」，然后问「谁在意外持有本该被回收的对象」。已沉淀 `~/agent-memory/10_knowledge/`。

## 后续要做的

1. 门页 `docs/agent-product-door.md` P3f2 段落更新（与本提交同分支）。
2. 余下 P3 旁路：静态路由 / 日历 / 未知基底 / 旁路；local_only 更多 runner 与原题号槽。
3. P4–P7；合并回 main 前跑全仓等价 CI（ruff + pytest + 前端四连），等用户确认。

## 不要做的

- 不恢复「P3f 清空历史」——已被反例反证并撤回（见 P3f1 快照）。
- 不把可选独立审查升级为硬门槛、不再启动独立审查者或等服务恢复——用户已拍（纠正 04834c55d72b）；擅自升级等于推翻用户决定。
- 不保存材料正文进 frame、不改 controller 历史提示词语义——坐标≠事实证据≠权限的边界仍在（P3f1 快照的理由未过期）。
