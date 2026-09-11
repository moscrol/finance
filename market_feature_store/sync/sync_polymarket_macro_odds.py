"""同步 Polymarket 宏观/地缘政治/加密类事件的市场隐含概率到 DuckDB。

数据源：Polymarket 官方公开 API（gamma-api.polymarket.com），只读、无需 API
key、免费。Polymarket 是搭在 Polygon 链上的去中心化预测市场，份额价格即市场
对某个结果的隐含概率（0~1），不是权威事实，是市场定价。

覆盖范围（刻意收窄，不是全量接入）：Polymarket 全站标签上千个，绝大多数是
体育/娱乐/名人八卦，跟投研无关。本同步只按 RELEVANT_TAGS 白名单过滤——宏观
（Fed/FOMC/GDP）、地缘政治（Geopolitics/Military Strikes/China）、加密货币
（Crypto/Bitcoin，部分 A 股概念股与加密行情联动）。刻意不接的：Elections 这
一大类整体噪音过高（各国地方选举居多），只留和宏观强相关的子标签。要增减
类别改 RELEVANT_TAGS 这个集合即可，不用碰抓取逻辑。

单位与口径：市场对象里的 outcomes/outcomePrices 是两个 JSON 字符串字段
（不是原生数组，取出来要再 json.loads 一次）；probability 直接取
outcomePrices 的浮点值，范围 0~1，不是百分比。同一 event 下可能有多个
market（如"谁会赢"类事件每个候选一个 market），每个 market 内部通常是
Yes/No 两个 outcome。

只留前瞻、剔除已开奖：上游 `closed=false` **不可信**，实测 30% 的行是截止日
早已过去的旧市场（详见 _is_expired）。这类行概率退化成 0/1、又因历史累计成交量
很大而占据 volume 排序头部，长得跟前瞻概率一模一样，必须在入库前挡掉。

为什么不在服务端按 tag 过滤（评估过，不走）：`tag=` 参数被静默忽略（包体与不传
完全一致）；`tag_slug=` 确实生效（实测 20/20 命中），但包体大小由「每个 event 内嵌
多少 market」决定（~100KB/event），过滤并不能让单个 event 变小。按 14 个白名单 tag
各发一次请求，总字节更多、且每次都独立承担 ~37% 的坍塌概率，整体反而更不可靠。
所以维持「一次大请求 + 客户端白名单过滤」。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

from ..db import connect, init_db

GAMMA_BASE = "https://gamma-api.polymarket.com"
SOURCE = "polymarket:gamma-api/events"

# 2026-09-10 实测的上游病症：不是「挂死」，是**吞吐坍塌**。一次 limit=100
# 的响应体足足 9.85 MB（每个 event 内嵌全部 market 元数据，~100KB/event）；
# 健康时 1.2~2.4 MB/s、4~8s 读完，病态时掉到 **0.02 MB/s**（慢 100 倍），
# 按那速度读完要 8 分钟。连接一直不断、字节一直在涓流，所以 urlopen(timeout=)
# 这个 socket 超时**永远不触发**（每次 recv 都刷新计时）——必须自己按时长掐，
# 否则夜跑是卡死而不是失败退出。
#
# 坍塌是**随机且独立**的，跟「第几页」无关（默认只拉 1 页也照样中）。同一进程
# 连探 8 次（每次 8s 预算）得到 成/挂/成/成/挂/挂/成/成，坍塌率 ~37%；关键是
# **挂完紧接着的重试立刻就成**（3.3~7.7s）。所以单次坍塌绝不能当「今天没数据」：
# 不重试的话夜跑约 1/3 的夜晚落 0 行，而重试只要 ~4s。加长单次预算是错的处方
# （要 ~500s 才读完），重试才是。
#
# 两层预算：_ATTEMPT_BUDGET_S 掐单次坍塌（健康响应最慢实测 7.7s，给 15s 不误杀），
# _TOTAL_BUDGET_S 是不论重试几次都不能突破的总天花板。三次全挂 = 45s 退出并标
# truncated（实测遇到过一次）。
# 精度上限：deadline 只在两次 chunk 之间检查，单次 read() 阻塞时管不着，真实上限
# 是 deadline + _SOCKET_TIMEOUT_S（实测 8s 预算跑到 11.7s）。
_TOTAL_BUDGET_S = 45.0
_ATTEMPT_BUDGET_S = 15.0
_MAX_ATTEMPTS = 3
_SOCKET_TIMEOUT_S = 15
_PAGE_PAUSE_S = 2.0
_RETRY_PAUSE_S = 1.0


class PolymarketTimeout(RuntimeError):
    """时长预算耗尽（单次尝试或总预算）。已抓到的部分仍然可用。"""

RELEVANT_TAGS = {
    "geopolitics", "macro geopolitics", "macro single", "macro election 2",
    "fed", "fed rates", "fomc", "fed chair",
    "china", "military strikes",
    "crypto", "crypto prices", "bitcoin", "crypto legal",
}

UPSERT_SQL = """
    INSERT INTO fact_polymarket_macro_odds_daily
        (trade_date, event_id, market_id, condition_id, tag, question,
         outcome, probability, volume, volume_24hr, end_date, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, market_id, outcome) DO UPDATE SET
        tag = excluded.tag,
        question = excluded.question,
        probability = excluded.probability,
        volume = excluded.volume,
        volume_24hr = excluded.volume_24hr,
        end_date = excluded.end_date,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def _get(path: str, params: dict, timeout: int = _SOCKET_TIMEOUT_S, deadline: float | None = None):
    """带真实时长上限的 GET（deadline 是绝对时刻，由调用方给）。

    不能只靠 urlopen 的 timeout：那是 socket 级的，服务端涓流发字节时不会触发。
    这里分块读并逐块查 deadline，超了就主动断开抛 PolymarketTimeout。
    """
    query = urllib.parse.urlencode(params)
    url = f"{GAMMA_BASE}{path}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    chunks: list[bytes] = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        while True:
            if deadline is not None and time.monotonic() > deadline:
                raise PolymarketTimeout(f"时长预算耗尽，已读 {sum(len(c) for c in chunks)} 字节")
            chunk = resp.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return json.loads(b"".join(chunks).decode())


def _get_with_retry(path: str, params: dict, total_deadline: float):
    """单页拉取 + 重试。挂住是随机的，重试立马就成（数据见文件头）。

    每次尝试自己一个 _ATTEMPT_BUDGET_S 短预算，但一律不得越过 total_deadline
    这个总天花板；天花板到了就不再开新尝试，直接把最后一次的异常抛出去
    让调用方标 truncated——宁可诚实报部分，不能拖死夜跑。
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        if attempt > 0:
            if time.monotonic() >= total_deadline:
                break
            time.sleep(_RETRY_PAUSE_S)
        attempt_deadline = min(time.monotonic() + _ATTEMPT_BUDGET_S, total_deadline)
        try:
            return _get(path, params, deadline=attempt_deadline)
        except (PolymarketTimeout, urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            print(
                f"polymarket 第 {attempt + 1}/{_MAX_ATTEMPTS} 次尝试失败（{exc}）",
                flush=True,
            )
    raise last_exc if last_exc else PolymarketTimeout("总预算耗尽，未发出请求")


def _matched_tag(event: dict) -> str | None:
    for t in event.get("tags") or []:
        label = str(t.get("label") or "").strip()
        if label.lower() in RELEVANT_TAGS:
            return label
    return None


def _parse_end_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _is_expired(end_dt: date | None, today: date) -> bool:
    """该 market 的截止日是否已经过了——过了就不是前瞻概率，不入库。

    不能只信上游的 closed 字段：2026-09-10 实测 `closed=false` 的返回里
    328/1106 行（164 个 market）的 endDate 已经早于当天，其中 324 行概率
    已退化成 0 或 1——就是已经开奖、只差上游改状态的旧市场。典型例子：
    "Netanyahu out by March 31?" 到 9 月仍然在列表里，Yes = 0.0。

    危害不在多几行，而在它们成交量很大（历史累计）、排序时直接占据
    头部：按 volume 取 top N 会拿到一堆三月就有答案的旧问题，而它们长得跟
    前瞻概率一模一样（都是 0~1 的数），agent 引用就是把结算价当预期读。

    end_dt 为 None（上游没给 endDate、实测 2 行）当作无法判定，保留。
    同日到期（end_dt == today）保留：当天还在交易。
    """
    return end_dt is not None and end_dt < today


def fetch_relevant_markets(
    pages: int = 1, page_size: int = 100, as_of: date | None = None
) -> tuple[list[dict], bool]:
    """按成交量从高到低翻页拉活跃事件，只保留命中 RELEVANT_TAGS 的那些。

    默认只拉第一页：按成交量排序的前 100 个事件就是有真实流动性的那批，
    长尾市场报价稀薄、概率本身是噪音，翻得越深信噪比越差。需要更宽覆盖时
    显式传 pages，页间按 _PAGE_PAUSE_S 节流（单纯礼貌；坍塌是随机的、与是否
    连发无关，见文件头）。注意：_TOTAL_BUDGET_S 是**整个 fetch**的天花板，
    多页时很可能在后面的页上耗尽预算而押 truncated。

    过期市场按 as_of（默认今天）丢弃，理由见 _is_expired。Gamma 接口只有
    "当前"快照、没有历史参数，所以过期判定只能按真实今天算，不跟随 sync()
    的 trade_date 标注日走。

    Returns: (records, truncated)。truncated=True 表示时长预算耗尽，
    返回的是已抓到的部分，不是完整结果——调用方要照实标注，别当全量用。
    """
    today = as_of or date.today()
    rows: list[dict] = []
    dropped_expired = 0
    deadline = time.monotonic() + _TOTAL_BUDGET_S
    for page in range(pages):
        if page > 0:
            time.sleep(_PAGE_PAUSE_S)
        try:
            events = _get_with_retry(
                "/events",
                {
                    "limit": page_size,
                    "offset": page * page_size,
                    "closed": "false",
                    "order": "volume",
                    "ascending": "false",
                },
                total_deadline=deadline,
            )
        except (PolymarketTimeout, urllib.error.URLError, TimeoutError) as exc:
            print(f"polymarket 第 {page} 页中断（已抓 {len(rows)} 行）: {exc}", flush=True)
            return rows, True
        if not events:
            break
        for event in events:
            tag = _matched_tag(event)
            if not tag:
                continue
            for market in event.get("markets") or []:
                try:
                    outcomes = json.loads(market.get("outcomes") or "[]")
                    prices = json.loads(market.get("outcomePrices") or "[]")
                except (TypeError, json.JSONDecodeError):
                    continue
                end_dt = _parse_end_date(market.get("endDate"))
                if _is_expired(end_dt, today):
                    dropped_expired += 1
                    continue
                for outcome, price in zip(outcomes, prices):
                    try:
                        prob = float(price)
                    except (TypeError, ValueError):
                        continue
                    market_id = str(market.get("id") or "")
                    if not market_id:
                        continue
                    rows.append(
                        {
                            "event_id": str(event.get("id") or ""),
                            "market_id": market_id,
                            "condition_id": market.get("conditionId"),
                            "tag": tag,
                            "question": market.get("question") or event.get("title"),
                            "outcome": outcome,
                            "probability": prob,
                            "volume": market.get("volume"),
                            "volume_24hr": market.get("volume24hr"),
                            "end_date": end_dt,
                        }
                    )
        if len(events) < page_size:
            break
    if dropped_expired:
        print(
            f"polymarket 丢弃 {dropped_expired} 个已过期 market"
            f"（上游 closed=false 不可信，见 _is_expired）",
            flush=True,
        )
    return rows, False


def sync(trade_date: str | None = None) -> dict:
    """同步当前活跃的宏观/地缘/加密类 Polymarket 市场概率快照。

    Returns: {"rows": int, "tags_hit": {tag: count}, "truncated": bool}
    truncated=True 表示上游中断、这次只是部分快照，不要当全量读。
    """
    td = trade_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    records, truncated = fetch_relevant_markets()
    if not records:
        return {"rows": 0, "tags_hit": {}, "truncated": truncated}

    rows = [
        (
            td,
            r["event_id"],
            r["market_id"],
            r["condition_id"],
            r["tag"],
            r["question"],
            r["outcome"],
            r["probability"],
            r["volume"],
            r["volume_24hr"],
            r["end_date"],
            SOURCE,
            now,
        )
        for r in records
    ]

    init_db()
    con = connect()
    try:
        con.executemany(UPSERT_SQL, rows)
    finally:
        con.close()

    tags_hit: dict[str, int] = {}
    for r in records:
        tags_hit[r["tag"]] = tags_hit.get(r["tag"], 0) + 1
    return {"rows": len(rows), "tags_hit": tags_hit, "truncated": truncated}
