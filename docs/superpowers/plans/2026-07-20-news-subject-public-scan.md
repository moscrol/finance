# News Subject and Public Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 HTTP URL 的本地路径误报，并让泛主题新闻冲击问题稳定锚定用户明确提到的主题。

**Architecture:** 在 query understanding 的新闻主体入口增加一个窄口径、句首锚定的显式主题规则，未命中时回退现有事件目标规则；在 smoke 公共扫描器上只补盘符左边界，不降低 Unix/Windows 路径检测能力。

**Tech Stack:** Python、正则表达式、pytest、FastAPI E2E smoke。

---

### Task 1: 写失败回归

**Files:**
- Modify: `intelligence/tests/test_query_understanding.py`
- Create: `intelligence/tests/test_smoke_workbench_self_use.py`

- [ ] 增加新闻主题解析测试：

```python
def test_related_news_topic_precedes_impact_object() -> None:
    envelope = understand_query(
        "请分析近期光模块相关消息对产业链和核心公司的影响，"
        "区分已证实事实、推断、受益与受损方向，并给反证。"
    )
    assert envelope.question_type == "news_impact"
    assert envelope.subject == "光模块"
    assert envelope.subject_kind == "theme"
```

- [ ] 增加扫描器真假路径测试：

```python
def test_public_scanner_does_not_treat_http_url_as_windows_path() -> None:
    scanner = PublicLeakScanner()
    scanner.scan("来源：https://example.com/a/1", "answer")
    assert scanner.hits == []

def test_public_scanner_still_rejects_local_paths() -> None:
    scanner = PublicLeakScanner()
    scanner.scan("C:/Users/name/file.txt", "answer")
    scanner.scan("/Users/name/file.txt", "answer")
    assert [item["marker"] for item in scanner.hits] == [
        "local_path",
        "local_path",
    ]
```

- [ ] 运行三个测试，确认旧代码至少两项失败。

### Task 2: 最小实现

**Files:**
- Modify: `intelligence/services/query_understanding.py`
- Modify: `scripts/smoke_workbench_self_use.py`

- [ ] 增加句首锚定的 `_RELATED_NEWS_TOPIC_RE`，在
  `_news_impact_target()` 中先取显式相关消息主题。
- [ ] 把 Windows 路径分支改为
  `(?<![A-Za-z0-9])[A-Za-z]:[/\\]`。
- [ ] 运行新增测试和 query/turn/smoke registry 相关测试，全部通过。
- [ ] 提交源码与测试。

### Task 3: 回归、发布和 E2E

**Files:**
- Verify: `intelligence/tests`
- Runtime: `/Users/a77/finance-workspace-runtime`

- [ ] 在无用户态环境变量、无未跟踪数据的 detached worktree 跑完整测试。
- [ ] 用户已授权合并；非强推合入 main 并建立新的 detached runtime。
- [ ] 原子切换唯一 8792，确认 readiness、市场快照、知识索引和 RAG worker。
- [ ] 重跑同一新闻问题，要求 public/secret scan 为 0、subject=光模块、
  无内部异常、无无关军工召回。
- [ ] 继续完成观察清单与每日复盘 E2E。
