"""A conservative request-scope view for deterministic intent recognizers.

This is NOT a topic router or a general Chinese semantic parser. It removes
explicitly prohibited task spans and reported questions from the text used to
recognize a *requested* operation. It never changes the original user message,
research materials, or model-visible text. Positive clauses, negated world facts
("why did it not rise"), double negatives and request questions stay available.

The lexicon describes grammatical operators/actions, not markets, dates, metrics
or evaluation questions. No new routing regex or financial topic rule lives here.
Only the causal recognizer opts in for now; other routing rules are unchanged.
"""
from __future__ import annotations

# Longest token wins, so 不需要 is one operator, not 不 + an unrelated suffix.
_DENIALS = tuple(sorted((
    "没有必要", "没必要", "不需要", "不必", "无需", "无须", "不用", "不要",
    "禁止", "避免", "不能", "不得", "不是", "并非", "勿", "别", "不",
), key=len, reverse=True))
_MODIFIERS = tuple(sorted((
    "应该", "应当", "必须", "需要", "可以", "继续", "尝试", "详细", "具体",
    "深入", "进行", "你", "您", "我们", "请", "要", "先", "再", "去", "能",
), key=len, reverse=True))
_ACTIONS = tuple(sorted((
    "解释", "分析", "推测", "猜测", "讨论", "研究", "说明", "预测", "比较",
    "对比", "列出", "查询", "提供", "给出", "判断", "归因", "展开", "寻找",
    "计算", "回答", "评估", "考虑", "总结", "描述", "编造", "讲解",
    "忽略", "回避", "跳过", "省略", "遗漏", "略过", "无视",
), key=len, reverse=True))
_AVOIDANCE = ("忽略", "回避", "跳过", "省略", "遗漏", "略过", "无视")
_QUESTIONS = ("能不能", "可不可以", "需不需要", "要不要", "该不该", "会不会")
_BOUNDARIES = "，,；;。.!！?？\n"
_RESTARTS = ("但是", "但", "而是", "不过", "同时", "另外", "并且", "还请", "也请")
_QUOTES = {"“": "”", "‘": "’", '"': '"', "'": "'", "「": "」", "『": "』"}
_REPORT_CUES = ("报告", "材料", "原文", "标题", "写道", "写着", "提到", "引用", "说过", "上文")
_QUOTE_REQUESTS = ("请回答", "请解释", "请分析", "回答", "解释一下", "分析一下")


def _token_at(text: str, index: int, tokens: tuple[str, ...]) -> str:
    return next((token for token in tokens if text.startswith(token, index)), "")


def _is_denied_action(text: str, index: int) -> bool:
    """Parse adjacent polarity/modal operators ending at a task action.

    Do not treat a 不 modifying a world predicate as task denial. The optional
    object bridge covers e.g. 不要对…进行分析, without scanning arbitrary words
    after 不 (which would swallow 为什么不涨…请解释).
    """
    cursor = index
    negatives = 0
    while cursor < len(text):
        if _token_at(text, cursor, _QUESTIONS):
            return False
        denial = _token_at(text, cursor, _DENIALS)
        if denial:
            negatives += 1
            cursor += len(denial)
            continue
        modifier = _token_at(text, cursor, _MODIFIERS)
        if modifier:
            cursor += len(modifier)
            continue
        break
    if not negatives:
        return False
    # 不要只/仅… is an additive request, not cancellation of that action.
    if text.startswith(("只", "仅", "光", "单单"), cursor):
        return False
    action = _token_at(text, cursor, _ACTIONS)
    if not action and text.startswith(("对", "就", "针对", "关于", "把"), cursor):
        # Object phrases contain no clause separators: the caller already split
        # clauses, and an explicit new request starts its own scope.
        hits = [(text.find(a, cursor), a) for a in _ACTIONS if text.find(a, cursor) >= 0]
        if hits:
            _, action = min(hits, key=lambda item: (item[0], -len(item[1])))
    if not action:
        return False
    return (negatives + int(action in _AVOIDANCE)) % 2 == 1


def _quote_end(text: str, index: int) -> int:
    """Quote regions are atomic, including punctuation inside them."""
    close = _QUOTES[text[index]]
    end = text.find(close, index + 1)
    return len(text) if end < 0 else end + 1


def _mask_reported_quotes(text: str) -> str:
    result = list(text)
    index = 0
    while index < len(text):
        if text[index] not in _QUOTES:
            index += 1
            continue
        end = _quote_end(text, index)
        # Look at this sentence, not a reporting cue in a previous sentence.
        start = max((text.rfind(sep, 0, index) for sep in "。.!！?？\n"), default=-1) + 1
        prefix = text[start:index]
        suffix = text[end:]
        governed = any(word in prefix for word in _QUOTE_REQUESTS)
        reported = any(word in prefix for word in _REPORT_CUES) or suffix.startswith(
            ("不是我的问题", "这句话", "这道题", "这段话")
        )
        if reported and not governed:
            result[index:end] = " " * (end - index)
        index = end
    return "".join(result)


def active_request_text(text: str) -> str:
    """Mask non-request spans, preserving length, all other text and raw input.

    Recognition is deliberately bounded to explicit linguistic forms. Unknown
    forms are left unchanged, not certified as understood. Callers must not use
    this view as a replacement for the full question in a task contract/model.
    """
    view = _mask_reported_quotes(text)
    result = list(view)
    clauses: list[tuple[int, int, str]] = []
    start = index = 0
    while index < len(view):
        if view[index] in _QUOTES:
            index = _quote_end(view, index)
            continue
        restart = _token_at(view, index, _RESTARTS)
        if view[index] in _BOUNDARIES or restart:
            width = len(restart) if restart else 1
            clauses.append((start, index, view[index:index + width]))
            start = index + width
            index = start
        else:
            index += 1
    clauses.append((start, len(view), ""))
    carry_denial = False
    for start, end, separator in clauses:
        part = view[start:end]
        # Remove whitespace only for grammatical matching, retaining the map
        # into the original view so caller offsets and quoted evidence survive.
        positions = [i for i, char in enumerate(part) if not char.isspace()]
        compact = "".join(part[i] for i in positions)
        if not compact:
            carry_denial = False
            continue
        denied_from: int | None = None
        if carry_denial and _token_at(compact, 0, _ACTIONS):
            denied_from = 0
        index = 0
        while denied_from is None and index < len(compact):
            question = _token_at(compact, index, _QUESTIONS)
            if question:
                index += len(question)
                continue
            denial = _token_at(compact, index, _DENIALS)
            if denial:
                if _is_denied_action(compact, index):
                    denied_from = index
                    break
                # Consume an entire polarity chain once. Otherwise scanning the
                # inner 不 of 并非不需要 would reverse the decision a second time.
                cursor = index + len(denial)
                while cursor < len(compact):
                    token = _token_at(compact, cursor, _DENIALS + _MODIFIERS)
                    if not token:
                        break
                    cursor += len(token)
                index = cursor
            else:
                index += 1
        if denied_from is not None:
            left = start + positions[denied_from]
            result[left:end] = " " * (end - left)
        # A comma-separated verb list inherits denial; a new positive request
        # (请/只需/… rather than a bare task verb) does not.
        carry_denial = denied_from is not None and separator in ("，", ",")
    return "".join(result)
