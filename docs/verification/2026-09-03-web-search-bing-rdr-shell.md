# `web_search` 一直在拿 Bing 的缓存壳：结果页两步到达，解析器在第一步就收了（2026-09-03）

能力放大线交接的下一步 ①是「库里没有的题跑两臂验 `web_search→web_fetch` live 链路」。开跑前先离线直调
`web_research.fetch_web_search` 看搜索后端能不能给出有数的 snippet，结果发现链路在模型之前就断了：
**`web_search` 返回 `status=success`、5 条结果，但内容与查询无关**。本收据记发现顺序、机制、修法、读数与边界。
对应 PR：`fix/web-search-wait-for-rdr`。

## 1. 发现顺序（一手，当天 13:40–14:10）

1. `fetch_web_search("腾讯控股 2024年 全年 营业收入 亿元")` → `success` 5 条，全是 v.qq.com / qq.com / tencent.com 首页。
   同法 5 道题（腾讯 / 小米 / 拼多多 / 阿里）全部只回实体官网导航页；「拼多多 2024年 全年营收」甚至回伊朗战争新闻与期权 Theta 文章。
2. 直连代理逐秒采样同一页：`/new` 返回后 `document.title` 与搜索框都是完整查询，`li.b_algo` 10 条却是无关结果；
   约 2 秒后 `location.href` 变成 `…&rdr=1&rdrig=<id>`，页面重载，之后 `li.b_algo` 才是真结果（小米 3659 亿 / 平安 IR 页）。
3. 第一遍页面带 `_G.JCache=1`（Bing 的实体缓存壳），跳转后仍是 1 → **`JCache` 不能当判据**；`href` 里的 `rdr=1` 能。
4. 顺手查到 9222 上那台 Chrome for Testing 以 `--headless=new` 起，UA 自带 `HeadlessChrome/151`。改 UA 重启后（见 §4），
   壳的内容从「与实体无关」（伊朗战争）变成「实体导航页」，但仍是壳、仍走 `rdr` 跳转——UA 不是根因，解析时机才是。
5. 会话跑热约十分钟后，同一批查询首屏即真结果、不再跳转。也就是 Bing 的「壳 → rdr」是新会话的 cookie 引导流程，
   何时走它取决于 Bing 侧状态，代码不能假设一定有或一定没有跳转。

## 2. 根因

`web_research._fetch_web_search_uncached` 的轮询：`/eval` 取 `li.b_algo`，**首批非空即 break**。`/new` 返回时页面已
`readyState=complete` 且有 10 条壳结果，于是每次拿走的都是壳。`ProviderTrace` 的 success / empty / error 三态对
「success 但内容错」不可见——这条 web 路径此前零 live 调用（09-02 茅台题两臂 9 次调用零次 web），没人看过它的结果。

## 3. 修法（`intelligence/services/web_research.py`）

- `/eval` 脚本一次带回 `{href, ready, items}`（抽成 `_bing_page_state_script(limit)`）。
- 收结果的判据：**`href` 含 `rdr=1` 且 `readyState=complete`**（主路径，detail=`settled after rdr redirect`）。
- 没观察到跳转时：同一批结果**连续稳定 3.0s** 才收（兜底，detail=`no rdr redirect; results stable`）。
  实测跳转在首屏后 0.9–2.1s 内发生（n=4），3.0s 留了余量；代价是无跳转时每次搜索多 3s。
- 到 deadline 仍没跳转、结果又在变：把最后一批交出去但 detail=`unsettled: …`，让产物看得出这一批不可信。
- `/eval` 回的不是预期形状 → `parse_error`，不再当 `[]` 静默轮询。
- 轮询间隔 1.0s → 0.3s（跳转窗只有 ~2s，1s 太粗）。

否掉的：① 只加固定 sleep——跳转时机不定，且会话热了以后根本不跳转；② 拿 `_G.JCache` 当判据——前后都是 1；
③ 换搜索引擎——超出本线范围，且问题是解析时机不是 Bing 本身。

## 4. 仓外改动（本地基础设施，不受版本控制）

`~/scripts-local/chrome_debug_agent.sh` 加 `--user-agent`（默认与本机 Chrome 版本一致、去掉 `Headless` 字样；
置空 `CDP_USER_AGENT` 还原），`launchctl kickstart -k` 重启了 `com.financeworkspace.chrome-debug`。重启前确认：
无 `market_feature_store` / fupanhui 任务在跑，代理只开着一个 `chrome://newtab`。profile 不变，cookie 保留。

**归因老实说**：改 UA 前后壳的内容不同（无关页 → 实体导航页），改后约十分钟 Bing 开始首屏给真结果；但样本只有
十几次查询、且与「会话跑热」同时发生，分不开。可以断言的是：**不改解析时机，UA 怎么改都还在拿壳**（§1 第 4 步）。

## 5. 读数

| 项 | 改前 | 改后 |
|---|---|---|
| 腾讯控股 2024 营收 | v.qq.com / qq.com / tencent.com 首页 | 头条「营收 6603 亿元」/ Reportify 年度业绩 |
| 小米集团 2024 总收入 | mi.com 官网 / 商城 / 小米汽车 | 「总收入 3659 亿元」×3 |
| 中国平安 2024 营收 | （直连采样）首屏「中华人民共和国_百度百科」 | 平安 IR 财务报告 / 新浪公告 / 澎湃 |
| 长江电力 2024 年报（从未搜过） | — | 新浪公告 / 东财公告 |
| Tencent 2024 revenue（英文） | Yahoo Finance 混「Pervasive Developmental Disorder」 | 腾讯官方 2024 全年业绩公告 PDF |

单测 `intelligence/tests/test_web_research.py` 新增 5 条：壳→rdr→真结果序列、无跳转稳定兜底、到 deadline 未稳定的
`unsettled` 标记、`/eval` 形状错 → `parse_error`、拼接 JS 括号配平（这一条防的是本轮真踩的坑：多一个 `}` 让代理回 4xx，
桩掉代理的测试看不见）。变异「首批非空即收」→ 3 红。

整仓门禁读数见 PR 描述与 `~/.finance-runtime/test-receipts/`。

## 6. 对交接下一步 ① 的含义

- 「web 链路零 live 调用」这条边界现在有了第一个读数：**链路在 `web_search` 这一环就断着**，与模型选不选工具、判官删不删句无关。
- 两臂实验必须在含本修复的快照上跑；在 `c88c81da5120` 上跑，模型拿到的是壳 snippet，读数只会是「web 无相关结果」，不是链路的读数。
- `web_fetch` 这一环本收据没验（它取的是 `web_search` 给的 URL；URL 对了才有意义）。

## 7. 不成立的结论

- 不能说「web_search 修好了」——修的是解析时机；Bing 侧壳 / 跳转行为随会话状态漂移，本收据的 live 读数是 09-03 下午一个会话里的十几次查询。
- 不能把 3.0s 稳定窗当最优值：它按 n=4 的跳转延迟定，若日后 detail 里 `unsettled` 变多，先看 `rdrig` 跳转是否被更慢的流程替代。
- UA 改动对 Bing 结果质量的贡献量级不明（§4）。
