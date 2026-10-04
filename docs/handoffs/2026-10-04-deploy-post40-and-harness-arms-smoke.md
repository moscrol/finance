# 合入部署 #40 与 G 列对照冒烟（2026-10-04 晚段，Claude）

承接同日上午段的 `2026-10-04-claude-takeover-closeout.md`。

## 背景

- **用户指令**（17:07）：「合入39和40，回收那2棵树。然后arena先让他去跑一跑，我想用arena做一下对照试试。然后我想了下，
  是不是我glm用8792和glm用pi也要做一下这个harness的对比」。
- **17:14 选项回答**：arena 当一个对照臂；GLM 用 8792 对 GLM 用 Pi「先打通并冒烟」；#40「部署」。
- **授权来源**：会话转写 `…kind-engelbart-aa727f/bec914d0-….jsonl` 第 1233、1316 行。部署收据里记了路径与时间戳。

## 按顺序做了什么

1. **合入。** #40 合入为 b550f42af，#39 合入为 bd2c58b37；两者 5 项 CI 全绿后才合。合入后 GitHub 本地备份 runner 跑出 success，
   gitea main 等于 origin main。
2. **回收用户点名的两棵树**（fwp-wt-harness-simplification-1002、fwp-wt-pr16-qc-1002）。先对新 main 重跑 dry-run，再 apply：
   拆 2 棵，失败 0，释放 +0.72 GiB；分支保留，打了归档钉。
3. **部署 bd2c58b3775f**，按 `docs/workflows/acceptance-workflow.md` §3–§4：
   - 快照树门禁：全量 20399 passed / 0 failed，`check_test_receipt --expect-revision gitea/main --base-drift-max 5` exit 0；
     前端门禁 exit 0 / complete / identity_stable / dirty=false。venv 与 04799 一样软链 ffe1，04799 到新 SHA 之间依赖文件零差异。
   - 切前：在役快照 0 处改动，账本 homes ok，health 正常。
   - 链切五步：bootout 后轮询到服务注销、端口释放（1 秒）再 bootstrap，约 25 秒 ready。
   - 切后三验：readiness 13/13；health 三读正确，监听进程 cwd 是新快照；账本 check 与 homes ok。
   - 探针：
     - 长电题：`fact_stock_daily` ×20，数据日 09-30 等于库内最新，无降级。
     - 同一道材料新闻题切前、切后对照：切前 3 轮、被拒 2 次（一句一 claim，然后引用不逐字），修复后交付；切后 1 轮、0 拒收，首稿交付。
   - 备份 `~/backups/gitea-20261004-post40.tar.gz`（4.35 GiB，gzip -t OK）。
   - 收据 `~/.finance-runtime/live-probe-traceability/deploy-post40-8792-run_20261004_173830_141526.json`。
4. **G 列冒烟**，实验包在 `~/.finance-runtime/harness-arms-20261004/`（README、MANIFEST）。
   - Pi 变体：Pi + `glm-5.3-flash`，只挂 `finance_call`，驱动控制台副本，组件钉 bd2c58b3775f。
   - P：新 8792。
   - D1 各 1 次：Pi 7/7，P 6/7。判分器用 10-01 恢复件，经只读包装调用。
5. **arena 对照臂任务包** `ARENA-ARM.md`：同一控制台、同一份数据，禁区写明；等用户重启 arena 交给它。
6. **自我更正**：一开始把 Pi 写成「F1 已通」。实际上预注册的 R 在 10-01 已是 `intelligence/eval/thin_react.py`，
   Pi 是另一种薄外壳。任务板 5 已更正，预注册追加了 10-04 修订。

## 决策与被否方案

| 决策点 | 方案 | 评价 | 结果 |
|---|---|---|---|
| 部署哪个 SHA | PR 头 d940a287f | 规程要求门禁跑在 main tip 上，不许拿分支收据凑数 | 否 |
| | main tip bd2c58b37 | 只比 PR 头多文档，代码同；在快照里重跑全量 | 采用 |
| venv | 新建 | 依赖零差异，新建只增加不确定性 | 否 |
| | 软链 ffe1（同 04799） | 与回滚点同一环境；ffe1 已上锁 | 采用 |
| 探针 | 只跑长电题 | 规程要求改运行时行为的上线做前后对照 | 否 |
| | 材料题切前切后 + 长电题 | 前者验行为变化，后者验数据口径 | 采用 |
| Pi 隔离 | sandbox 黑名单 | 答案散在 analysis、arms、docs、reviews 多处，堵不全 | 否 |
| | 只挂一个自定义工具 | 物理上读不到文件；也对齐 8792「只有工具、没有 shell」 | 采用 |
| 控制台组件 | 保持 08-27 的 40fd | 与 P 不同码，工具实现会混进对比 | 否 |
| | 钉 bd2c58b3775f | 与 P 同码 | 采用 |
| 判分器 | 直接跑恢复件 main() | 写死旧四臂，默认覆盖旧 analysis/ | 否 |
| | 只读包装复用 score_case | 判分函数不变，哈希校验后 import | 采用 |
| Pi 全局配置 | 改 models.json | 17:14 有人刚加了 GLM 配置，会互相覆盖 | 否：只用命令行参数 |

## 验证与收据

- 部署：见上面的收据 JSON；门禁收据 `test-receipts/gate-2eUm3mTe/`；前端收据
  `~/.finance-runtime/reviews/claude-takeover-20261004/deploy-bd2c58b37/frontend-gate/frontend.json`。
- 冒烟：`harness-arms-20261004/scoring/smoke-D1-RvsP.json`；Pi 会话与事件流在 `arms/react-glm-pi/D1-…/pi/`；
  P 的 run 是 `harness-arms-p-glm-1004/run_20261004_174122_633956`。
- **不成立的结论**：
  - 冒烟 n=1，不比高低。
  - 材料题切后首稿通过可能有采样运气，只证明「一句一 claim」拒收在机制上没了，不证明内容更对。
  - P 的 workflow 路径没有身份证据。

## 下一步

1. **开跑 G 列批量前要用户定**：
   - P 的分流（按生产分流并分引擎报告，或强制同一引擎）；
   - G 是否按路径钉模型；
   - 两臂（P、thin_react R）还是三臂（再加 Pi）；
   - 预算：120 或 180 次。
2. **补 F3**：Pi 加记录响应体 model 的本地代理；P 的 workflow 路径落 served_model，或为它写只读适配器。然后在预注册冻结各臂哈希。
3. **arena**：用户重启后把 `ARENA-ARM.md` 交给它，先跑 D1 冒烟，再用 `score_arms.py` 出分。
4. arena 的 PR #38 仍开着，没有评测；可作为 P 的一个变体放进 G 列对照。
5. FINANCEWORKS-6 的下一个交付因素是输出 schema 违规；内容推理错另立因素，优先供给信息与工具。
6. 修 `worktree_safety` 的祖先目录前缀误报，再回收剩余可回收树。

## 不要做

- 不把冒烟读数写成「Pi 比 8792 强」。
- 不改 Pi 的全局 `models.json` / `settings.json`。
- 不跑恢复判分器的 `main()`：它会覆盖 08-27 的 analysis/。
- 从 `origin/main` 切出的分支上游是 main，推送必须写全远端分支名，不用裸 `git push`。
- 不拆 04799 快照（回滚点）与 ffe1（生产 venv 来源，已上锁）。
