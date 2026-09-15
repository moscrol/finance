"""题材生命周期钦定词表（G-04）：两套模块细词 → 一套 canonical 阶段词。

背景（2026-09-05 gap roadmap G-04 / 终局 spec §13.2 F3）：仓内长期并存两套题材阶段词——
``theme_lifecycle.py`` 八阶段（证据词 × 市场结构相位的当日**诊断**）与
``theme_lifecycle_timeline.py`` 七段（纯盘面逐日行的历史**回放**）。跨模块联立时只能靠
「引用必须标模块」的人肉纪律，``opinion_stage.THEME_STAGE_COARSE``（tsc-v0）为错位标记
维护了一份双表粗序映射。本模块把映射收成唯一事实源，纪律退出。

钦定：**canonical 词表取七段时间线词**（酝酿 / 首发 / 发酵 / 主升 / 分歧 / 退潮 / 回流）。
理由：(a) 终局 spec（09-05 §4）引用的就是这套；(b) 它由库内逐日行确定性派生、任意历史
区间可重放，符合「换模型能重算」的代码化判据；(c) 八阶段的叙事判读（奖励谁 / 抛弃谁）
是框架层内容，保留在各自模块的细词与 guidance 里，不做数据词表。

映射语义（依据两模块自身的判定条件，非另行发明；与 tsc-v0 粗序逐词兼容）：

===============  ========  =====================================================
八阶段细词        canonical  依据
===============  ========  =====================================================
新出现            酝酿       判定是「图谱/知识库未登记的市场新词」，纯证据侧、
                            不查盘面首板——没有盘面确认时不声称「首发」
旧逻辑唤醒        酝酿       新一轮生命周期的证据侧起点；「回流」要求盘面已再现
                            双红，唤醒不含该确认（tsc-v0 亦作 early，映回流会矛盾）
升温验证          发酵       升温 = 硬证据跟进 / 主升相无硬证据；发酵 = 双红确认，
                            同为中段确认期
加速定价          主升       直接对应（主升相 + 硬证据）
高位分歧          分歧       直接对应（趋势分歧相）
二阶段回流        回流       直接对应
衰退观察          退潮       直接对应（衰退词 / 高位兑现相）
证伪退出          退潮       时间线无证伪段——证伪是证据事实，盘面可观测位置是
                            退潮；证伪语义由细词与 signals 保留，不丢
===============  ========  =====================================================

「无法判定」不在映射表内：:func:`to_canonical` 返回 ``None``，表示不在生命周期序上。

**本模块只放常量与纯函数，零依赖**（theme_lifecycle / timeline / opinion_stage 都会
import 它，不得反向 import 任何 services 模块）。

尚未做（见交接 feat-theme-stage-vocab-g04）：canonical 阶段入旁路库标签与
``LABEL_VERSION`` 升版、prompt / 渲染层切词——两者都等人工对照集裁定
（``scripts/theme_stage_concordance.py``）之后，不抢跑。
"""

from __future__ import annotations

VOCAB_VERSION = "tsv-v1"

STAGE_INCUBATION = "酝酿"
STAGE_FIRST_MOVE = "首发"
STAGE_FERMENT = "发酵"
STAGE_MAIN_UP = "主升"
STAGE_DIVERGENCE = "分歧"
STAGE_EBB = "退潮"
STAGE_REFLOW = "回流"

CANONICAL_STAGES: tuple[str, ...] = (
    STAGE_INCUBATION,
    STAGE_FIRST_MOVE,
    STAGE_FERMENT,
    STAGE_MAIN_UP,
    STAGE_DIVERGENCE,
    STAGE_EBB,
    STAGE_REFLOW,
)

# 粗序：错位标记（opinion_stage.dislocation）用的三档。证伪 / 无法判定不在序上。
CANONICAL_COARSE: dict[str, str] = {
    STAGE_INCUBATION: "early",
    STAGE_FIRST_MOVE: "early",
    STAGE_FERMENT: "mid",
    STAGE_MAIN_UP: "late",
    STAGE_DIVERGENCE: "late",
    STAGE_EBB: "late",
    STAGE_REFLOW: "late",
}

MODULE_DIAGNOSIS = "theme_lifecycle"
MODULE_TIMELINE = "theme_lifecycle_timeline"

TO_CANONICAL: dict[str, dict[str, str]] = {
    MODULE_DIAGNOSIS: {
        "新出现": STAGE_INCUBATION,
        "旧逻辑唤醒": STAGE_INCUBATION,
        "升温验证": STAGE_FERMENT,
        "加速定价": STAGE_MAIN_UP,
        "高位分歧": STAGE_DIVERGENCE,
        "二阶段回流": STAGE_REFLOW,
        "衰退观察": STAGE_EBB,
        "证伪退出": STAGE_EBB,
    },
    MODULE_TIMELINE: {stage: stage for stage in CANONICAL_STAGES},
}


def to_canonical(stage: str | None, module: str) -> str | None:
    """模块细词 → canonical 词。未知模块抛错（fail-closed）；细词不在表内（含「无法判定」、
    ``None``）返回 ``None``——不在生命周期序上，调用方自行决定 unknown 语义，不猜。"""
    mapping = TO_CANONICAL.get(module)
    if mapping is None:
        raise ValueError(f"未知题材模块 {module!r}，可选 {sorted(TO_CANONICAL)}")
    if stage is None:
        return None
    return mapping.get(stage)


def coarse_of(canonical_stage: str | None) -> str | None:
    """canonical 词 → early / mid / late 三档粗序；不在序上返回 ``None``。"""
    if canonical_stage is None:
        return None
    return CANONICAL_COARSE.get(canonical_stage)


def module_coarse_tables() -> dict[str, dict[str, str]]:
    """按模块生成「细词 → 粗序」双表，形状与 tsc-v0 的 ``THEME_STAGE_COARSE`` 相同。

    tsc-v0 是手工维护的双表；本函数把它变成 canonical 映射的派生物（细词 → canonical →
    粗序两步合成），行为逐字节不变（测试 ``test_theme_stage_vocab.py`` 以 tsc-v0 字面表
    为冻结对照锁死）。opinion_stage 引用它，不再自持第二份映射。
    """
    return {
        module: {
            stage: CANONICAL_COARSE[canonical]
            for stage, canonical in mapping.items()
        }
        for module, mapping in TO_CANONICAL.items()
    }
