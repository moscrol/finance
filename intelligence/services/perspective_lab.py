"""Perspective Lab 多角色认知编程 (P0)：角色画像 + 文章 ingest + 多角色合议落档。

设计文档：``docs/superpowers/specs/2026-07-03-perspective-lab-design.md``。

核心取舍（P0）：

- **事实层与认知层分离**：角色（博主/趋势交易者/价值投资者/用户框架）只是解释同一份
  硬数据的镜头，不得改写事实；输出必须区分「事实 / 角色解释 / 证伪条件」。
- **学框架不学口癖**：画像 schema 记录 market_lenses / risk_triggers /
  falsification_style 等可迁移分析结构，不复刻语气。
- **确定性最小闭环**：P0 不依赖 LLM、不建向量索引；ingest 只做确定性字段抽取
  （标题/日期/来源/提及的指数与题材关键词），debate 由画像规则 + 用户提供的硬事实
  摘要确定性合成结构化报告。LLM 抽取留作后续开关（P1）。
- **本地私有落档**：全部数据落在 ``intelligence/users/<user>/perspectives/``，
  gitignore 不进仓库（版权 + 隐私边界）。

数据落点（均按用户隔离）：

- ``perspectives/profiles/<id>.json``            角色画像（schema_version=1）
- ``perspectives/articles/<id>/manifest.jsonl``  文章元信息台账（按内容哈希去重）
- ``perspectives/articles/<id>/raw/``            文章原文（本地私用）
- ``perspectives/debates.jsonl``                 每次合议的机器可读记录
- ``perspectives/outcomes.jsonl``                P2：假设验证台账（本版只预留）

本模块只用标准库，不依赖 duckdb / 联网，可离线运行、可独立单测。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.userspace import UserSpace

PROFILE_SCHEMA_VERSION = 1
DEBATE_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1

PERSPECTIVE_TYPES = (
    "blogger",
    "trend_trader",
    "value_investor",
    "user_framework",
    "kol_fengyuan",
)
MIN_ARTICLES_FOR_CONFIDENT_PROFILE = 3
PERSPECTIVE_MODE_NEUTRAL = "neutral"
PERSPECTIVE_MODE_SINGLE = "single"
PERSPECTIVE_MODE_COMPARE = "compare"
PERSPECTIVE_MODES = (
    PERSPECTIVE_MODE_NEUTRAL,
    PERSPECTIVE_MODE_SINGLE,
    PERSPECTIVE_MODE_COMPARE,
)
MAX_RUNTIME_PERSPECTIVES = 3

# perspective id 约束与 user_id 同风格：字母/数字开头，仅 [A-Za-z0-9._-]，≤64，防路径穿越。
_PERSPECTIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# 确定性抽取用的固定词表（只做关键词命中，不做任何推断）。
_KNOWN_INDICES = ("上证指数", "深证成指", "创业板指", "科创50", "北证50", "沪深300", "中证500", "中证1000")

# 内置角色画像：spec 8.1 的默认四类角色里，除 blogger 需用户 ingest 训练外，
# 其余三类给出可直接 debate 的基础画像（用户可 init 后手工编辑覆盖）。
_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "trend_trader": {
        "display_name": "趋势交易者视角",
        "type": "trend_trader",
        "market_lenses": [
            {"name": "市场阶段", "description": "指数、量能和赚钱效应处于启动/主升/分歧/兑现/退潮哪一段", "weight": 0.3},
            {"name": "资金选择", "description": "主线容量、涨停扩散、新高集群、核心股承接与相对强度", "weight": 0.4},
            {"name": "情绪结构", "description": "连板高度、炸板率、后排跟风意愿", "weight": 0.3},
        ],
        "opportunity_preferences": ["主线第一次分歧后的核心回流", "低位题材双红且涨停扩散", "缩量回踩关键均线的强势股"],
        "risk_triggers": ["缩量上涨且后排不跟", "高位核心放量滞涨", "炸板率骤升且新高集群收缩"],
        "evidence_hierarchy": ["盘面选择", "成交结构", "题材扩散", "消息催化"],
        "reasoning_patterns": [{"name": "先阶段后方向", "rule": "先定市场阶段，再讨论题材和个股；不脱离市场状态判断空间"}],
        "anti_patterns": ["只看产业逻辑不看盘面承接", "在退潮期抢反弹当主升做"],
        "falsification_style": [
            "如果核心股跌破关键均线且题材无新高扩散，则降低判断级别",
            "如果次日高开放量滞涨，则优先判断分歧转一致失败",
        ],
    },
    "value_investor": {
        "display_name": "价值投资者视角（Buffett-inspired）",
        "type": "value_investor",
        "market_lenses": [
            {"name": "估值与安全边际", "description": "当前价格相对内在价值/历史分位是否有安全边际", "weight": 0.4},
            {"name": "商业质量", "description": "护城河、竞争格局、长期现金流的可持续性", "weight": 0.4},
            {"name": "情绪温度计", "description": "市场狂热/恐慌程度，别人贪婪我恐惧", "weight": 0.2},
        ],
        "opportunity_preferences": ["好生意遇到坏消息的错杀", "高确定性现金流被短期情绪压制", "行业出清后的龙头集中"],
        "risk_triggers": ["估值透支多年成长", "商业模式依赖持续融资", "一致预期极度乐观"],
        "evidence_hierarchy": ["财报/年报", "公告/订单/产能", "产业链验证", "卖方观点", "盘面情绪"],
        "reasoning_patterns": [{"name": "先质量后价格", "rule": "先判断生意好坏与护城河，再谈价格与买点；不为博弈而买"}],
        "anti_patterns": ["把动量当基本面改善", "用短期盘面否定长期价值"],
        "falsification_style": [
            "如果核心资产盈利能力（毛利率/ROE）持续两个季度恶化，则重估内在价值",
            "如果估值分位进入历史极端区且无新增基本面，则降低仓位假设",
        ],
    },
    "user_framework": {
        "display_name": "用户复盘框架",
        "type": "user_framework",
        "market_lenses": [
            {"name": "市场阶段", "description": "用户自己的阶段划分（可手工编辑 profile 定制）", "weight": 0.5},
            {"name": "题材结构", "description": "主线/支线/轮动位置与个人能力圈匹配度", "weight": 0.5},
        ],
        "opportunity_preferences": ["与个人能力圈匹配、可条件化验证的机会"],
        "risk_triggers": ["超出能力圈的博弈", "无法给出证伪条件的判断"],
        "evidence_hierarchy": ["盘面选择", "公告/订单/产能", "产业链验证", "卖方观点", "情绪传闻"],
        "reasoning_patterns": [{"name": "条件化结论", "rule": "所有判断必须条件化：满足什么信号才成立，出现什么信号即放弃"}],
        "anti_patterns": ["把角色观点当事实", "无验证窗口的模糊判断"],
        "falsification_style": ["每个判断给出 T+1/T+3 可观察指标与 miss 条件"],
    },
    "kol_fengyuan": {
        "display_name": "风远框架视角",
        "type": "kol_fengyuan",
        "market_lenses": [
            {"name": "双锚模型", "description": "方向锚（板块方向股）与高度锚（连板高标）同时恶化+最后一龙冲高回落=全板块逆转信号", "weight": 0.2},
            {"name": "出清形态判别", "description": "区分A型出清（恐慌放量+V回，1-3天）与B型出清（买盘枯竭缩量阴跌，周期更长），两种形态的买点条件完全不同", "weight": 0.2},
            {"name": "五维排序", "description": "确定性×弹性×兑现时间×拥挤度×是否已定价，按市场场景（恐慌反弹/主升/高位拥挤）动态调权重，命中一票否决项直接出局", "weight": 0.25},
            {"name": "三级信号体系", "description": "领先指标（CapEx/交期/利用率）→确认指标（现货价/涨幅收敛）→滞后指标（合约价转负/库存），按层级而非单点判断周期位置", "weight": 0.2},
            {"name": "供给侧通胀框架", "description": "全球寡头格局+零新增产能+扩产周期长+需求爆发=供给弹性≈0环节的涨价确定性排序", "weight": 0.15},
        ],
        "opportunity_preferences": [
            "出清完成信号确认后的核心错杀修复（不接飞刀、等条件全部满足）",
            "供给弹性≈0且涨价已由头部厂商验证的上游材料环节",
            "增量资金回流第二阶段被主动选择的方向（不追第一波超跌反弹）",
        ],
        "risk_triggers": [
            "利多不涨+连板高标同时出现（板块抱团踩踏前兆，优先减仓）",
            "竞价第一屏任一锚恶化（高贝塔持仓先减1/3，举证责任翻转为证明该留）",
            "纯叙事票无业绩锚且估值锚定极远期（一票否决）",
            "ETF无差别赎回砸盘期接飞刀",
        ],
        "evidence_hierarchy": ["盘面资金选择", "涨价/订单/产能硬事实", "第三方数据交叉验证", "卖方观点", "叙事传闻"],
        "reasoning_patterns": [
            {"name": "先定周期位置再谈标的", "rule": "先用三级信号体系判断板块处于周期哪一段，再讨论个股；不脱离出清/退潮阶段谈买点"},
            {"name": "条件化买点", "rule": "买点必须是多条件同时满足（如缩量止跌+日内V反+同板块龙头开板+指数同步止跌），列出当前满足几条"},
            {"name": "资金结构归因", "rule": "暴跌先区分基本面恶化还是多类资金共振卖出（减仓/止损/割肉/ETF赎回），归因不同则应对不同"},
        ],
        "anti_patterns": [
            "把单次观察写成定律（框架需持续升级，如放量V回=出清完成已被B型出清证伪）",
            "抱最强股穿越退潮期的侥幸心态",
            "用滞后指标做领先判断",
        ],
        "falsification_style": [
            "每个框架给出显式失效条件与升级记录（如原三条件失效则升级为四条件并注明原因）",
            "判断给出验证窗口与反向证据清单：出现哪些信号即降级或放弃",
            "对自己持仓观点做反顺从检查，不因有仓位就调低风险权重",
        ],
    },
}

# 固定三问（spec 8.5）：角色互相质询不是自由聊天。
CROSS_EXAM_QUESTIONS = (
    "你认为对方忽略了什么关键变量？",
    "你认为对方把哪类弱证据当强证据？",
    "如果明天只能看三个指标，你会用哪三个指标验证谁更接近现实？",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return date_cls.today().isoformat()


def resolve_perspective_id(perspective_id: str) -> str:
    """校验 perspective id：防路径穿越，约束与 user_id 同风格。"""
    raw = str(perspective_id or "").strip()
    if raw in {".", ".."} or "/" in raw or "\\" in raw or not _PERSPECTIVE_ID_RE.match(raw):
        raise ValueError(
            f"非法 perspective id：{perspective_id!r}（只允许字母数字与 . _ -，需以字母/数字开头，长度≤64）"
        )
    return raw


# --------------------------------------------------------------------------- #
# 路径解析：全部收口在 users/<user>/perspectives/ 内
# --------------------------------------------------------------------------- #
def perspectives_root(us: UserSpace) -> Path:
    return us.root / "perspectives"


def profile_path(us: UserSpace, perspective_id: str) -> Path:
    pid = resolve_perspective_id(perspective_id)
    return perspectives_root(us) / "profiles" / f"{pid}.json"


def articles_dir(us: UserSpace, perspective_id: str) -> Path:
    pid = resolve_perspective_id(perspective_id)
    return perspectives_root(us) / "articles" / pid


def manifest_path(us: UserSpace, perspective_id: str) -> Path:
    return articles_dir(us, perspective_id) / "manifest.jsonl"


def debates_path(us: UserSpace) -> Path:
    return perspectives_root(us) / "debates.jsonl"


def outcomes_path(us: UserSpace) -> Path:
    return perspectives_root(us) / "outcomes.jsonl"


@dataclass(frozen=True)
class RuntimePerspectiveContext:
    mode: str
    perspective_ids: tuple[str, ...]
    display_names: tuple[str, ...]
    prompt: str

    def answer_header(self) -> str:
        if self.mode == PERSPECTIVE_MODE_NEUTRAL:
            return "当前视角：数据中立\n来源范围：数据提供方、公开来源与本轮检索证据"
        if self.mode == PERSPECTIVE_MODE_SINGLE:
            return (
                f"当前视角：{self.display_names[0]}\n"
                f"来源范围：本轮事实证据 + {self.display_names[0]} 独立观点层"
            )
        names = "｜".join(("数据中立", *self.display_names))
        return f"当前视角：多视角并列（{names}）\n来源范围：本轮事实证据 + 各视角独立观点层"


# --------------------------------------------------------------------------- #
# profile：init / load / render
# --------------------------------------------------------------------------- #
def default_profile(perspective_id: str, display_name: str, ptype: str, *, ts: str | None = None) -> dict[str, Any]:
    pid = resolve_perspective_id(perspective_id)
    if ptype not in PERSPECTIVE_TYPES:
        raise ValueError(f"非法角色类型：{ptype!r}（可用：{'/'.join(PERSPECTIVE_TYPES)}）")
    now = ts or _now_iso()
    builtin = _BUILTIN_PROFILES.get(ptype) if ptype != "blogger" else None
    profile: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "id": pid,
        "display_name": display_name.strip() or pid,
        "type": ptype,
        "created_at": now,
        "updated_at": now,
        "source_policy": {
            "allowed_sources": ["uploaded_articles"],
            "citation_required": True,
            "min_articles_for_confident_profile": MIN_ARTICLES_FOR_CONFIDENT_PROFILE,
        },
        "market_lenses": [],
        "opportunity_preferences": [],
        "risk_triggers": [],
        "evidence_hierarchy": [],
        "reasoning_patterns": [],
        "anti_patterns": [],
        "falsification_style": [],
        "voice_guidance": {"style": "清晰、直接、少口癖", "forbidden": ["复刻私人语气", "冒充本人"]},
        "confidence": {
            "article_count": 0,
            "profile_confidence": "low",
            "known_gaps": ["样本不足时只能作为候选视角"],
        },
    }
    if builtin:
        for key in (
            "market_lenses",
            "opportunity_preferences",
            "risk_triggers",
            "evidence_hierarchy",
            "reasoning_patterns",
            "anti_patterns",
            "falsification_style",
        ):
            profile[key] = json.loads(json.dumps(builtin[key], ensure_ascii=False))
        if not display_name.strip():
            profile["display_name"] = builtin["display_name"]
    return profile


def init_perspective(
    us: UserSpace,
    perspective_id: str,
    *,
    display_name: str = "",
    ptype: str = "blogger",
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """创建角色：空/内置 profile + 文章目录。已存在则报错，不覆盖。"""
    path = profile_path(us, perspective_id)
    if path.exists():
        raise ValueError(f"角色已存在：{path}（如需修改请直接编辑该 JSON）")
    profile = default_profile(perspective_id, display_name, ptype, ts=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    (articles_dir(us, perspective_id) / "raw").mkdir(parents=True, exist_ok=True)
    (perspectives_root(us) / "notes").mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, profile


def load_profile(us: UserSpace, perspective_id: str) -> dict[str, Any]:
    path = profile_path(us, perspective_id)
    if not path.exists():
        raise FileNotFoundError(
            f"角色「{perspective_id}」不存在（{path}）；先 `perspective init --id {perspective_id}` 创建。"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"角色画像不是 JSON 对象：{path}")
    return data


def list_profiles(us: UserSpace) -> list[dict[str, Any]]:
    root = perspectives_root(us) / "profiles"
    if not root.exists():
        return []
    profiles: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        perspective_id = str(data.get("id") or "").strip()
        try:
            resolve_perspective_id(perspective_id)
        except ValueError:
            continue
        confidence = data.get("confidence") or {}
        profiles.append(
            {
                "perspective_id": perspective_id,
                "display_name": str(data.get("display_name") or perspective_id),
                "type": str(data.get("type") or "blogger"),
                "article_count": int(confidence.get("article_count") or 0),
                "profile_confidence": str(
                    confidence.get("profile_confidence") or "low"
                ),
            }
        )
    return profiles


def validate_runtime_selection(
    us: UserSpace,
    mode: str,
    perspective_ids: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    if mode not in PERSPECTIVE_MODES:
        raise ValueError(f"非法视角模式：{mode!r}")
    resolved = tuple(resolve_perspective_id(item) for item in perspective_ids)
    if len(set(resolved)) != len(resolved):
        raise ValueError("视角不能重复选择")
    if len(resolved) > MAX_RUNTIME_PERSPECTIVES:
        raise ValueError(f"最多选择 {MAX_RUNTIME_PERSPECTIVES} 个视角")
    if mode == PERSPECTIVE_MODE_NEUTRAL and resolved:
        raise ValueError("数据中立模式不能选择 KOL 视角")
    if mode == PERSPECTIVE_MODE_SINGLE and len(resolved) != 1:
        raise ValueError("单一视角模式必须选择 1 个 KOL 视角")
    if mode == PERSPECTIVE_MODE_COMPARE and not resolved:
        raise ValueError("多视角并列模式至少选择 1 个 KOL 视角")
    for perspective_id in resolved:
        load_profile(us, perspective_id)
    return resolved


def _search_terms(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", str(text or "").lower())
    words = re.findall(r"[a-z0-9._-]+", normalized)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    bigrams = [chinese[index : index + 2] for index in range(max(0, len(chinese) - 1))]
    return list(dict.fromkeys([*words, *bigrams]))


def _article_documents(us: UserSpace, perspective_id: str) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    for record in _read_manifest(manifest_path(us, perspective_id)):
        raw_path = Path(str(record.get("raw_path") or ""))
        try:
            raw_path.resolve().relative_to(perspectives_root(us).resolve())
        except (OSError, ValueError):
            continue
        if not raw_path.is_file():
            continue
        try:
            text = raw_path.read_text(encoding="utf-8")
        except OSError:
            continue
        documents.append(
            {
                "title": str(record.get("title") or raw_path.stem),
                "date": str(record.get("date") or ""),
                "source": str(record.get("source") or ""),
                "text": text,
            }
        )
    return documents


def retrieve_article_snippets(
    us: UserSpace,
    perspective_id: str,
    query: str,
    *,
    limit: int = 3,
    excerpt_chars: int = 360,
) -> list[dict[str, str]]:
    documents = _article_documents(us, perspective_id)
    query_terms = _search_terms(query)
    if not documents or not query_terms:
        return []
    tokenized = [_search_terms(document["text"]) for document in documents]
    doc_count = len(documents)
    avg_length = sum(len(tokens) for tokens in tokenized) / doc_count
    document_frequency = {
        term: sum(1 for tokens in tokenized if term in tokens) for term in query_terms
    }
    scored: list[tuple[float, dict[str, str]]] = []
    for document, tokens in zip(documents, tokenized):
        frequencies = {term: tokens.count(term) for term in query_terms}
        score = 0.0
        for term, frequency in frequencies.items():
            if frequency == 0:
                continue
            idf = math.log(
                1 + (doc_count - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + 1.5 * (
                1 - 0.75 + 0.75 * len(tokens) / max(avg_length, 1)
            )
            score += idf * frequency * 2.5 / denominator
        if score <= 0:
            continue
        normalized_text = re.sub(r"\s+", " ", document["text"]).strip()
        positions = [
            normalized_text.lower().find(term)
            for term in query_terms
            if normalized_text.lower().find(term) >= 0
        ]
        start = max(0, (min(positions) if positions else 0) - excerpt_chars // 4)
        excerpt = normalized_text[start : start + excerpt_chars]
        if start > 0:
            excerpt = f"…{excerpt}"
        if start + excerpt_chars < len(normalized_text):
            excerpt = f"{excerpt}…"
        scored.append(
            (
                score,
                {
                    "title": document["title"],
                    "date": document["date"],
                    "source": document["source"],
                    "excerpt": excerpt,
                },
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [document for _, document in scored[:limit]]


def _profile_prompt(
    profile: dict[str, Any],
    snippets: list[dict[str, str]],
) -> str:
    confidence = profile.get("confidence") or {}
    lines = [
        f"### {profile.get('display_name')}（{profile.get('id')}）",
        f"- 画像置信度：{confidence.get('profile_confidence', 'low')}；"
        f"样本数：{confidence.get('article_count', 0)}",
        "- 市场镜头："
        + "；".join(
            f"{lens.get('name')}：{lens.get('description')}"
            for lens in profile.get("market_lenses") or []
        ),
        # 证据层级与推理模板此前没进 prompt——实测后果是视角"名存实薄"：
        # LLM 拿不到「该视角先看什么、按什么顺序推理」，输出被通用研究契约压过。
        "- 证据层级（该视角的证据优先顺序，越靠前越优先）："
        + "；".join(str(item) for item in profile.get("evidence_hierarchy") or []),
        "- 推理模板："
        + "；".join(
            f"{pattern.get('name')}：{pattern.get('rule')}"
            for pattern in profile.get("reasoning_patterns") or []
        ),
        "- 机会偏好：" + "；".join(profile.get("opportunity_preferences") or []),
        "- 风险信号：" + "；".join(profile.get("risk_triggers") or []),
        "- 反模式（该视角会批评/避免的做法）："
        + "；".join(profile.get("anti_patterns") or []),
        "- 证伪方式：" + "；".join(profile.get("falsification_style") or []),
        "- 原文召回（观点层，不是事实）：",
    ]
    if not snippets:
        lines.append("  - 未召回相关文章；该视角未知，不得补写其观点。")
    for snippet in snippets:
        source = " / ".join(
            item for item in (snippet["date"], snippet["source"], snippet["title"]) if item
        )
        lines.append(f"  - {source or '未标注来源'}：{snippet['excerpt']}")
    return "\n".join(lines)


def build_runtime_context(
    us: UserSpace,
    *,
    mode: str,
    perspective_ids: list[str] | tuple[str, ...],
    query: str,
) -> RuntimePerspectiveContext:
    resolved = validate_runtime_selection(us, mode, perspective_ids)
    if mode == PERSPECTIVE_MODE_NEUTRAL:
        return RuntimePerspectiveContext(
            mode=mode,
            perspective_ids=(),
            display_names=(),
            prompt=(
                "本轮使用数据中立视角。只使用数据提供方、公开来源和本轮检索证据；"
                "不得调用或模拟任何 KOL 观点、个人金融记忆或历史经验判断。"
                "输出时明确区分事实、未知和 AI 推理，不把推理写成事实。"
            ),
        )
    profiles = [load_profile(us, perspective_id) for perspective_id in resolved]
    profile_blocks = [
        _profile_prompt(
            profile,
            retrieve_article_snippets(us, str(profile["id"]), query),
        )
        for profile in profiles
    ]
    # 证据纪律对 single/compare 通用：视角的证据层级决定证据的组织顺序；
    # 首选证据层缺失时必须"大声失败"而不是静默换证据——上次实测的失败形状是
    # 盘面派视角拿不到量价数据时，回答被通用研究话术（公告/订单门槛）整体接管，
    # 用户看到的是一份没有视角的报告，且没人告诉他视角其实没起作用。
    evidence_discipline = (
        "证据组织必须服从该视角的证据层级：优先用其排序靠前的证据类型作答；"
        "若本轮证据缺少该视角的首选证据层（如盘面量价/成交结构），"
        "必须在回答开头显式声明「该视角首选证据（XX）本轮缺失，以下映射基于次级证据」，"
        "不得用其他层级证据冒充首选层判断，也不得因此把视角输出降格为通用研究结论。"
    )
    if mode == PERSPECTIVE_MODE_SINGLE:
        contract = (
            "只允许使用下方这一位 KOL 的画像与原文召回，不得混入其他 KOL 或个人记忆。"
            "KOL 内容属于观点层，当前检索数据属于事实层，AI 映射属于推理层，三者必须分开。"
            f"{evidence_discipline}"
            "按以下结构输出：当前视角、来源范围、KOL原始判断、当前行情映射、"
            "支持/冲突数据、适用条件、失效条件、置信度、未知项。"
            "原文未覆盖的问题必须写“该视角未知”，不得代替本人补写。"
        )
    else:
        contract = (
            "本轮使用多视角并列。先单列“数据中立”，再逐一单列下方每个 KOL；"
            "各视角不得互相污染，不得以多数意见自动成为事实。"
            f"{evidence_discipline}"
            "最后单列视角冲突、综合判断、风险与未知；综合判断必须标注为 AI 推理。"
        )
    return RuntimePerspectiveContext(
        mode=mode,
        perspective_ids=resolved,
        display_names=tuple(
            str(profile.get("display_name") or profile["id"]) for profile in profiles
        ),
        prompt=(
            f"{contract}\n\n"
            "以下为选中视角的私有观点上下文，只能用于解释本轮事实证据：\n"
            + "\n\n".join(profile_blocks)
        ),
    )


def runtime_answer_header(
    us: UserSpace,
    *,
    mode: str,
    perspective_ids: list[str] | tuple[str, ...],
) -> str:
    resolved = validate_runtime_selection(us, mode, perspective_ids)
    display_names = tuple(
        str(profile.get("display_name") or perspective_id)
        for perspective_id in resolved
        for profile in (load_profile(us, perspective_id),)
    )
    return RuntimePerspectiveContext(
        mode=mode,
        perspective_ids=resolved,
        display_names=display_names,
        prompt="",
    ).answer_header()


def runtime_fallback_notice(mode: str) -> str:
    if mode == PERSPECTIVE_MODE_NEUTRAL:
        return ""
    if mode == PERSPECTIVE_MODE_SINGLE:
        return (
            "KOL原始判断：该视角未知（本轮未完成 LLM 视角映射）。\n"
            "下方内容仅为数据中立事实底座，不代表该 KOL 的判断。"
        )
    return (
        "各 KOL 原始判断：该视角未知（本轮未完成 LLM 多视角映射）。\n"
        "下方内容仅为数据中立事实底座，不代表任何 KOL 的判断或共识。"
    )


def _save_profile(us: UserSpace, profile: dict[str, Any]) -> Path:
    path = profile_path(us, str(profile.get("id")))
    profile["updated_at"] = _now_iso()
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def render_profile_text(profile: dict[str, Any]) -> str:
    conf = profile.get("confidence") or {}
    lines = [
        f"# 角色画像：{profile.get('display_name')}（{profile.get('id')} / {profile.get('type')}）",
        f"- 样本文章数：{conf.get('article_count', 0)}",
        f"- 置信度：{conf.get('profile_confidence', 'low')}",
        f"- 已知缺口：{'；'.join(conf.get('known_gaps') or []) or '无'}",
        "",
        "## 市场镜头",
    ]
    for lens in profile.get("market_lenses") or []:
        lines.append(f"- {lens.get('name')}（权重 {lens.get('weight')}）：{lens.get('description')}")
    lines += ["", "## 机会偏好"]
    lines += [f"- {v}" for v in profile.get("opportunity_preferences") or []]
    lines += ["", "## 风险降权信号"]
    lines += [f"- {v}" for v in profile.get("risk_triggers") or []]
    lines += ["", "## 证伪风格"]
    lines += [f"- {v}" for v in profile.get("falsification_style") or []]
    return "\n".join(lines) + "\n"


def _confidence_label(article_count: int) -> str:
    return "medium" if article_count >= MIN_ARTICLES_FOR_CONFIDENT_PROFILE else "low"


# --------------------------------------------------------------------------- #
# 文章 ingest：保存原文 + manifest 去重 + 确定性抽取
# --------------------------------------------------------------------------- #
def _slugify_title(title: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title.strip())
    return s.strip("-")[:60] or "article"


def extract_market_context(text: str) -> dict[str, list[str]]:
    """确定性关键词命中（不推断）：只报告固定词表里的指数名。题材/个股 P0 留空。"""
    return {
        "mentioned_indices": [name for name in _KNOWN_INDICES if name in text],
        "mentioned_themes": [],
        "mentioned_stocks": [],
    }


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def ingest_article(
    us: UserSpace,
    perspective_id: str,
    input_path: str | Path,
    *,
    title: str,
    date: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """保存原文 + 写 manifest（按内容哈希去重）+ 更新画像置信度。

    先做完所有校验再落盘：文章不存在/角色不存在时不写任何半成品。
    """
    profile = load_profile(us, perspective_id)  # 缺 profile 先报错
    src = Path(input_path)
    if not src.is_file():
        raise FileNotFoundError(f"文章不存在：{src}")
    if not str(title or "").strip():
        raise ValueError("必须提供 --title")
    day = str(date or _today()).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError(f"非法日期：{date!r}（需要 YYYY-MM-DD）")

    text = src.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    article_id = f"pa-{content_hash}"

    mpath = manifest_path(us, perspective_id)
    existing = _read_manifest(mpath)
    for rec in existing:
        if rec.get("article_id") == article_id:
            return {"article_id": article_id, "duplicate": True, "raw_path": rec.get("raw_path")}

    raw_dir = articles_dir(us, perspective_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{day}-{_slugify_title(title)}.md"
    if raw_path.exists():  # 同日同名不同内容：加哈希后缀避免覆盖
        raw_path = raw_dir / f"{day}-{_slugify_title(title)}-{content_hash}.md"
    shutil.copyfile(src, raw_path)

    record = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "article_id": article_id,
        "perspective_id": profile["id"],
        "title": title.strip(),
        "date": day,
        "source": (source or "").strip() or None,
        "raw_path": str(raw_path),
        "chars": len(text),
        "market_context": extract_market_context(text),
        "ingested_at": _now_iso(),
    }
    with mpath.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 更新画像置信度（确定性：只改样本数与置信度标签，不动认知字段）
    conf = profile.setdefault("confidence", {})
    count = len(existing) + 1
    conf["article_count"] = count
    conf["profile_confidence"] = _confidence_label(count)
    if conf["profile_confidence"] == "low":
        gaps = conf.setdefault("known_gaps", [])
        if "样本不足时只能作为候选视角" not in gaps:
            gaps.append("样本不足时只能作为候选视角")
    else:
        conf["known_gaps"] = [g for g in conf.get("known_gaps") or [] if g != "样本不足时只能作为候选视角"]
    _save_profile(us, profile)

    return {"article_id": article_id, "duplicate": False, "raw_path": str(raw_path), "article_count": count}


# --------------------------------------------------------------------------- #
# 多角色合议（P0 确定性版）
# --------------------------------------------------------------------------- #
def _hit_terms(terms: list[str], facts: str) -> list[str]:
    """确定性信号匹配：画像里的信号词有没有出现在硬事实摘要里（子串命中）。"""
    norm_facts = re.sub(r"\s+", "", facts)
    return [t for t in terms if t and re.sub(r"\s+", "", t) in norm_facts]


def _role_section(profile: dict[str, Any], facts: str) -> dict[str, Any]:
    lenses = profile.get("market_lenses") or []
    conf = profile.get("confidence") or {}
    low_sample = profile.get("type") == "blogger" and conf.get("profile_confidence") != "medium"
    return {
        "perspective_id": profile.get("id"),
        "display_name": profile.get("display_name"),
        "lenses": [f"{ln.get('name')}：{ln.get('description')}" for ln in lenses],
        "opportunity_hits": _hit_terms(profile.get("opportunity_preferences") or [], facts),
        "risk_hits": _hit_terms(profile.get("risk_triggers") or [], facts),
        "confirm_signals": list(profile.get("opportunity_preferences") or []),
        "falsify_signals": list(profile.get("risk_triggers") or []),
        "falsification_style": list(profile.get("falsification_style") or []),
        "blind_spots": list(profile.get("anti_patterns") or []),
        "low_sample": low_sample,
    }


def run_debate(
    us: UserSpace,
    *,
    query: str,
    perspective_ids: list[str],
    facts: str,
    date: str | None = None,
    save: bool = True,
) -> tuple[str, dict[str, Any]]:
    """P0 确定性合议：画像规则 × 用户提供的硬事实摘要 → 结构化 Markdown 报告。

    不调用 LLM、不编造判断：角色段落只输出「镜头 / 命中的机会信号 / 命中的风险信号 /
    确认与反证清单 / 盲区」，裁判层做确定性交叉对比（共同命中 vs 分歧）并给退化提示。
    """
    if not str(query or "").strip():
        raise ValueError("必须提供 --query")
    duplicates = sorted({pid for pid in perspective_ids if perspective_ids.count(pid) > 1})
    if duplicates:
        raise ValueError(f"重复的 --perspective：{'、'.join(duplicates)}（同一角色不能重复参与合议）")
    if len(perspective_ids) < 2:
        raise ValueError("至少需要 2 个不同的 --perspective 才能合议")
    facts = str(facts or "").strip()
    if not facts:
        raise ValueError("P0 需要用 --facts / --facts-file 提供硬事实摘要（P1 才自动接 ask）")
    day = str(date or _today()).strip()

    profiles = [load_profile(us, pid) for pid in perspective_ids]
    sections = [_role_section(p, facts) for p in profiles]

    # 裁判层（确定性）：共同风险命中 = 共识；只有单角色命中的 = 分歧点。
    risk_sets = {s["perspective_id"]: set(s["risk_hits"]) for s in sections}
    opp_sets = {s["perspective_id"]: set(s["opportunity_hits"]) for s in sections}
    all_risk = set().union(*risk_sets.values()) if risk_sets else set()
    all_opp = set().union(*opp_sets.values()) if opp_sets else set()
    shared_risk = set.intersection(*risk_sets.values()) if risk_sets else set()
    shared_opp = set.intersection(*opp_sets.values()) if opp_sets else set()
    divergent = sorted((all_risk | all_opp) - (shared_risk | shared_opp))
    degenerate = not divergent  # 所有角色命中完全一致 → 本次辩论无增量

    facts_hash = hashlib.sha256(facts.encode("utf-8")).hexdigest()
    debate_id = "pd-" + hashlib.sha256(
        f"{day}|{query}|{','.join(perspective_ids)}|{facts_hash}".encode()
    ).hexdigest()[:12]

    lines: list[str] = [f"# Perspective Debate：{query}", ""]
    lines += [
        "## 0. 输入与证据边界",
        f"- 市场数据日期：{day}",
        "- 硬事实来源：用户提供的摘要（P0；P1 起自动接 ask 证据链）",
        f"- 角色：{'、'.join(s['display_name'] for s in sections)}",
        "- 缺口：P0 无文章片段召回（RAG 在 P1），角色段落为画像规则的确定性匹配",
        "",
        "## 1. 硬事实底座（以下为事实，未经角色改写）",
    ]
    lines += [f"> {ln}" for ln in facts.splitlines() if ln.strip()]
    lines += ["", "## 2. 角色独立判断（以下均为角色解释，不是事实）"]
    for i, s in enumerate(sections, 1):
        lines += [
            f"### 2.{i} {s['display_name']}（{s['perspective_id']}）",
            f"- 市场镜头：{'；'.join(s['lenses']) or '（画像未填写，请编辑 profile）'}",
            f"- 命中的机会信号：{'；'.join(s['opportunity_hits']) or '无（硬事实中未出现该角色偏好的机会特征）'}",
            f"- 命中的风险信号：{'；'.join(s['risk_hits']) or '无（硬事实中未出现该角色的降权信号）'}",
            f"- 确认信号清单：{'；'.join(s['confirm_signals']) or '（画像未填写）'}",
            f"- 反证信号清单：{'；'.join(s['falsify_signals']) or '（画像未填写）'}",
            f"- 证伪风格：{'；'.join(s['falsification_style']) or '（画像未填写）'}",
            f"- 盲区（anti-patterns）：{'；'.join(s['blind_spots']) or '（画像未填写）'}",
        ]
        if s["low_sample"]:
            lines.append("- ⚠️ 样本不足，只能作为候选视角（文章数 < 3）")
        lines.append("")
    lines += ["## 3. 角色互相质询（固定三问，供人工/LLM 逐角色作答）"]
    lines += [f"{i}. {q}" for i, q in enumerate(CROSS_EXAM_QUESTIONS, 1)]
    lines += [
        "",
        "## 4. 裁判合议（系统合成层，确定性交叉对比）",
        f"- 所有角色共同命中的机会信号：{'；'.join(sorted(shared_opp)) or '无'}",
        f"- 所有角色共同命中的风险信号：{'；'.join(sorted(shared_risk)) or '无'}",
        f"- 分歧点（仅部分角色命中）：{'；'.join(divergent) or '无'}",
    ]
    if degenerate:
        lines.append("- ⚠️ 退化提示：各角色信号命中完全一致，本次辩论无增量；请检查画像差异或补充硬事实细节")
    lines += [
        "- 加权/降权理由：P0 按「命中风险信号多的角色提示优先复核」处理；长期胜率加权在 P2",
        "",
        "## 5. 可证伪假设（P0 只写报告，接 checkpoint 在 P2）",
        "| id | 假设 | 验证窗口 | 指标 | hit 条件 | miss 条件 |",
        "|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(sections, 1):
        style = s["falsification_style"][0] if s["falsification_style"] else "（画像未填写证伪风格）"
        lines.append(f"| h{i} | {s['display_name']}视角的首要证伪点 | T+1 | 待人工填写 | 待人工填写 | {style} |")
    report = "\n".join(lines) + "\n"

    record = {
        "schema_version": DEBATE_SCHEMA_VERSION,
        "debate_id": debate_id,
        "date": day,
        "query": query.strip(),
        "perspectives": [s["perspective_id"] for s in sections],
        "facts": facts,
        "shared_opportunity_hits": sorted(shared_opp),
        "shared_risk_hits": sorted(shared_risk),
        "divergent_hits": divergent,
        "degenerate": degenerate,
        "created_at": _now_iso(),
    }
    if save:
        dpath = debates_path(us)
        dpath.parent.mkdir(parents=True, exist_ok=True)
        with dpath.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return report, record
