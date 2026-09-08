"""时间长河：as-of 联立读取面（垂直切片 v0）。

设计见 `docs/superpowers/specs/2026-09-05-time-river-endstate-design.md` §3 与
`2026-09-05-time-river-gap-roadmap.md` G-02a / G-02 对象契约。本模块是那条河的
**最小垂直切片**：一天 × 一个实体 × 六条轨，用来证明或证伪「联立」这件事本身，
不是六轨全量 provider。

三条硬约束（来自终局 §9 / F4，写成代码而不是口号）：

1. **不新建存储。** ``slice_river`` 是纯函数，每条轨现算，``RiverObject`` 只在内存
   组装。索引层不持有任何轨的主数据副本，只持 ``ref`` 与 ``source_hash``。
2. **缺轨返回 ``Gap``，不用别的轨补编。** 没有数据、或实体口径接不上，都如实报缺口
   并写明 reason；调用方看到的是「这条轨没有」，不是空列表冒充「这条轨为零」。
3. **路径上无 LLM。** 同一 ``(as_of, entity, knowledge_cutoff)`` 两次调用逐字段相同。

已知的两处口径现实（实测 2026-09-05，不是设计意图）：

- ``recorded_at`` 目前取自各事实表的 ``updated_at``。而 ``updated_at`` 是**刷新时间**
  （`market_feature_store/schema.sql:10`），重发布会把它推到今天，所以它只是真实首次
  入库时刻的**上界**——只会少算不会多算，因此 ``pit_grade`` 保守可信，但整条河的可
  strict 段被系统性低估。工单 #27（`2026-09-05-river-recorded-at-workorder.md`）加
  写一次不更新的 ``recorded_at`` 之后，本模块改读那一列，此处注释即可删。
- **六条轨至少三套实体命名空间**：板块 / 题材 / 个股轨用 ``sector_ts_code`` +
  ``sector_name``；``fact_theme_flow_daily`` 用自己的 ``theme_name``；判断轨
  （``checkpoints.jsonl``）用自由文本 ``themes``。唯一的桥接表
  ``config_theme_sector_link`` **实测 0 行**。所以实体解析只做**精确匹配**，
  接不上就是 ``Gap``——不做模糊匹配、不做同义词猜测，猜错会静默串轨。
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

DEFAULT_DB = "db/market_feature_store.duckdb"

# 六个维度 = 终局 §3 + §13.2 F9 钦定的六条轨。**不要私自增删或改名**：
# 初版把「板块」单列成一条轨、少了「舆论」，与终局对不上。板块的量价与双红属于
# 盘面轨（§3 原文「量价、双红、涨停热度、指数阶段、流动性指纹」），已并回。
Track = Literal["market", "theme", "opinion", "capital", "stock", "judgment"]
TRACKS: tuple[Track, ...] = ("market", "theme", "opinion", "capital", "stock", "judgment")

PitGrade = Literal["strict", "trade_date_only"]

# 个股轨与题材轨的节点数上限。切片是给人和模型读的，不是导出全量；
# 排序键必须确定（金额降序 + 代码升序），否则「两次调用结果相同」这条验收会假绿。
NODE_LIMIT = 10


@dataclass(frozen=True)
class RiverObject:
    """河上的一个对象。字段对齐 roadmap G-02 契约，v0 只落必需的那些。"""

    track: Track
    entity_id: str
    object_type: str
    ref: str  # 指回主数据：表:主键 / 文件:记录 id。索引层不复制正文
    source_hash: str
    valid_from: str  # 世界里什么时候为真 = as-of 交易日
    recorded_at: str | None  # 系统什么时候知道；None = 不可判 → 整片降档
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": self.track,
            "entity_id": self.entity_id,
            "object_type": self.object_type,
            "ref": self.ref,
            "source_hash": self.source_hash,
            "valid_from": self.valid_from,
            "recorded_at": self.recorded_at,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class Gap:
    """一条轨读不出来。``reason`` 必须说清是「没有数据」还是「口径接不上」。"""

    track: Track
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"track": self.track, "gap": True, "reason": self.reason, "detail": self.detail}


TrackResult = list[RiverObject] | Gap


@dataclass(frozen=True)
class RiverSlice:
    as_of: str
    entity_id: str
    entity_name: str
    knowledge_cutoff: str
    tracks: dict[Track, TrackResult]
    # 本次实体身份经过了跨供应商归一。归一的是**身份**不是**可比性**：
    # config_sector_alias 的 note 明写「两套口径成分不同，跨切换日数值不可直接比较」。
    # 跨换源日做数值比较（区间、队列、聚类）的调用方必须自己看这个标记。
    alias_applied: bool = False
    # ``knowledge_cutoff > as_of``：这一片**看得见 as-of 之后才被记录的对象**。
    # 终局 spec §4.1 只在「事后人工复核」那一档允许它，且明写「不得进入任何校准或
    # 方法有效性统计」。所以它是一等字段而不是注释：下游必须能机器判定。
    hindsight: bool = False

    @property
    def gaps(self) -> list[Gap]:
        return [v for v in self.tracks.values() if isinstance(v, Gap)]

    @property
    def objects(self) -> list[RiverObject]:
        out: list[RiverObject] = []
        for v in self.tracks.values():
            if isinstance(v, list):
                out.extend(v)
        return out

    @property
    def pit_grade(self) -> PitGrade:
        """全部对象的 ``recorded_at`` 都存在且 <= C 才是 strict，否则降档。

        降档不是丢弃：``trade_date_only`` 的切片照样能用于当日带读，只是不能进
        回放与校准（#25 已定的两档口径）。

        ⚠ 降档**只是标记**，默认仍然把 ``recorded_at > C`` 的对象返回给调用方。
        这等于把「要不要用」的决定推给下游——下游若不看 ``pit_grade`` 就是前视
        泄漏。要机器保证无前视，用 ``require_strict=True`` 让本层直接滤掉，
        不要依赖调用方自觉。
        """
        if self.hindsight:
            # 事后复核片永远不是 strict：它的 cutoff 晚于 as_of，按定义看得见后来的事。
            # 不在这里 fail closed 的话，`grade == "strict"` 这个判据会替它背书，
            # 而所有回放 / 校准消费方用的正是这个判据。
            return "trade_date_only"
        if not self.objects:
            # 空切片不能报 strict：``all([])`` 恒真，会让「六轨全缺」伪装成
            # 「六轨全部通过严格 PIT」，而消费方的判据通常就是 ``grade == strict``。
            # 认不出来就 fail closed。
            return "trade_date_only"
        for obj in self.objects:
            if obj.recorded_at is None or obj.recorded_at[:10] > self.knowledge_cutoff:
                return "trade_date_only"
        return "strict"

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            # 两个限定语都必须活过序列化：从收据 / JSON 重建切片的消费方（带读、回放）
            # 看不到它们，就会在跨换源日做不可比的比较、或把事后视角当无前视用，
            # 而且两种都不会有人发现。
            "hindsight": self.hindsight,
            "alias_applied": self.alias_applied,
            "tracks": {
                k: (v.to_dict() if isinstance(v, Gap) else [o.to_dict() for o in v])
                for k, v in self.tracks.items()
            },
        }


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def _ts(value: Any) -> str | None:
    """把 ``updated_at`` 归一成 ISO 串。None / 空 → None（→ 整片降档，不猜）。"""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value).strip()
    return text or None


# --------------------------------------------------------------------------- #
# 板块系表的记录时刻：两个来源取较早
# --------------------------------------------------------------------------- #
# `updated_at` 是**刷新时间**（`schema.sql:10`），各 sync 一律
# `ON CONFLICT DO UPDATE SET updated_at = excluded.updated_at`——重发布会把整段历史推到今天。
# 关键性质：它只会**变晚、不会变早**。所以 `updated_at <= 交易日` 是「那时已存在」的
# **充分**证据（可信），而 `updated_at > 交易日` **不是**「那时不存在」的证据（不可信）。
#
# 快照台账 `ops_sector_universe_snapshot_daily.captured_at` 是那一版板块宇宙的真实抓取时刻，
# 不随重发布移动，同样是存在性的合法证据。两个都在时取**较早**的那个。
#
# ⚠ 不要整轨换成 `captured_at`：实测资金轨 `fact_sector_stock_daily` 会从 47 天 strict
# 掉到 20 天——台账 2026-07-27 才开始，之前的行都是 `snapshot_id='legacy'`，
# 而它们的 `updated_at` 里有一批是诚实的。换源不是升级，取较早才是。
#
# 实测收益（2026-09-06 主库）：六轨联立可 strict 重放 **1 天 → 16 天**（2026-07-30~09-02）。
# 存量 384 天仍是 legacy 无台账行，记录时刻确实丢了，不猜——它们继续按 trade_date_only 走。
SECTOR_LEDGER_TABLE = "ops_sector_universe_snapshot_daily"


def sector_ledger_join(alias: str = "v") -> str:
    """板块系表 → 快照台账的左连接。表不存在时调用方应跳过（见 ``_has_table``）。"""
    return (
        f" LEFT JOIN {SECTOR_LEDGER_TABLE} snap"
        f" ON snap.snapshot_id = {alias}.sector_universe_snapshot_id "
    )


def sector_recorded_at_sql(alias: str = "v", *, with_ledger: bool = True) -> str:
    """记录时刻表达式。``LEAST`` 在 DuckDB 里忽略 NULL（实测），故不必再包 COALESCE。

    **审计脚本 `scripts/river_pit_audit.py` 按同一对函数取 SQL**，不各写一套——
    两处口径必漂，而漂的时候审计会替河说谎（报的 strict 天数不是河真能给出的）。
    """
    upd = f"CAST({alias}.updated_at AS TIMESTAMP)"
    if not with_ledger:
        return upd
    # captured_at 带时区（Asia/Taipei = +08:00，与交易日同一时区），CAST 成朴素时间戳
    # 取的就是当地墙上时间——正是要拿来和交易日比的那个量。
    return f"LEAST({upd}, CAST(snap.captured_at AS TIMESTAMP))"


def _has_table(con: Any, table: str) -> bool:
    rows = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name=? LIMIT 1",
        [table],
    ).fetchall()
    return bool(rows)


def _rows(con: Any, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


# --------------------------------------------------------------------------- #
# 各轨 provider：签名统一 (con, as_of, entity_id, entity_name) -> TrackResult
# --------------------------------------------------------------------------- #
def _market_track(con: Any, as_of: str, eid: str, ename: str) -> TrackResult:
    """盘面轨：量价、双红、涨停热度、指数阶段（终局 §3）。

    三个对象：全市场环境（这一天的背景）、该实体的量价与边际量（双红判据所在）、
    该实体的涨停热度。它们同属盘面，分成三条轨会让「六轨」名不副实。

    严格双红 = ``pct_chg>0 且 diff_ratio>10 且 amount>500``（见 CLAUDE.md /
    strategy1-matrix）。这里只**摆出三个字段的原值并算出布尔**，不解释、不下结论——
    判读归框架层，河只负责让它可重算。
    """
    out: list[RiverObject] = []

    env = _rows(
        con,
        """
        SELECT trade_date, market_stage, stage_day, total_amount, amount_vs_yesterday_pct,
               advancers, limit_up, limit_down, sh_deviation_pct, volume_state,
               concentration_state, updated_at
        FROM fact_market_daily WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
        """,
        [as_of],
    )
    if env:
        r = env[0]
        upd = r.pop("updated_at")
        out.append(
            RiverObject(
                track="market",
                entity_id="__market__",
                object_type="stage",
                ref=f"fact_market_daily:{as_of}",
                source_hash=_hash(r),
                valid_from=as_of,
                recorded_at=_ts(upd),
                payload={k: v for k, v in r.items() if k != "trade_date"},
            )
        )

    ledger = _has_table(con, SECTOR_LEDGER_TABLE)
    quote = _rows(
        con,
        f"""
        SELECT v.trade_date, v.sector_ts_code, v.sector_name, v.sw_l1, v.pct_chg, v.amount,
               v.diff_ratio, v.strength, v.multi_period_resonance,
               v.sector_universe_snapshot_id,
               {sector_recorded_at_sql("v", with_ledger=ledger)} AS recorded_at
        FROM fact_sector_daily v
        {sector_ledger_join("v") if ledger else ""}
        WHERE CAST(v.trade_date AS DATE) = CAST(? AS DATE) AND v.sector_ts_code = ?
        """,
        [as_of, eid],
    )
    if quote:
        r = quote[0]
        upd = r.pop("recorded_at")
        pct, diff, amt = r.get("pct_chg"), r.get("diff_ratio"), r.get("amount")
        payload = {k: v for k, v in r.items() if k != "trade_date"}
        payload["strict_double_red"] = (
            None
            if pct is None or diff is None or amt is None
            else bool(pct > 0 and diff > 10 and amt > 500)
        )
        out.append(
            RiverObject(
                track="market",
                entity_id=eid,
                object_type="label",
                ref=f"fact_sector_daily:{as_of}:{eid}",
                source_hash=_hash(r),
                valid_from=as_of,
                recorded_at=_ts(upd),
                payload=payload,
            )
        )

    # 涨停热度按板块名匹配：该表的代码空间历史上出现过 .TI，与板块轨的 .FP 不同源
    # （实测 2026-06-02 那批是 .TI，当前批是 .FP），按名匹配才跨得过换源。
    heat = _rows(
        con,
        """
        SELECT limit_up_count, total_count, limit_up_ratio, market_share, rank,
               market_limit_up_count, data_stage, updated_at
        FROM fact_theme_limit_heat_daily
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE) AND sector_name = ?
        ORDER BY rank NULLS LAST LIMIT 1
        """,
        [as_of, ename],
    )
    if heat:
        r = heat[0]
        upd = r.pop("updated_at")
        out.append(
            RiverObject(
                track="market",
                entity_id=eid,
                object_type="label",
                ref=f"fact_theme_limit_heat_daily:{as_of}:{ename}",
                source_hash=_hash(r),
                valid_from=as_of,
                recorded_at=_ts(upd),
                payload={"source_view": "limit_heat", **r},
            )
        )

    if not out:
        return Gap("market", "no_data", f"{as_of} 既无大盘环境行也无 {eid} 的量价与热度")
    return out


def _theme_track(con: Any, as_of: str, eid: str, _ename: str) -> TrackResult:
    """题材轨：该板块当日的涨停个股与它们挂的题材名（叙事在市场上的落点）。"""
    rows = _rows(
        con,
        """
        -- up_stat_days / up_stat_boards 是 sync 已经解析好的整数（97% 填充），
        -- 而 up_stat 是原始字符串「1/1」。2026-09-05 审计发现整数列全仓无人读、
        -- 下游还在解析字符串——这里直接取整数，字符串只作原样留档。
        SELECT stock_ts_code, stock_name, limit_status, limit_times,
               up_stat, up_stat_days, up_stat_boards,
               first_limit_time, theme_names_json, leader_plate, amount, updated_at
        FROM fact_theme_limit_stock_daily
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE) AND sector_ts_code = ?
        ORDER BY amount DESC NULLS LAST, stock_ts_code
        LIMIT ?
        """,
        [as_of, eid, NODE_LIMIT],
    )
    if not rows:
        return Gap("theme", "no_data", f"fact_theme_limit_stock_daily 无 {as_of} 的 {eid}（当日无涨停成分）")
    out: list[RiverObject] = []
    for r in rows:
        upd = r.pop("updated_at")
        out.append(
            RiverObject(
                track="theme",
                entity_id=eid,
                object_type="event",
                ref=f"fact_theme_limit_stock_daily:{as_of}:{eid}:{r['stock_ts_code']}",
                source_hash=_hash(r),
                valid_from=as_of,
                recorded_at=_ts(upd),
                payload=r,
            )
        )
    return out


def _report_tags(raw: Any) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(x) for x in parsed] if isinstance(parsed, list) else []


def load_reports_asof(con: Any, as_of: str) -> list[dict[str, Any]]:
    """截至 ``as_of`` 的全部研报目录行，按日期升序。

    表只有几百行，一次取回、在 Python 里精确比对标签，比 SQL ``LIKE '%铜%'`` 更准
    （后者会把「铜缆」「铜箔」算成「铜」的覆盖），也比逐实体查更省。
    """
    return _rows(
        con,
        """
        SELECT report_id, title, report_date, report_type, is_hot,
               sector_tags, concept_tags, created_at
        FROM fact_research_report_catalog
        WHERE report_date <= CAST(? AS DATE)
        ORDER BY report_date, report_id
        """,
        [as_of],
    )


def coverage_hits(con: Any, as_of: str, name: str, rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """标签精确命中 ``name`` 的研报。``rows`` 可由调用方预取以便全市场横扫复用。"""
    pool = load_reports_asof(con, as_of) if rows is None else rows
    return [r for r in pool if name in _report_tags(r["sector_tags"]) + _report_tags(r["concept_tags"])]


def coverage_metrics(hits: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    """把命中的研报折成覆盖度量。**近 90 日覆盖是主口径，累计只作背景。**

    实测 469 份研报里 249 份（53%）挤在 2026-01 那一次回填批次里，所以按累计数排序
    会把「一年前被喊过很多」读成「现在催化多」——横扫里出现过「云计算累计 77 份、
    近 90 日 0 份」这种行。累计字段保留，但任何排序与筛选都用 ``count_90d``。
    """
    as_of_d = date.fromisoformat(as_of)
    last = hits[-1]
    return {
        "first_coverage_date": str(hits[0]["report_date"]),
        "last_coverage_date": str(last["report_date"]),
        "days_since_last": (as_of_d - last["report_date"]).days,
        "cumulative_count": len(hits),
        "count_30d": sum(1 for r in hits if (as_of_d - r["report_date"]).days < 30),
        "count_90d": sum(1 for r in hits if (as_of_d - r["report_date"]).days < 90),
        # 阶段词表待 G-06 拍板，且当前样本撑不住密度斜率——不猜。
        "stage": "unverifiable",
        "stage_reason": "舆论阶段词表未钦定（roadmap G-06 §5 第 3 题），且研报样本集中于回填批次",
    }


def _opinion_track(con: Any, as_of: str, eid: str, ename: str) -> TrackResult:
    """舆论轨：卖方覆盖密度（终局 §4「这个逻辑被多少人、以哪个版本在喊」）。

    源是 ``fact_research_report_catalog``——本轨有两处与其他轨不同，都要记住：

    1. **它是唯一有真 ``recorded_at`` 的轨。** 该表同时有 ``created_at`` 与
       ``updated_at``：实测 469 行里 ``updated_at`` 去重后只剩 **1 天**（被 09-02
       那次批量重写抹平），而 ``created_at`` 有 **104 个不同日期**且 468/469 行
       ``<= report_date``。所以本轨取 ``created_at`` 作 ``recorded_at``，
       它现在就能进严格 PIT，不用等工单 #27。
    2. **只出可计算的覆盖度量，不出阶段词。** 舆论阶段词表是 roadmap G-06 的待拍板
       项（§5 第 3 题），而且现有样本撑不住：实测研报高度集中在回填批次
       （某板块 2026-01 有 14 份、之后每月 1 份），密度斜率算出来是采集节奏不是舆论。
       所以 ``stage`` 一律 ``unverifiable`` 并写明原因——**算不出就说算不出**，
       不拿一个看着像阶段的词去填。

    标签用精确匹配而不是 SQL ``LIKE``：``LIKE '%铜%'`` 会把「铜缆」「铜箔」算成
    「铜」的覆盖。表只有几百行，全取回来在 Python 里精确比对更便宜也更准。
    """
    hits = coverage_hits(con, as_of, ename)
    if not hits:
        return Gap(
            "opinion",
            "no_data",
            f"截至 {as_of} 没有 tag 命中「{ename}」的研报（实测 402 个板块名里 228 个有覆盖）",
        )

    metrics = coverage_metrics(hits, as_of)
    last = hits[-1]
    out = [
        RiverObject(
            track="opinion",
            entity_id=eid,
            object_type="label",
            ref=f"fact_research_report_catalog:coverage:{ename}:{as_of}",
            source_hash=_hash(metrics),
            valid_from=as_of,
            # 覆盖度量这个聚合对象，最早在最后一份研报入库时才成立。
            recorded_at=_ts(last["created_at"]),
            payload=metrics,
        )
    ]
    for r in hits[-3:]:  # 最近三份，作可回溯的证据锚点，不搬全文
        out.append(
            RiverObject(
                track="opinion",
                entity_id=eid,
                object_type="event",
                ref=f"fact_research_report_catalog:{r['report_id']}",
                source_hash=_hash(r),
                valid_from=str(r["report_date"]),
                recorded_at=_ts(r["created_at"]),
                payload={
                    "title": r["title"],
                    "report_date": str(r["report_date"]),
                    "report_type": r["report_type"],
                    "is_hot": r["is_hot"],
                },
            )
        )
    out.extend(_fundamental_docs(con, as_of, eid, ename))
    return out


def _fundamental_docs(con: Any, as_of: str, eid: str, ename: str) -> list[RiverObject]:
    """产业基本面研究文档（`fact_theme_fundamental_doc`）。

    2026-09-06 审计发现这张表**整表无生产读取方**——37 份带核心逻辑、验证要点、
    关联板块的产业研究，抓回来一次没被读过。这里接上它。

    **覆盖现实要写在这儿，别让下一个人以为有 37 份可用**：37 份里只有 **5 份**
    挂了 `linked_sectors`（覆盖 MLCC / 化工原料 / 化工 / 人脑工程 / 航空 / 石油 /
    石油化工 / 医药 8 个板块），其余 32 份只挂 `linked_themes`。而题材命名空间与
    板块之间没有桥接表（`config_theme_sector_link` 实测 0 行），所以按板块取切片
    最多只能拿到那 5 份。要拿全 37 份，得先有题材实体的切片入口。

    好处是这一批**天然严格 PIT 干净**：`produced_at` 是写一次的生成时刻，
    没有被批量重写抹平过——和 `fact_research_report_catalog.created_at` 同族。

    `core_theme` / `verification_points` 是散文：可读、可进 prompt，但**不可重算**，
    所以它们只进 payload，不参与任何度量。
    """
    rows = _rows(
        con,
        """
        SELECT document_pk, title, analysis_type, workflow_name, core_theme,
               verification_points, linked_sectors, produced_at
        FROM fact_theme_fundamental_doc
        WHERE produced_at <= ? ORDER BY produced_at
        """,
        [f"{as_of}T23:59:59"],
    )
    out: list[RiverObject] = []
    for r in rows:
        try:
            linked = json.loads(r["linked_sectors"] or "[]")
        except (TypeError, ValueError):
            continue
        if not isinstance(linked, list):
            continue
        # 精确匹配：代码或板块名。两边都在 .FP 空间，实测 8/8 命中。
        if not any(
            str(x.get("sector_code")) == eid or str(x.get("sector_name")) == ename
            for x in linked
            if isinstance(x, dict)
        ):
            continue
        produced = str(r["produced_at"])
        out.append(
            RiverObject(
                track="opinion",
                entity_id=eid,
                object_type="narrative_version",
                ref=f"fact_theme_fundamental_doc:{r['document_pk']}",
                source_hash=_hash(r),
                valid_from=produced[:10],
                recorded_at=produced,
                payload={
                    "title": r["title"],
                    "analysis_type": r["analysis_type"],
                    "workflow_name": r["workflow_name"],
                    # 散文：可读不可重算，不进任何度量
                    "core_theme": r["core_theme"],
                    "verification_points": r["verification_points"],
                },
            )
        )
    return out


def _capital_track(con: Any, as_of: str, eid: str, ename: str) -> TrackResult:
    """资金轨：成分股资金流聚合 + theme 表口径（后者常接不上，如实报）。

    两个来源故意分开成两个对象：它们的实体命名空间不同，合并会掩盖口径接缝。
    """
    ledger = _has_table(con, SECTOR_LEDGER_TABLE)
    # 聚合对象的记录时刻取 ``MAX``：整份聚合要等最后一条成分股落地才算可知。
    # 逐行先按「两来源取较早」解析、再对解析后的值取 MAX——反过来（先 MAX 再取较早）
    # 会把某一行的早时刻安到整份聚合上，等于宣称聚合比它的成分先存在。
    # 三个 SUM 先转 DECIMAL 再加：DuckDB 并行 SUM(DOUBLE) 的求和顺序不定，同一入参两次调用
    # amount_sum 会在最后一位上翻（实测 2026-01-12 算力租赁 2413.130000000001 vs 2413.1299999999997），
    # 连带 source_hash 变——破的是本模块「两次调用逐字段相同」的硬约束。
    agg = _rows(
        con,
        f"""
        SELECT COUNT(*) AS n_stocks,
               CAST(SUM(CAST(v.fund_flow_1d AS DECIMAL(24, 6))) AS DOUBLE) AS fund_flow_1d_sum,
               CAST(SUM(CAST(v.fund_flow_5d AS DECIMAL(24, 6))) AS DOUBLE) AS fund_flow_5d_sum,
               CAST(SUM(CAST(v.amount AS DECIMAL(24, 6))) AS DOUBLE) AS amount_sum,
               MAX({sector_recorded_at_sql("v", with_ledger=ledger)}) AS recorded_at
        FROM fact_sector_stock_daily v
        {sector_ledger_join("v") if ledger else ""}
        WHERE CAST(v.trade_date AS DATE) = CAST(? AS DATE) AND v.sector_ts_code = ?
        """,
        [as_of, eid],
    )
    out: list[RiverObject] = []
    if agg and agg[0]["n_stocks"]:
        r = dict(agg[0])
        upd = r.pop("recorded_at")
        out.append(
            RiverObject(
                track="capital",
                entity_id=eid,
                object_type="label",
                ref=f"fact_sector_stock_daily:{as_of}:{eid}:agg",
                source_hash=_hash(r),
                valid_from=as_of,
                recorded_at=_ts(upd),
                payload={"source_view": "sector_constituent_flow", **r},
            )
        )

    # theme 表走另一套命名空间，只做精确同名匹配——桥接表 config_theme_sector_link 实测 0 行。
    theme = _rows(
        con,
        """
        SELECT theme_code, theme_name, total_fund, total_amount, stock_count, updated_at
        FROM fact_theme_flow_daily
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE) AND theme_name = ?
        """,
        [as_of, ename],
    )
    if theme:
        r = dict(theme[0])
        upd = r.pop("updated_at")
        out.append(
            RiverObject(
                track="capital",
                entity_id=eid,
                object_type="label",
                ref=f"fact_theme_flow_daily:{as_of}:{r['theme_code']}",
                source_hash=_hash(r),
                valid_from=as_of,
                recorded_at=_ts(upd),
                payload={"source_view": "theme_flow", **r},
            )
        )
    if not out:
        return Gap("capital", "no_data", f"{as_of} 的 {eid} 既无成分资金流也无同名 theme_flow 行")
    return out


def _stock_track(con: Any, as_of: str, eid: str, _ename: str) -> TrackResult:
    """个股轨：成分股当日行情节点。**不是推荐名单**——只有事实，无评级无方向。"""
    rows = _rows(
        con,
        """
        SELECT s.stock_ts_code, s.stock_name, d.close, d.pct_chg, d.amount, d.turnover,
               s.high_status_label, s.limit_times, d.updated_at
        FROM fact_sector_stock_daily s
        JOIN fact_stock_daily d
          ON d.stock_ts_code = s.stock_ts_code
         AND CAST(d.trade_date AS DATE) = CAST(s.trade_date AS DATE)
        WHERE CAST(s.trade_date AS DATE) = CAST(? AS DATE) AND s.sector_ts_code = ?
        ORDER BY d.amount DESC NULLS LAST, s.stock_ts_code
        LIMIT ?
        """,
        [as_of, eid, NODE_LIMIT],
    )
    if not rows:
        return Gap("stock", "no_data", f"{as_of} 的 {eid} 无成分股行情")
    out: list[RiverObject] = []
    for r in rows:
        upd = r.pop("updated_at")
        out.append(
            RiverObject(
                track="stock",
                entity_id=eid,
                object_type="event",
                ref=f"fact_stock_daily:{as_of}:{r['stock_ts_code']}",
                source_hash=_hash(r),
                valid_from=as_of,
                recorded_at=_ts(upd),
                payload=r,
            )
        )
    return out


def _judgment_track(
    as_of: str, eid: str, ename: str, checkpoints_path: Path
) -> TrackResult:
    """判断轨：用户登记的可证伪点。

    ``ref`` 直接用记录自带的 ``id``（``checkpoints.py:172`` 的 ``_make_id``，内容派生
    哈希，追加式 JSONL 下天然稳定），不新造主键。
    ``recorded_at`` 用记录的 ``ts``——判断轨是六条轨里**唯一原生带记录时刻**的一条。
    ``valid_from`` 用 as-of 交易日：判断所指的日子，不是写下的日子。
    """
    if not checkpoints_path.exists():
        return Gap("judgment", "no_source", f"{checkpoints_path} 不存在")
    out: list[RiverObject] = []
    with checkpoints_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            # 实体口径：checkpoint 的 themes 是自由文本，只做精确同名匹配。
            if ename not in (rec.get("themes") or []):
                continue
            if str(rec.get("ts", ""))[:10] != as_of:
                continue
            out.append(
                RiverObject(
                    track="judgment",
                    entity_id=eid,
                    object_type="checkpoint",
                    ref=f"checkpoints.jsonl:{rec.get('id')}",
                    source_hash=_hash(rec),
                    valid_from=as_of,
                    recorded_at=_ts(rec.get("ts")),
                    payload={
                        "claim": rec.get("claim"),
                        "category": rec.get("category"),
                        "due": rec.get("due"),
                        "metric": rec.get("metric"),
                        "themes": rec.get("themes"),
                    },
                )
            )
    if not out:
        return Gap("judgment", "no_data", f"{as_of} 没有挂在「{ename}」上的可证伪点")
    return out


# --------------------------------------------------------------------------- #
# 联立
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EntityRef:
    """实体在河上的身份。

    ``canonical_id`` 是跨供应商稳定的主键，``code_on_date`` 是那一天库里真实的代码。
    两者分开是因为 2026 年换过一次板块数据供应商（同花顺 ``.TI`` → fupanhui ``.FP``），
    而且**不是一刀切**：实测 ``.TI`` 覆盖 2024-12-25~2026-07-24、``.FP`` 覆盖
    2025-10-09~2026-09-02，两套重叠九个月，每个板块的切换日还各不相同
    （2026-07-14 那天「半导体」已是 ``.FP``、「钢铁」还是 ``.TI``）。

    不做这层归一，同一个板块在换源前后就是两个 entity_id，区间与队列查询会把
    一个板块悄悄劈成两个实体，而断点因板块而异——查不出来也报不出来。
    """

    canonical_id: str
    code_on_date: str
    name: str
    alias_applied: bool = False


def _alias_map(con: Any) -> dict[str, str]:
    """``config_sector_alias``：旧供应商代码 → 现行代码。

    这张表 2026-09-05 审计时**全仓零引用**（连写入方都没有），但内容是对的：
    117 条 provider-migration 映射，每条都带 ``confidence`` 与两段覆盖区间。
    """
    try:
        rows = _rows(con, "SELECT alias, sector_ts_code FROM config_sector_alias", [])
    except Exception:  # 表不存在的老库：退化成不归一，不报错
        return {}
    return {str(r["alias"]): str(r["sector_ts_code"]) for r in rows if r["alias"] and r["sector_ts_code"]}


def resolve_entity(con: Any, as_of: str, entity: str) -> EntityRef | None:
    """把用户给的实体解析成跨供应商稳定的身份，只做精确匹配。

    接受代码或板块名。解析不出就返回 None——**不做模糊匹配**：几套命名空间之间
    没有通用桥接表，猜错会静默串轨，比读不出来更糟。

    ⚠ 归一的是**身份**，不是**可比性**。别名表自己的 note 写着「两套口径成分不同，
    跨切换日数值不可直接比较」——所以 ``alias_applied`` 会一路带到切片上，
    跨换源日做数值比较的调用方必须自己看这个标记。
    """
    rows = _rows(
        con,
        """
        SELECT sector_ts_code, sector_name FROM fact_sector_daily
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
          AND (sector_ts_code = ? OR sector_name = ?)
        LIMIT 1
        """,
        [as_of, entity, entity],
    )
    if not rows:
        # 用户给的可能是现行代码，而这一天库里还是旧代码——反查别名表。
        alias = _alias_map(con)
        old_codes = [old for old, new in alias.items() if new == entity]
        for old in sorted(old_codes):
            rows = _rows(
                con,
                """
                SELECT sector_ts_code, sector_name FROM fact_sector_daily
                WHERE CAST(trade_date AS DATE) = CAST(? AS DATE) AND sector_ts_code = ?
                LIMIT 1
                """,
                [as_of, old],
            )
            if rows:
                break
        if not rows:
            return None

    code = str(rows[0]["sector_ts_code"])
    name = str(rows[0]["sector_name"])
    canonical = _alias_map(con).get(code, code)
    return EntityRef(
        canonical_id=canonical, code_on_date=code, name=name, alias_applied=canonical != code
    )


def _enforce_cutoff(tracks: dict[Track, TrackResult], cutoff: str) -> dict[Track, TrackResult]:
    """滤掉 ``recorded_at > C`` 或为 NULL 的对象；整条轨被滤空则退化成 ``Gap``。

    ``recorded_at`` 为 NULL 的一律滤掉：不可判等于不能证明当时已知，按无前视红线
    走 fail closed，不给「可能知道」留后门。
    """
    out: dict[Track, TrackResult] = {}
    for track, result in tracks.items():
        if isinstance(result, Gap):
            out[track] = result
            continue
        kept = [o for o in result if o.recorded_at is not None and o.recorded_at[:10] <= cutoff]
        if kept:
            out[track] = kept
        else:
            out[track] = Gap(
                track,
                "pit_filtered",
                f"{len(result)} 个对象的 recorded_at 晚于 cutoff={cutoff} 或缺失，按无前视滤除",
            )
    return out


def slice_river(
    as_of: str,
    entity: str,
    *,
    knowledge_cutoff: str | None = None,
    require_strict: bool = False,
    allow_hindsight: bool = False,
    db_path: str | Path | None = None,
    checkpoints_path: str | Path | None = None,
    teaching_labels_db: str | Path | None = None,
) -> RiverSlice:
    """取 ``as_of`` 这一天、``entity`` 这个实体的六轨对齐切片。

    ``knowledge_cutoff`` 缺省 = ``as_of``（当日带读口径）。回放 / 校准要显式传，
    且必须 ``<= as_of``——**本层强制**，不是文档约定。

    ``teaching_labels_db`` 给了授课框架旁路库时，盘面轨多出 ``teaching_*`` 对象（当日阶段读数、
    王朝链截至当日的状态、区间涨幅高标组，见 ``teaching_framework.river_objects``）；不给则
    切片与此前**逐字节相同**——roadmap G-01 (b)「关掉后输出与当前一致」在本层就成立。

    ``allow_hindsight=True`` 才允许 ``cutoff > as_of``，对应终局 spec §4.1 的第三档
    「事后人工复核」。这一档的切片 ``hindsight=True`` 且 ``pit_grade`` 永远不是
    ``strict``，spec 明写它「不得进入任何校准或方法有效性统计」。

    ``require_strict=True`` 时本层直接滤掉 ``recorded_at > C`` 与 ``recorded_at``
    缺失的对象，被滤空的轨返回 ``Gap(reason="pit_filtered")``。回放、校准、
    ``methodology_backtest`` 这类**不能看见未来**的消费方必须传它；当日带读不用传。
    """
    import duckdb

    cutoff = knowledge_cutoff or as_of
    # 未来日期当 cutoff = 时间穿越：`_enforce_cutoff` 与 `pit_grade` 都拿它做比较，
    # 传 2099-01-01 会让**所有**对象通过 PIT 检查，回放结果因此偏乐观且自称可信。
    # 默认拒绝而不是默认放行：无前视是这条河的核心承诺，破它要显式签字。
    hindsight = cutoff > as_of
    if hindsight and not allow_hindsight:
        raise ValueError(
            f"knowledge_cutoff={cutoff!r} 晚于 as_of={as_of!r}：那是事后视角，会带上后来才知道的事。"
            " 人工复核确需如此就显式传 allow_hindsight=True（该片 pit_grade 永远不是 strict，"
            "且不得进入校准与方法有效性统计）。"
        )
    if hindsight and require_strict:
        raise ValueError(
            "allow_hindsight 与 require_strict 互斥：前者放进未来对象，后者要求无前视。"
        )
    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        raise FileNotFoundError(f"数据库不存在：{db}（不自动创建）")

    if checkpoints_path is None:
        from intelligence.userspace import user_space

        checkpoints_path = user_space().checkpoints_path
    ck_path = Path(checkpoints_path)

    con = duckdb.connect(str(db), read_only=True)
    try:
        ref = resolve_entity(con, as_of, entity)
        if ref is None:
            # 实体在这一天解析不出来：六条轨全部是缺口，且原因是同一个。
            # 不回落到「最近一个有该板块的交易日」——那会把切片的 as-of 悄悄挪走。
            reason = f"{as_of} 的板块宇宙里没有「{entity}」（不做模糊匹配）"
            return RiverSlice(
                as_of=as_of,
                entity_id=entity,
                entity_name=entity,
                knowledge_cutoff=cutoff,
                tracks={t: Gap(t, "entity_unresolved", reason) for t in TRACKS},
                hindsight=hindsight,
            )
        # 各轨用**当天真实的代码**去查（否则查不到行），出来的对象再把 entity_id
        # 换成跨供应商稳定的 canonical_id。ref 保留当天的代码不动——它指向的是
        # 那一行真实数据，改了就回溯不过去。
        eid, ename = ref.code_on_date, ref.name
        tracks: dict[Track, TrackResult] = {
            "market": _market_track(con, as_of, eid, ename),
            "theme": _theme_track(con, as_of, eid, ename),
            "opinion": _opinion_track(con, as_of, eid, ename),
            "capital": _capital_track(con, as_of, eid, ename),
            "stock": _stock_track(con, as_of, eid, ename),
            "judgment": _judgment_track(as_of, eid, ename, ck_path),
        }
    finally:
        con.close()
    if teaching_labels_db is not None:
        from intelligence.services.teaching_framework.river_objects import teaching_objects

        teaching = teaching_objects(teaching_labels_db, as_of)
        if teaching:
            market = tracks["market"]
            # 教学对象本来就是盘面轨的对象（指数阶段），不是拿别的轨补编；盘面轨若是缺口而
            # 教学标签有值（实测不会——标签的输入就是盘面行），也如实放出对象而不是留缺口。
            tracks["market"] = [*market, *teaching] if isinstance(market, list) else teaching
    if ref.alias_applied:
        tracks = {
            track: result
            if isinstance(result, Gap)
            else [
                obj if obj.entity_id == "__market__" else replace(obj, entity_id=ref.canonical_id)
                for obj in result
            ]
            for track, result in tracks.items()
        }
    if require_strict:
        tracks = _enforce_cutoff(tracks, cutoff)
    return RiverSlice(
        as_of=as_of,
        entity_id=ref.canonical_id,
        entity_name=ref.name,
        knowledge_cutoff=cutoff,
        tracks=tracks,
        alias_applied=ref.alias_applied,
        hindsight=hindsight,
    )


def render(sl: RiverSlice) -> str:
    lines = [
        f"as_of={sl.as_of}  entity={sl.entity_id} {sl.entity_name}  "
        f"cutoff={sl.knowledge_cutoff}  pit_grade={sl.pit_grade}"
        + ("  ⚠ hindsight=true（事后视角，不得进入校准与方法有效性统计）" if sl.hindsight else ""),
        "",
    ]
    for track in TRACKS:
        result = sl.tracks[track]
        if isinstance(result, Gap):
            lines.append(f"  {track:<9} GAP  {result.reason}: {result.detail}")
            continue
        rec = {o.recorded_at[:10] if o.recorded_at else "NULL" for o in result}
        lines.append(
            f"  {track:<9} {len(result):>3} obj  recorded_at={sorted(rec)}  "
            f"ref[0]={result[0].ref}"
        )
    return "\n".join(lines)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="时间长河 as-of 切片（垂直切片 v0）")
    ap.add_argument("as_of")
    ap.add_argument("entity", help="板块代码或板块名")
    ap.add_argument("--cutoff", default=None, help="knowledge_cutoff，缺省 = as_of；晚于 as_of 会被拒绝")
    ap.add_argument(
        "--allow-hindsight",
        action="store_true",
        help="允许 cutoff 晚于 as_of（事后人工复核档）。该片 pit_grade 永远不是 strict，不得进校准",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--teaching-labels-db",
        default=None,
        help="授课框架旁路库（scripts/teaching_framework.py 的 --labels-db）；给了盘面轨多出 teaching_* 对象，不给逐字节同前",
    )
    args = ap.parse_args()

    sl = slice_river(
        args.as_of, args.entity, knowledge_cutoff=args.cutoff, allow_hindsight=args.allow_hindsight,
        teaching_labels_db=args.teaching_labels_db,
    )
    print(json.dumps(sl.to_dict(), ensure_ascii=False, indent=2) if args.json else render(sl))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
