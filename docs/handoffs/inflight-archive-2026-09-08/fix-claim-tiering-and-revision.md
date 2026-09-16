# fix/claim-tiering-and-revision

## 这个分支做什么

补 #144（已合 `96446a93`）漏掉的三件：修订轮失联、一条内容闸被当形式闸降级、
以及旧链那道罚空气的绑定闸。**PR #146 open，未合。**

## 决策与被否方案（一句话版，展开见 `docs/handoffs/2026-08-17-delivery-gate-session.md`）

| 决策 | 否掉的方案 | 为什么 |
|---|---|---|
| 绑定闸「契约没下达就不问罪」 | ①直接删掉这道闸 ②给 prompt 补 marker 语法 | ①删了回不来 ②旧链是 fallback，为降级路补一套 claim 契约不划算（用户拍板先做便宜那半） |
| 判据从 prompt 自身算 | 写死 `False` / 加 env 开关 | prompt 哪天教语法，闸自己回来，不靠谁记得 |
| 问罪逻辑放 `ask_synthesis` | 放 `answer_model`（第一版就是） | 那层有三个消费方，全局标志会误伤另两个——**全量测试抓到的** |
| 已取代证据「降桶标注」 | 提回 `error` 整答退稿 | knevo 三桶：降级要让读答案的人看见，不是记在 warnings 台账里 |

## 当前状态

已提交并 push 到 `c7623ff5`：降桶标注、修订轮触发+采纳门槛、草稿回传、契约豁免、
遥测 `claim_binding_issues_before/after`。工作区干净。**未合 main，未切 8792。**

## 已验证

全量 `intelligence/tests` **4771 passed / 12 skipped / 0 failed**（clean @ `3cbdc245`）。
七条守卫逐条变异证伪，正反成对。三发 live 收据在
`~/.finance-runtime/claim-tiering-20260817/`（跑法见同目录 `run_live.py`）。

## 未验证 / 已知边界

- **降桶标注 live 一次没压到**：三发都没出结构化 claim，只有单测覆盖。
- 三发 live 耗时 204.9/267.8/218.4s 被检索方差主导，**n=1 不许读快慢**。
- 修订轮「契约下达后能不能真改对」仍是未知——本轮把它豁免了，没验证过它有效。

## 下一步

1. 批 #145（账实更正）与 #146。两个都 open/mergeable。
2. 要验降桶标注，得造一发带 superseded 证据的题。
3. 若哪天要让旧链真走 claim 契约：改 `_SYNTHESIS_SYSTEM_PROMPT` 教语法 +
   `build_synthesis_messages` 注入 registry，闸会自己回来，然后重跑 live 看绑定率。

## 踩过的坑

- **变异测试前没先提交实现**，`git checkout --` 把实现连同变异一起还原了，重做一遍。
- **目标测试全绿≠没坏**：4 个文件绿的时候全量是红的，误伤在另外两个消费方。
- `--timeout` 这仓没装插件，且管道到 `tail` 会把 pytest 的退出码吞成 0。
