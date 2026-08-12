# 六模式提示词词表（统一触发口径）

## 六模式提示词词表（统一触发口径）

用户说出下列提示词时，agent 直接路由到对应模式，不要追问：

| 模式名 | 提示词（任一命中即触发） | 标准入口 |
|---|---|---|
| `brief` | 速览X / 快查X / X是什么 / 题材速读X / 晨汇方向X | `radar.py --term X --vault <知识库>/wiki --mode brief` |
| `front-map` | X信息地图 / X值不值得展开 / X全景图 | `radar.py --term X --vault <知识库>/wiki --mode front-map` |
| `deep-dive` | 深研X / 尽调X / 深拆X / X验证清单 | `radar.py --term X --vault <知识库>/wiki --mode deep-dive` |
| `scan`（知识库模块4） | 扫描表 / 全库扫描 / 工艺材料扫描 | 知识库 `skills/theme-radar-reports/scripts/generate_scan_table.py` |
| `replay`（知识库模块7） | X发酵复盘 / X怎么走到今天 / X时间线 | 知识库 `skills/theme-radar-reports/scripts/generate_fermentation_report.py X` |
| `migrate`（知识库模块8） | 拿X当标尺 / 横迁 / 找X的同类 | 知识库 `skills/theme-radar-reports/scripts/generate_migration_scan.py --pattern X` |

路由原则：带具体题材词 X 且问产业维（是什么/谁受益/怎么验证）→ brief/front-map/deep-dive 三档按深度选；问时间维（怎么发酵的）→ replay；不带题材词、要全库视角 → scan；要类比/找下一个 → migrate。

```bash
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜"
```

题材速读（高可读性，用户日常首选）：

```bash
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "光刻胶" \
  --mode brief
```

`--mode brief` 只输出四个模块，结构固定、可读性优先：

1. `## 一、题材定义`：一句话定锚（优先主概念 wiki 页）+ 核心逻辑 + 相关概念定锚。
2. `## 二、产业链上下游`：产业链树状图 + 按 下游/中游/上游材料/上游设备/配套 分层列出环节、公司和看点。
3. `## 三、工艺与材料细分扫描`：每个细颗粒对象一组（名称｜位置 / 逻辑 / 代表公司），不用宽表。
4. `## 四、各细分核心个股`：按细分方向分组的公司表（公司/分层/wiki 一句话定位），公司集合被前面细分覆盖的重复段自动跳过。

当用户要"题材定义+产业链+细分+核心个股"这种速览需求时，默认用 brief；需要验证清单、护栏、发酵进度等完整拆解时再用 deep-dive / front-map。

带外部定义运行：

```bash
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --definition "感光干膜是PCB、IC载板等图形转移环节使用的光敏材料，和mSAP/高端PCB制程、线路精细化相关。"
```

写入报告：

```bash
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --out "<知识库>/wiki/synthesis/感光干膜-theme-radar.md"
```

