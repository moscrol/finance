# feat/ablation-noise-floor

树 `/Users/a77/fwp-wt-ablation-noise-floor`，基于 `gitea/main@19c77a16`。
**未合 main、未推、未动 8792/8796/8802。**

## 这个分支做什么

起因是「8796 解耦线还有哪些组件能做成可开关、这形式适不适合消融」。盘完发现
瓶颈不是开关数量——是**读数没有方差底**，以及**登记表漏了几条真缝**。

### ① 消融读数加当次实测方差门（`192c2fd5`）

`run_quality_ablation.py` 此前直接输出 `marginal_contribution_total`，没有任何
方差门。2026-08-26 那轮据此报出 `reading-baseline −0.4` 并写进交接文档
「建议默认关或按题型门控」；两天后（`2026-08-28-shared-memory-plane-design.md` §6）
实测同一批判官对**逐字相同**的答案能打出 12/13/15，散布比那个 −0.4 大一个量级。

该设计稿已把结论写成可迁移原则：**每轮盲评故意塞一对相同答案实测当次方差，
不引用历史噪声底。** 本轮把它落成执行件。

- `judge_noise_floor()`：每题基线答案额外重复盲评（`--calibration-repeats`，默认 2）。
  只花 judge 调用，不花 ask。
- 门槛按各组件自己的可用题数现算：`SE = sd_judging×√2/√n`，阈值 `sigma×SE`（默认 2）。
  可用题少的组件本就该要更大的 Δ。
- 比较规则复用 `variance_baseline.ab_decision`，不另写一份 if。
- **fail-closed**：未实测方差（重复 0 次 / 全 unscored / 旧收据）**一律 `no_call`**，
  不回退历史噪声底。补评脚本沿用源轮那份底，不凭空新给。
- 覆盖面限定随读数入收据：只含**判官复评**方差，**不含 ask 侧重跑方差**，
  是噪声**下界**——跨过它是必要条件不是充分条件。

**2026-08-26 那三份读数的正确判定：全部 `no_call`。**

> ⚠ 本节初版写的是「按当次噪声重判：+2.8 callable / +1.5 no_call / −0.4 no_call」，
> 底用的是 2026-08-28 那组同文本 12/13/15（sd=1.53）。**那是引用历史噪声底——
> 本单的核心规则恰恰是不许这么做。** 2026-08-31 质检点名，此处已改。
> 生产路径没破（缺校准一律 `no_call`，fail-closed 拦住了），破的是叙述层。
> 教训归档进 [[low-sampling-on-high-variance]]：**规则写进代码之后，
> 自己的回溯表也归它管。**

08-26 那轮**没有做同文本校准**（当时还没有 `--calibration-repeats`），
所以三份读数一份都判不了，与 Δ 多大无关。顺带纠正一处数字：
kb-rag 的可用题是 **4** 题不是 5（收据 `questions_usable=4`），
门槛该按 n=4 算成 ±2.16。

**`reading-baseline` 的「负贡献」不成立**——这条结论不变，但**证据要换成更硬的那份**：
同一批 7 份收据里它的 Δ 是 `−0.4 / +1.167 / −2.0 / −0.2 / +1.4 / −1.0 / −0.667`，
**变号三次**。一个跨轮变号的量，谈不上「稳定负贡献」，不需要噪声底就能说。
据它做的默认关 / 题型门控提案应撤回，不是延后。

已知同族遗留：`knowledge_injection_policy.py:6` 写着「主线题七次读数全部 ≤0，
均值 ≈ -2.3/20」。上面那 7 个是**聚合**读数、不是主线题切片，两者未必同一组；
但「稳定负贡献」这个措辞在聚合层面已被证伪，该切片是否真全 ≤0 **本轮未验**。

### ② 补登三行运行时缝 + 修 reading-baseline 漏掉的关法（`fb2a9b2a` → `ca7633aa` 修正）

新 kind `lane`（选走哪条执行路的缝；不归 `parameter`——那类是 argparse 默认值，
拨了不改行为）。三行**均为登记行，正控留空、不进臂、排除在 `default-v1` 之外**
（棘轮 #3；盒的生产断言 `ambient_ids`/`non_tool_defaults`/`capability_source`
逐字节未变，只有 `excluded` 多三条自述原因）。

| id | 为什么补 | 关法实测结论 |
|---|---|---|
| `fast-path-runner` | 确定性快路 vs 模型路的分水岭，本板最大的漏网 | **构造注入不是 off，是中止**（见下） |
| `repair-chain` | R-20260824 实测 repair 会「删真话留拼接伤」，净贡献是真问题 | **cap=0 不是关，是回到默认帽**（见下） |
| `evidence-judge` | 质量臂测出的最高边际贡献（+2.8）此前不在板上 | `env:ASK_EVIDENCE_JUDGE=off`；结构臂无收据字段，可观测面在质量臂 |

另修 `predicate.reading-baseline`：`enabled()`（`reading_baseline.py:373-388`）是
contextvar 与 env `FINANCE_READING_BASELINE` **两道门任一关闭即关**，登记原先只列了
contextvar。§5.2 定的「多个关法必须全列」`followup-composer` 和 `l3_lookup` 都照做了，
就这行漏了——而质量臂用的正是 env 那条。

## 踩过的坑（两条都是自己踩的，已钉成测试）

**坑① 构造参数长得像缝，不等于是缝。**
初稿给 `fast-path-runner` 写了 `constructor_injection:fast_path_runner`。核符号时证伪：
路由决定在 `continuous_turn_adapter.py:337` 的
`frame.question_type in CONTINUOUS_FAST_PATH_TYPES`，发生在调 runner **之前**；
注入抛异常的 runner 被 `:359` 就地捕获 → `status=failed`，而 `execution_kind`
**仍是** `deterministic_fast_path`。拿它当 off 会得到降级的一集且正控恒不变——
与设计稿 §3 记的 `semantic-verifier` deadline 陷阱**同形**。
覆盖面也写大了：`FAST_PATH_RUNNER_SUPPORTED_TYPES` 只有 `market_technical` 一个题型；
四臂 A5「涨停题材 0.6s 零模型」走的是 market_watch 确定性包，**不是本路**，初稿把两条
lane 混为一谈。

**坑② fail-safe 会把「关」吃掉。**
初稿给 `repair-chain` 写了 `repair_seconds_cap=0`。`repair_coordinator.py:36-42`
`_resolve_seconds_cap` 明写「None / 非正数 → 默认帽。fail-safe：坏输入不该把窗口
静默压成 0」，所以 0 → 30.0，与不拧**逐字节相同**；env `ASK_REPAIR_SECONDS_CAP`
走同一条解析，同样关不掉。把 0 当 off 会产出「拧了、没变、正控空」的假失败读数。

> 两条的共同外壳：**把「我能传一个值进去」当成「我能关掉它」**。
> 设计稿 §11-4 的「宣称某行已接线先 rg 那个符号」照做就能抓到，两次都是照做才抓到的。

**坑③（流程）变异测试前必须先提交。** 第二批修正没提交就跑变异，
`git checkout --` 把未提交的修正一起 revert 了，复原后 4 条红。已重做并先提交再变异。

## 验收

- 全量 **7325 passed / 15 skipped / 1 xfailed / 0 failed**（`.venv-workbench`，
  `umask 022` + `env -i` 透传壳），对 `ca7633aa` 成立。
- ruff 全绿；pre-commit 七道钩子全绿（层级 / 路径字面量 / 字段契约 / dataset /
  工具可达性）。
- `generate_default_switch_box.py --check` 再生一致。
- **变异测试 10 条，条条转红**（未被变异证伪过的守门测试是假门禁）：
  方差门 5 条（抽 fail-closed / 门槛不随 n 收缩 / 丢 √2 / 补评不沿用源底 /
  删限定语）；登记行 5 条（构造注入写回 close_via / cap=0 写回 close_via /
  fail-safe 改成真压 0 / 给三行编正控 / 题型集合写大）。
- 方差门**未跑 live**：`--calibration-repeats` 只做过 dry-run 与单元验证，
  没花过真 LLM。首次真跑前请确认 provider 链（见脚本 fail-closed 提示）。

## 下一步（未做，按值排序）

1. **撤回 reading-baseline 的负贡献结论**，并修 `knowledge_injection_policy.py`
   docstring 里同族的噪声带内引用。
2. `fast-path-runner` / `repair-chain` 要进臂，得先**造一个真关法**
   （route 级差量支持 / repair admission 层的开关），不是补正控字段。
3. 三行进 `default-v1` 需用户点头：从 `generate_default_switch_box.py` 的
   `_PENDING_BOX_ADMISSION` 删 id 再 regenerate（盒是生成物，不手改）。
4. 板的 `revision` 已更到 `19c77a16`；`run_capability_switchboard.py` 的
   `_RUNNER_APPLIES_KINDS` 仍只有 `capability`。本单没碰 runner，「下一批」仍成立。
   **实测口径（2026-08-31 质检纠正，本节初版把两个概念混成了「23 行」）**：
   总行 **45** · 够格进臂 `arm_ids` = **22** · runner 真拧得动 = **20**
   （12 capability + `semantic-verifier` + `noop-prompt` + 6 个已接线谓词）·
   报 `not_implemented` = **25**。
   注意 `followup-composer` 与 `program.research-program` **在臂里但 runner 仍报未接线**
   ——「进臂」与「拧得动」是两件事，45−22=23 这个算法把它们混了。
