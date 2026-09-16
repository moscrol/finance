# Experience-card `promoted_to_code` + Alpha 向导 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让已固化进管线的方法论卡不再被注入 prompt，并把 Hosted Alpha 的 Cloudflare 人工步骤收成可重复向导——不翻 8792 的 auth。

**Architecture:** 经验卡生命周期在 `promotion` 字段上再加一档 `promoted_to_code`。唯一注入口 `load_cards` 像跳过 `invalidated` 一样跳过它（单点过滤，不在 select_resident / select_relevant 再散一层）。纠偏走既有 append-only `memory_status` 归档，不改历史行。Alpha 认证代码已在 main；本轮只交向导，不改生产启动器。

**Tech Stack:** Python 3 / unittest / JSONL 用户态（gitignore）/ `memory_status` / wizard template.sh

---

## 策展裁决（本轮锁死）

经验卡 13 张（live，非 invalidated）全部 `promotion=promoted_to_code`。飞凯 candidate 的原则是「事实层交叉验证叙事层」，已在管线；个股数字不当事实引用。

7 条纠偏：

| # | 原则 | 去向 | 理由 |
|---|---|---|---|
| 1 | 反模板化 | 归档 | answer_quality / answer_lint |
| 2 | 多维动态推理 | 归档 | orchestrator 生命周期 |
| 3 | 第一性原理 + 二阶导 | 归档 | stock-deep-dive D1–D3 |
| 4 | 澄清≠证伪 | **留下** | 代码里搜不到这条 A 股微观结构规则 |
| 5 | 日度四源推演 | 归档 | 四源在 forecast；「查远端 PR/main」是运营泄漏，不该进用户 prompt |
| 6 | 相对日期绑复盘日 | **留下** | `market_review_requested_date` 只解析显式日期，不把「今天」绑到已给的复盘截止日 |
| 7 | 结构化腔 | **留下** | intelligence 里搜不到这条表达规范 |

生产 `FORESIGHT_USERS_DIR` 没有 `experience_cards.jsonl`（8792 本来就不注入这 13 张）。纠偏两边都有，归档两份。

---

### Task 1: `load_cards` 跳过 `promoted_to_code`

**Files:**
- Modify: `intelligence/services/experience_cards.py`
- Modify: `intelligence/tests/test_experience_cards.py`
- Modify: `intelligence/tests/test_retrieval_recall.py`
- Modify: `intelligence/cli.py`

- [x] **Step 1: Write the failing tests**

在 `ResidentCardTests` 后追加：

```python
class PromotedToCodeTests(unittest.TestCase):
    def test_load_skips_promoted_to_code_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cards.jsonl"
            path.write_text(
                json.dumps({"question": "Q1", "promotion": "methodology", "prompt_rule": "keep"}, ensure_ascii=False)
                + "\n"
                + json.dumps({"question": "Q2", "promotion": "promoted_to_code", "prompt_rule": "drop"}, ensure_ascii=False)
                + "\n"
                + json.dumps({"question": "Q3", "promotion": "candidate", "prompt_rule": "fresh"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            loaded, warn = experience_cards.load_cards(path, window=0)
        self.assertIsNone(warn)
        self.assertEqual([c["question"] for c in loaded], ["Q1", "Q3"])

    def test_promoted_to_code_is_not_resident(self) -> None:
        cards = [
            {"question": "old", "promotion": "promoted_to_code", "prompt_rule": "already in code", "ts": "t1"},
            {"question": "live", "promotion": "methodology", "prompt_rule": "still resident", "ts": "t2"},
        ]
        resident = experience_cards.select_resident_cards(cards)
        self.assertEqual([c["question"] for c in resident], ["live"])
```

在 `ExperienceCardsRetrieverTests._make_cards` 加一张 `promotion: promoted_to_code` 的深挖卡，断言召回不含它。

- [x] **Step 2: Run tests to verify they fail**

Run: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_experience_cards.py intelligence/tests/test_retrieval_recall.py::ExperienceCardsRetrieverTests -q`

Expected: FAIL — `promoted_to_code` 卡仍被 `load_cards` 返回。

- [ ] **Step 3: Minimal implementation**

`experience_cards.py`：

```python
ARCHIVED_PROMOTIONS = frozenset({"promoted_to_code"})
```

`load_cards` 在 `invalidated` 判断后加：

```python
        if str(obj.get("promotion") or "").strip() in ARCHIVED_PROMOTIONS:
            continue
```

`cli.py` `--promotion` choices 加上 `"promoted_to_code"`。

`select_resident_cards` 不必再过滤——`promoted_to_code` 不在 `RESIDENT_PROMOTIONS`。防御测试覆盖的是「有人绕过 load 直接喂 select」。

- [ ] **Step 4: Run tests to verify they pass**

Same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/experience_cards.py intelligence/tests/test_experience_cards.py intelligence/tests/test_retrieval_recall.py intelligence/cli.py
git commit -m "$(cat <<'EOF'
feat(memory): 经验卡 promotion=promoted_to_code 不再注入

方法论已固化进编排/契约/质检门后，再注入同一套卡是重复供给。
load_cards 与 invalidated 同一 choke point 跳过该档；记录留在 jsonl 可回放。

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>
EOF
)"
```

---

### Task 2: 标记 13 张卡 + 归档 4 条纠偏（用户态，不入库）

**Files:**
- Modify (gitignore): `intelligence/users/linxiaoqi5111/experience_cards.jsonl`
- Modify (gitignore): `intelligence/users/linxiaoqi5111/corrections.jsonl`
- Modify (仓外): `~/.local/share/finance-workbench/users/linxiaoqi5111/corrections.jsonl`

- [ ] **Step 1: Rewrite the 13 live cards' promotion in place**

只改 `promotion` 字段；invalidated 行一字不动。

- [ ] **Step 2: Verify load_cards on the real file returns 0 of the 13**

```python
from intelligence.services import experience_cards
cards, _ = experience_cards.load_cards("intelligence/users/linxiaoqi5111/experience_cards.jsonl", window=0)
assert all(c.get("promotion") != "promoted_to_code" for c in cards)
assert len(cards) == 0  # 16 行里 3 张 invalidated + 13 张 promoted_to_code
```

- [ ] **Step 3: Archive corrections 1/2/3/5 via memory_status (append-only)**

target_ts（两边相同）：

- `2026-06-29T09:37:58+00:00` 反模板化
- `2026-06-29T12:57:20+00:00` 多维动态推理
- `2026-06-29T13:16:40+00:00` 第一性原理 + 二阶导
- `2026-07-02T00:31:00+08:00` 日度市场推演

reason: `promoted_to_code: already in pipeline (2026-08-28 UMD experiment)`

留下：澄清≠证伪、相对日期、结构化腔。

- [ ] **Step 4: Do not commit these jsonl files** (`.gitignore: intelligence/users/*/experience_cards.jsonl` 等)

---

### Task 3: 文档与图谱

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-shared-memory-plane-design.md`（状态：gate 证伪，本轮已执行归档）
- Modify: `intelligence/users/README.md`
- Modify: `~/agent-memory/10_knowledge/finance-agent-capability-graph.md`（经验卡节点钉 `::load_cards`）
- Modify: `docs/workbench/hosted-alpha-gate.md`（链到向导）

- [ ] **Step 1: Update the four docs as listed**
- [ ] **Step 2: Run `python3 scripts/graph_audit.py` in agent-memory; expect exit 0**
- [ ] **Step 3: Commit finance-workspace docs with the code commit or a follow-up docs commit. Capability graph is a separate repo commit.**

---

### Task 4: Hosted Alpha 向导（不翻 8792）

**Files:**
- Create: `scripts/hosted-alpha-wizard.sh`（从 `~/.claude/skills/wizard/template.sh` 复制，只改 STAGES 以下）
- Modify: `docs/workbench/hosted-alpha-gate.md`

- [ ] **Step 1: Copy template.sh, set TOTAL_STAGES, write Chinese stages**

Stages:

1. 确认公网主机名（默认建议 `beta.industry7view.com`，已有同域隧道）
2. Cloudflare Zero Trust → Access 应用（开控制台 URL）
3. 粘贴 Team Domain 与 AUD tag
4. 邀请邮箱 → user_id 名单，写入 `~/.local/share/finance-workbench/beta-users.json`
5. 写入 `~/.local/share/finance-workbench/alpha.env`（AUTH_MODE / TEAM / AUD / USER_MAP / QUOTA / FULL_ACCESS）
6. 展示如何接到 `start-finance-workbench`——**向导不改启动器、不 kickstart 8792**

ENV_FILE 默认 `~/.local/share/finance-workbench/alpha.env`。

- [ ] **Step 2: `bash -n scripts/hosted-alpha-wizard.sh`；chmod +x。不要自己跑向导。**
- [ ] **Step 3: 跑 `pytest intelligence/tests/test_api_auth.py intelligence/tests/test_api_quota.py` 确认门代码仍绿。**
- [ ] **Step 4: Commit wizard + runbook pointer.**

---

## 明确不做

- 不实现 shared_memory JSONL 注入层（设计稿 §7 已否）
- 不把 `WORKBENCH_AUTH_MODE=cf_access` 写进生产启动器（缺 CF Access 会让 8792 fail-closed 起不来）
- 不改 `linxiaoqi5111` 的 checkpoints / interactions
- 不提交实验台账、探针目录、日更 export
- 不合 main、不 push，除非用户明确要求
