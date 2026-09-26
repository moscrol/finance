# feat/e2-p5-cross-turn-inheritance

## 这个分支做什么
E2 分片 P5（D7）：把 A7 的逐轴继承五格压到**真实链路**（run_turn → 真实 decide_turn → TaskFrame → Episode 上下文），并修沿途暴露的两处继承缺陷。只动本树，从 `gitea/main@801d0fc2` 开出。

## 决策与被否方案
- 同值重申幂等：按 `(text_ref, authenticity, scope)` 去重、保留**最早**轮次；否只按 text_ref 去重（同句不同作用域是不同附着），否保留最新轮次（会让前提来历随重申漂移，且与既有注释相反）。
- 题级标注跨轮唯一：作用域渲染成 `轮次1的q3`；否丢弃题号已不在本轮的继承标注（前提仍生效，丢了就丢状态），否只靠同行的 `轮次N` 字段（要读者自己拼，正是误读来源）。
- 测试停在控制器之后再装配 Episode；否在 adapter 处断言（换轴放宽后主语不可解析会合法走澄清车道，把 P3 分流混进 P5 继承）。
- 展开与被否方案全表：`docs/handoffs/2026-09-16-e2-p5-cross-turn-inheritance.md`。

## 当前状态
提交 `fc9a130b`（2 个生产文件 + 1 个新测试文件），树干净。未推送 / 未合并 / 未部署。生产 8792 仍是 `6e23dd57`，本片不重切。

## 已验证
python 全量 `fc9a130b`：ruff 0、pytest 10963P/0F/81S/2xfail（467s）。定向回归 580P/4S。新反例 11P（先红 2 条真缺陷）。registry 五条 0。删保护变异 3/3 红、还原后回基线。frontend/e2e 读数见日志根 `~/.finance-runtime/e2-p5-20260916/`（`fe-*.rc`、`e2e.rc`）。

## 未验证 / 已知边界
作者自验非独立 QC，判官全是离线替身。本片没有新写 D7.3/D7.4/D7.6，只是用反例锁住既有实现。A7/A14 的**正式**验收资格仍在 P7（要全新会话、原始 T3 文本、不重贴禁令）；本片用的是构造查询 + T2/T3 夹具。两轴放宽成 full 后主语不可解析走澄清，是既有行为，未改也未论证。D6（条件化纯度 / 材料锚点 / 历史句排除）整片未动。

## 下一步
1. 合并要用户确认（AGENTS.md 硬规则）。合并前重跑 `merge-tree` 探冲突，再 `check_test_receipt.py <收据> --expect-revision <合并头> --base-drift-max 5`。
2. P6（D6）是下一片：条件化纯度 + 逐事实材料锚点 + 历史助手句正式排除，收口点在 `build_episode_input`；设计稿 §3.6 与 A3/A10/A12 是判据。
3. grounded 探针欠一次：Sub2API 上游今天 502/503/429，脚本在 `~/.finance-runtime/switch-20260916-6e23dd57e965/grounded_probe.py`，网关恢复后按 `docs/handoffs/2026-09-16-8792-switch-6e23dd57.md` §4 重跑。

## 踩过的坑
`run_turn` 把管线异常折成 `status=failed` + 空正文：不装 `_fail` 探针就看不到堆栈，夹具错误会伪装成产品缺陷（本轮 7 红里 4 红是夹具）。多个测试共用同一个 `task_id` 会撞 root budget 账本（`root budget already exists for live episode`），每次装配要唯一 id。E2E 端口：本机常有多个 session 并发，用 `WORKBENCH_E2E_PORT` / `RE06_E2E_PORT` 避开 8791/8794。
