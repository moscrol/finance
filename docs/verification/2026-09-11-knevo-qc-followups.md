# 2026-09-11 · knevo delta 质检复核与整改收据

分支 `feat/knevo-delta-readside`。上游是一份对 W1/W2/W3/W5 交付的质检报告。
本轮做两件事：**不采信质检方的红绿记录、逐条自己重跑**；然后修它点名的三处偏差。

## 一、复核结论

质检点名的四处偏差，我独立复验后**三处成立、一处的实证部分不成立**（结论仍成立）：

| # | 质检声明 | 我的验法 | 结果 |
|---|---|---|---|
| 1 | W2 漏了第三条真实出口：prime 前缀仍是旧形制 | 同一条台账记录分别喂 `judgments.render_for_prompt` 与 `user_memory._judgment_lines` | ✅ 成立，两边逐字不同 |
| 2 | D18 在 ask 生产路径没接 `on_date` | 读 `ask.py::_build_d18`；对比同文件 D0 的 `d0_on_date` 闭包 | ✅ 结构成立 |
| 2b | 实证「9 月 5 日哪些是秒板 → 块给 9 月 10 日数据」 | 拿生产库直跑 | ❌ **复现不了**，两种入参都返回空串——原因见下面第二节 |
| 3 | W5 双守卫注释的「分工」描述不实，守卫 B 不可达 | 三种 keyword（无 / 命中 / 不命中）各跑一遍 | ✅ 成立，不命中时回落全市场，rows 必非空 |
| 4 | W5 提交信息「`intelligence/services/` 无一处引用 `first_limit_time`」字面不实 | `git grep` 打到 `gitea/main` | ✅ 成立，`river.py` 与 `teaching_framework/{coverage,leader_succession}.py` 在主干就有 |

## 二、质检也没抓到的：D18 的源列已断供 8 天

跨日期 diff（不是数行数）：

```
2026-08-31  rows=1003  seal=1003
2026-09-01  rows=728   seal=728
2026-09-02  rows=527   seal=527
2026-09-03  rows=430   seal=0     ← 断点
2026-09-04  rows=292   seal=0
2026-09-07  rows=1003  seal=0
2026-09-09  rows=366   seal=0
2026-09-10  rows=280   seal=0
```

`fact_theme_limit_stock_daily.first_limit_time` 自 **2026-09-03 起连续 5 个交易日
全 NULL，行照常进**。这是 AGENTS.md 点名的「行在、值全 NULL」空壳，只抓行数的
覆盖率审计看不见——spec 写的「有 149,728 行非空」是**累计**读数，spec 落笔那天
（09-10）断供已持续 5 个交易日。

后果：

- **W5 交付在生产上目前是惰性的**。最近交易日走第一道守卫 `with_seal == 0` 直接
  返回空串。这也解释了为什么质检的实证复现不出来——不是它记错，是那条路径根本
  到不了渲染。
- G1b（`open_times` 恒 NULL）不再是孤例。`leader_succession.py` 的一字板判定
  （`seal_num is None or first_limit_time is None → "unknown"`）现在**两个输入同时
  为空**，此前只有一个。
- 上游补回后代码侧无需改动，块会自动恢复。

追上游要外呼 fupanhui / 同花顺比对 payload 字段名，不在本轮范围，**未做**。

## 三、本轮改了什么（三处，各带变异收据）

| 改动 | 落点 | 变异实测 |
|---|---|---|
| W2b 逐条归属补到 prime 出口 | `judgments.py::render_for_prompt` | 退回块级旧形制 → `test_judgments` 2 条 + `test_prime` 1 条红 |
| D18 接问句日期 | `ask.py::_d18_applies` / `_build_d18` | 删 `on_date=` 传参 → 红；删 `market_review_requested_date` 调用 → 红 |
| 两处失真注释改写 | `market_timeseries.py` | 注释，无断言 |

两条设计取舍：

1. **W2b 的前缀是 `[你的判断 …]`，不带 `M·` 命名空间。** prime 不是 [M] 证据块，
   冒用已注册的块号等于伪造引用出处。
2. **W2b 的测试钉在 `build_prime` / `render_prefix`，不钉渲染器。** W2 自己的教训
   就是「出口比渲染器多」（差点漏掉 `memory_lookup`）——只改渲染器而没接上 prime
   时，这条测试同样红。
3. **D18 的接线用 AST 对账，不跑 ask.py。** 闭包在 `_answer_query_impl` 内部，端到端
   要真跑一轮问答；`conformance_datablocks` 对装配面已是同一取舍（读源码不执行）。
   钉的是「参数在场 ≠ 被读」这个形状。

## 三点五、门禁读数（以及一处收据错挂）

本轮（`251a2cf6` + 上述改动）：

```
ruff check .   All checks passed!
pytest -q      9141 passed, 77 skipped, 1 xfailed  (323s, exit 0)
```

基线用 `--collect-only` 量而不是抄上一份收据：原树 **9217 collected**，本轮
**9219** —— 正好 +2，即新增的两条测试，没有别的东西混进来。

⚠ 顺带：`251a2cf6`（W6）提交信息自报「全量 9088 passed / 77 skipped / 1 xfailed」，
但 9088+77+1 = 9166 ≠ 该 revision 的 9217 collected。那份读数描述的是**加 W6 测试
之前**的树（与 `45be2a0b` 的收据一致），被挂到了 W6 提交上。W6 本身是绿的（本轮
在更高的计数上重跑证实），只是收据条件与 revision 不符——正是仓里「收据要带成立
条件」那条纪律要防的形状。

## 四、仍然开着的

- **W4（AB 双盲台账）**：spec 写「二选一，请用户定」，红线是不允许维持现状
  （目标 25 样本 / 实际 2 / verdict 逾期两月）。**未动。**
- **W2b 未回写 spec**：spec 文档在 `docs/knevo-e009-arch-delta` 分支上，本分支只有
  代码。该 spec 的 W2 做法一节写的是「`user_memory` 渲染改为条目级」，字面没圈
  prime——**这不是执行漏做，是评审时漏圈范围**。合并 docs 分支时补一行 W2b。
- **两笔本地 merge 无授权记录**：`f017580a`（polymarket-macro-odds-impl）与
  `45be2a0b`（feat/event-pricing-slice1）于 11:02 合入本分支。spec W6 与本分支
  12 分钟前的交接都写着「合并须用户确认」。合的是特性分支不是 main，也未推送，
  未触 main 红线，但自己声明的闸自己跳了。**待用户认账或回退。**
- **上游 `first_limit_time` 断供**：见第二节。
