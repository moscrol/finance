#!/usr/bin/env python3
"""列出知识库里还没做 DeepDive 的 concept 和个股（entity_type=上市公司）。

判定「已有 DeepDive」（任一命中即算已做）：
- 页面正文/frontmatter 出现 DeepDive/Deep Dive/深挖；
- wiki/sources 里存在标题含该页面名、且命中深挖类命名的源文件
  （DeepDive/深挖/IMA canonical/研究报告/深度研究/信息池/题材地图）；
- 个股：entity 页含 IMA 逻辑卡标记（「IMA 最新逻辑跟踪」/「最新逻辑卡」/「IMA stock logic」）；
- 同义词：页面本名或任一别名（aliases.json + frontmatter aliases）命中即算。

概念清单额外输出「疑似重叠」列：与已做概念名称有 >=2 字重合的，列出供人工跳过，
不自动剔除（语义近义无法程序确认）。

增量模式：--state <json>。首跑写入全量清单快照；之后再跑只输出上次快照后
新增的缺口（新建页面 or 从「已有」变回「缺口」不会发生，只看新增页面），
并把快照滚动更新。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DD_RE = re.compile(r"deep[\s_-]?dive|深挖", re.IGNORECASE)
IMA_STOCK_RE = re.compile(r"IMA 最新逻辑跟踪|最新逻辑卡|IMA stock logic")
DD_SOURCE_RE = re.compile(
    r"deep[\s_-]?dive|深挖|IMA canonical|研究报告|深度研究|信息池|题材地图", re.IGNORECASE
)


def _covered_by_sources(sources_dir: Path) -> list[str]:
    return [p.stem for p in sources_dir.glob("*.md") if DD_SOURCE_RE.search(p.stem)]


def _alias_map(aliases_path: Path) -> dict[str, set[str]]:
    canon_to_aliases: dict[str, set[str]] = {}
    if aliases_path.exists():
        data = json.loads(aliases_path.read_text(encoding="utf-8"))
        for alias, canonical in (data.get("aliases") or {}).items():
            canon_to_aliases.setdefault(str(canonical), set()).add(str(alias))
    return canon_to_aliases


FM_FIELD = re.compile(r"^([a-z_]+):\s*(.*)$")


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        match = FM_FIELD.match(line.strip())
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def _hierarchy(graph_path: Path) -> tuple[set[str], set[str]]:
    parents: set[str] = set()
    children: set[str] = set()
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        hier = ("is_subconcept_of", "子领域", "细分", "belongs_to", "题材雷达子方向", "子方向", "子工艺")
        for rel in graph.get("relations", []):
            rel_type = str(rel.get("type") or "")
            if rel_type in hier or rel_type.startswith("上位"):
                children.add(str(rel.get("from") or ""))
                parents.add(str(rel.get("to") or ""))
    return parents, children


def _scan(
    dir_path: Path,
    require_listed: bool,
    main_filter: tuple[set[str], set[str]] | None = None,
    dd_source_titles: list[str] | None = None,
    alias_map: dict[str, set[str]] | None = None,
    covered_names: set[str] | None = None,
) -> list[dict[str, str]]:
    rows = []
    for page in sorted(dir_path.glob("*.md")):
        text = page.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        if require_listed and "上市公司" not in fm.get("entity_type", ""):
            continue
        if DD_RE.search(text) or (require_listed and IMA_STOCK_RE.search(text)):
            if covered_names is not None:
                covered_names.add(page.stem)
            continue
        names = {page.stem}
        if alias_map:
            names |= alias_map.get(page.stem, set())
        fm_aliases = fm.get("aliases", "")
        names |= {a.strip().strip(chr(34)).strip(chr(39)) for a in fm_aliases.strip("[]").split(",") if a.strip()}
        names = {n for n in names if len(n) >= 2}
        if dd_source_titles and any(n in title for title in dd_source_titles for n in names):
            if covered_names is not None:
                covered_names.add(page.stem)
            continue
        if main_filter is not None:
            parents, children = main_filter
            name = page.stem
            n_tickers = len(re.findall(r"\d{6}", fm.get("tickers", "")))
            is_main = name in parents or (name not in children and n_tickers >= 3)
            if not is_main:
                continue
        rows.append(
            {
                "name": page.stem,
                "tickers": fm.get("tickers", ""),
                "updated": fm.get("updated", ""),
                "revision": fm.get("revision", ""),
            }
        )
    rows.sort(key=lambda r: (r["updated"], r["revision"]), reverse=True)
    return rows


# 粒度对齐 agent-daily / theme-radar 的 canonical_concept（盘面题材级）：
# 盘面题材级概念保留为缺口；真近义/子集判定已覆盖（SEMANTIC_COVERED）；
# 更宽的行业伞概念单独剔除（UMBRELLA_EXCLUDED）。
# 语义判定：缺口概念 -> 已做深挖的同族概念（仅限真近义/子集，视为已覆盖）
SEMANTIC_COVERED: dict[str, str] = {
    "利基存储": "存储芯片 / HBM与国产存储",
    "AI存储": "存储芯片 / HBM与国产存储",
    "DRAM": "存储芯片 / HBM与国产存储",
    "HAMR": "磁电存储",
    "半导体设备材料": "半导体设备零部件 / 半导体",
    "CoWoS": "先进封装",
    "半导体封装": "先进封装 / 封测",
    "半导体先进制造": "半导体 / 晶圆代工",
    "半导体工艺": "半导体 / 晶圆代工 / 光刻",
    "半导体国产替代": "国产替代 / 半导体",
    "第三代半导体": "碳化硅 / 氮化镓",
    "AI芯片": "AI算力芯片 / ASIC芯片",
    "AI终端": "AI端侧 / AI手机",
    "AI BOX（车载算力终端）": "车载终端",
    "金刚石散热": "钻石散热",
    "TGV（玻璃通孔技术）": "玻璃基板",
    "被动元件": "被动器件",
    "PCB油墨": "PCB / PCB钻孔耗材",
    "PCB微钻": "PCB钻针 / PCB钻孔耗材",
    "光伏钨丝": "光伏 / 光伏新技术",
    "动力煤": "煤炭",
    "焦煤": "煤炭",
    "煤化工上游": "煤化工",
    "XR空间计算": "AR眼镜 / 空间智能",
    "新能源电池材料": "锂电材料 / 电解液 / 前驱体",
    "油服设备": "油田服务 / 油气装备",
    "数据中心网络": "交换机 / 数据中心",
    "数据中心交换机": "交换机 / 交换芯片",
    "机器人零部件": "机器人减速器 / 关节电机 / 行星滚柱丝杠",
    "5G_6G通信": "6G / 6G产业",
    "激光设备": "激光 / 激光器 / 超快激光",
    "高阶MLCC": "MLCC / MLCC粉体",
    "智能终端": "AI端侧 / AI手机",
}

# 行业伞概念：宽于 agent-daily/theme-radar 的盘面题材粒度，不单独列为缺口；
# 同族盘面题材已有深挖。
UMBRELLA_EXCLUDED: dict[str, str] = {
    "战略金属": "小金属 / 钨钼小金属 / 稀土",
    "化工新材料": "化工 / 硅基新材料",
    "先进制造": "高端装备与自主可控制造 / 增材制造",
    "高端制造": "高端装备与自主可控制造",
    "智能制造": "工业智能制造",
    "高端装备制造": "高端装备与自主可控制造",
    "工业互联网": "工业智能制造 / 工业控制",
    "智能传感器": "力学传感器 / 温度传感器 / 气体传感器 等",
    "海洋工程": "海上油气 / 深海",
    "传统能源": "煤炭 / 油气 / 火电",
    "周期资源": "煤炭 / 有色金属 / 铁矿石",
    "资源品": "煤炭 / 有色金属 / 铁矿石",
    "公用事业": "水电 / 火电 / 电力运营商",
    "农业": "农业科技 / 种业 / 粮食安全",
    "医药": "创新药 / 医药出海",
    "医药生物": "创新药 / 生物制品 / 医药出海",
    "生物医药": "创新药 / 生物制品 / 医药出海",
    "双碳目标": "绿色低碳 / 绿色电力",
    "建材": "节能建材 / 装饰材料 / 耐火材料",
    "数字经济": "数据要素",
    "显示技术": "OLED / MiniLED / LED显示",
    "水泥": "水泥出海",
    "消费": "新消费 / 情绪消费 / 服务消费",
    "环保": "环保服务 / 固废 / 垃圾焚烧",
    "能源转型": "新能源 / 绿色电力 / 储能",
    "贵金属": "黄金 / 白银 / 贵金属回收",
    "电力设备": "新型电力系统 / 特高压 / 数据中心电力设备",
    "养殖": "养殖复苏 / 猪周期",
    "航空航天": "商业航天 / 军机 / 航空发动机",
    "食品饮料": "白酒 / 食品 / 预制菜",
    "品牌出海": "白电品牌出海 / 黑电品牌出海 / 清洁电器品牌出海",
    "新材料": "硅基新材料 / 电子信息材料 等各材料专题",
}


def _lcs_len(a: str, b: str) -> int:
    best = 0
    for i in range(len(a)):
        for j in range(i + best + 1, len(a) + 1):
            if a[i:j] in b:
                best = j - i
            else:
                break
    return best


def _overlap_hints(name: str, covered: set[str], min_len: int = 2, top: int = 3) -> str:
    hits = sorted(
        ((c, _lcs_len(name, c)) for c in covered),
        key=lambda x: -x[1],
    )
    hits = [c for c, l in hits if l >= min_len][:top]
    return " / ".join(hits) if hits else "-"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wiki", default="/Users/a77/knowledge-base-private/wiki")
    ap.add_argument("--out-dir", default="/tmp/deepdive_gaps")
    ap.add_argument("--state", default=None, help="增量模式状态文件；不传则每次全量")
    ap.add_argument(
        "--concept-scope",
        choices=["main", "all"],
        default="main",
        help="main=只列主概念（concept_graph 层级边里的父节点，或非子节点且 tickers>=3）；all=全部",
    )
    args = ap.parse_args()

    wiki = Path(args.wiki)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    main_filter = None
    if args.concept_scope == "main":
        main_filter = _hierarchy(wiki / "relations" / "concept_graph.json")
    dd_source_titles = _covered_by_sources(wiki / "sources")
    alias_map = _alias_map(wiki / "relations" / "aliases.json")
    covered_concepts: set[str] = set()
    concepts = _scan(
        wiki / "concepts",
        require_listed=False,
        main_filter=main_filter,
        dd_source_titles=dd_source_titles,
        alias_map=alias_map,
        covered_names=covered_concepts,
    )
    sem_excluded = [r for r in concepts if r["name"] in SEMANTIC_COVERED]
    umb_excluded = [r for r in concepts if r["name"] in UMBRELLA_EXCLUDED]
    concepts = [
        r
        for r in concepts
        if r["name"] not in SEMANTIC_COVERED and r["name"] not in UMBRELLA_EXCLUDED
    ]
    for row in concepts:
        row["overlap"] = _overlap_hints(row["name"], covered_concepts)
    stocks = _scan(
        wiki / "entities",
        require_listed=True,
        dd_source_titles=dd_source_titles,
        alias_map=alias_map,
    )

    prev: dict[str, list[str]] = {"concepts": [], "stocks": []}
    if args.state and Path(args.state).exists():
        prev = json.loads(Path(args.state).read_text(encoding="utf-8"))

    for label, rows in (("concepts", concepts), ("stocks", stocks)):
        seen = set(prev.get(label) or [])
        emit = [r for r in rows if r["name"] not in seen] if seen else rows
        mode = "增量" if seen else "全量"
        out = out_dir / f"deepdive-gap-{label}.md"
        has_overlap = label == "concepts"
        header = "| 名称 | tickers | updated | revision |"
        sep = "|---|---|---|---|"
        if has_overlap:
            header = "| 名称 | 疑似重叠(已做) | tickers | updated | revision |"
            sep = "|---|---|---|---|---|"
        lines = [
            f"# 待补 DeepDive：{label}（{mode}，共 {len(emit)} 条 / 缺口总数 {len(rows)}）",
            "",
            header,
            sep,
        ]
        for r in emit:
            base = f"| {r['name']} | "
            if has_overlap:
                base += f"{r.get('overlap', '-')} | "
            base += f"{r['tickers'] or '-'} | {r['updated'] or '-'} | {r['revision'] or '-'} |"
            lines.append(base)
        if label == "concepts":
            if sem_excluded:
                lines += [
                    "",
                    f"## 近义/子集判定已覆盖（已剔除 {len(sem_excluded)} 条）",
                    "",
                    "| 名称 | 判定覆盖于（已做深挖） |",
                    "|---|---|",
                ]
                lines += [
                    f"| {r['name']} | {SEMANTIC_COVERED[r['name']]} |" for r in sem_excluded
                ]
            if umb_excluded:
                lines += [
                    "",
                    f"## 行业伞概念，宽于盘面题材粒度（已剔除 {len(umb_excluded)} 条）",
                    "",
                    "| 名称 | 同族已做题材 |",
                    "|---|---|",
                ]
                lines += [
                    f"| {r['name']} | {UMBRELLA_EXCLUDED[r['name']]} |" for r in umb_excluded
                ]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{label}: {mode} {len(emit)} 条 -> {out}")

    if args.state:
        Path(args.state).write_text(
            json.dumps(
                {
                    "concepts": [r["name"] for r in concepts],
                    "stocks": [r["name"] for r in stocks],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
