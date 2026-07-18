# Workbench 产品成熟度最终本地验收

- 日期：2026-07-16
- 分支：`fix/workbench-product-maturity-p0`
- 范围：P0、P0.5、P1、P2 与 provider-chain 续验
- 结论：本地代码、隔离真实数据链和浏览器验收通过；尚未 push/PR/merge，尚未切换
  canonical 8792，因此不声明生产部署完成。

## 要求—证据矩阵

| 要求 | 当前实现 | 权威证据 | 判断 |
|---|---|---|---|
| “这个逻辑/方向/这条链/边际变化”追问不逃逸 | 统一 QueryResolver + owner/context 继承 | routing golden tests、P0 verification | 已证明 |
| “怎么看个股/板块”正确路由 | relation 指纹实体词典；公司→stock-deep-dive，题材→theme-research | query resolution/controller tests | 已证明 |
| stage 超时无后台幽灵任务 | 父调用返回前 structured join；超预算结果不缓存 | owner DAG timeout tests、P0.5 verification | 已证明 |
| Hybrid RAG 不重复冷启动 | 长驻 JSONL worker；超时 terminate/kill/restart；lineage 保留 | RAG worker tests + cold/hot 真实 smoke | 已证明，部署时须开启 |
| 行情不能以“目录存在”冒充 ready | complete + fresh/historical contract；partial/unknown fail closed | contract/API tests、旧 runtime 反例 | 已证明 |
| 外部 spot 故障时仍有治理后数据 | exact DuckDB → exact AkShare → prior DuckDB provider chain | 91 focused tests + 两条真实 `/tmp` smoke | 已证明 |
| partial 不污染 canonical | AkShare 只写临时候选；PASS 后才原子晋升 | partial isolation、old complete preservation tests | 已证明 |
| followups 展示与提交语义分离 | `{label<=20, full_prompt}` + 一周期 alias | API/component tests | 已证明 |
| 胜率面板不复制事实 | 从 verdict aggregate 投影；25 样本门；strict/partial 两口径 | forecast performance tests | 已证明 |
| 错因/批注不会自动污染 prompt | reflection/rule candidate 人工 approve/reject；fingerprint 绑定 | forecast learning/API tests | 已证明 |
| 桌面/平板/手机产品交互 | 五表面、BYOK、3 turns、owner followup、cancel/reload | Playwright 15/15 | 已证明 |
| canonical 8792 使用本分支 | 仍指向旧 `bb9754f` 软链 | readlink、live readiness | 未完成，需合并授权 |
| main/CI | 分支尚未发布 | Git remote/PR state | 未完成，需发布授权 |

## 真实 provider 验收

### 最新日路径

目标日 2026-07-16：

```text
duckdb_exact: unavailable (DuckDB 尚无 07-16)
akshare_exact: complete in 133807ms
provider=akshare_exact
market breadth=2498/2861
themes=26, strong_stocks=42
contract=PASS, ready=true
```

Eastmoney 先断连，Sina 慢路径成功。说明 AkShare 可以补最新日，但延迟和端点稳定性决定
它只能运行在后台 provider，不能进入用户请求链。

### 外部源失败路径

把 AkShare Python 指向不存在文件：

```text
duckdb_exact: unavailable
akshare_exact: failed in 1ms
duckdb_latest: complete in 24ms
requested=2026-07-16, served=2026-07-15
provider=duckdb_latest, freshness=historical
stock facts=5524, themes=4, strong_stocks=80
contract=PASS, ready=true
```

这证明历史降级是实际 provider 行为，不只是 mock 测试。requested/served 日期同时暴露，
因此 Presenter 可以诚实说“数据截至 7 月 15 日”。

## 回归证据

```text
Focused provider/API: 91 passed
Full Python clean env: 1831 passed, 1 skipped, 8 existing utcnow warnings
Frontend lint: PASS
Frontend typecheck: PASS
Frontend unit: 56 passed
Frontend production build: PASS
Playwright: 15 passed (desktop/tablet/mobile)
plist lint / zsh syntax / Ruff / diff check: PASS
```

Playwright 首轮因宿主 `FORESIGHT_USER` 泄漏失败；配置固定测试 server 用户为 `default`
后，在宿主变量仍已设置的条件下重跑 15/15。这是测试环境隔离修复，不是绕过失败。

## 尚未完成的生产门

1. 明确授权 push/创建 PR/合并 main。
2. 按 `docs/workbench/canonical-8792-cutover.md` 新建 clean detached runtime，原子切软链，
   不 reset 旧脏 runtime。
3. 在 canonical 数据根运行 provider chain，安装 LaunchAgent，开启
   `RAG_WORKER_ENABLED=1`。
4. 真实 8792 readiness、路由三问、followup、Validation 面板和 self-use smoke 通过。
5. local full-repo Registry `check` 的 knowledge-base 新 Skill 漂移需要独立回灌；本分支未改
   Skill，不把该跨仓债务混进 provider PR。

只有上述 1–4 完成后，才能声明“本地工作台已部署为成熟产品”。
