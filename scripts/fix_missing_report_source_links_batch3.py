#!/usr/bin/env python3
import json
import re
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
OUT = WIKI / 'raw/theme-radar/missing-report-source-links-batch3-result.json'
MAPPING = {
    '固态变压器产业研究报告': '固态变压器产业新变化与新格局研究分析',
    '量子科技-研究报告': '量子科技产业投资价值深度分析报告',
    '粉末冶金-研究报告': '粉末冶金产业新变化与新格局深度研究分析报告',
    '空间计算-研究报告': '空间计算产业新格局与供应链分析报告',
    '电力芯片-研究报告': '电力芯片产业新格局与投资机会深度研究报告',
    '电解液-研究报告': '电解液产业深度研究：技术变革重塑产业格局，供应链整合加速龙头崛起',
    '激光雷达-研究报告': '激光雷达产业新变化与新格局深度分析报告',
    '铝合金轮毂-研究报告': '铝合金轮毂产业研究报告：新变化与新格局分析',
    '超级电容-研究报告': '超级电容产业新变化与新格局深度研究报告',
    '碘化锂-研究报告': '碘化锂产业新格局与供应链分析报告',
    '钠电池产业新格局深度研究': '钠电池产业新格局深度研究：2025年产业化元年的投资机遇与供应链重构',
    '海底线缆-研究报告': '海底线缆产业新变化与新格局深度研究报告',
    '封测-研究报告': '封测产业新变化与新格局深度研究报告',
    '硅产业-研究报告': '硅产业新变化和新格局研究分析报告',
    '金刚石钻针-研究报告': '金刚石钻针产业新变化与新格局研究分析报告',
    '电容薄膜-研究报告': '电容薄膜产业新变化与新格局深度研究报告',
    '聚酯树脂产业-研究报告': '聚酯树脂产业新变化和新格局研究分析',
    '玻璃基板-研究报告': '玻璃基板产业新变化和新格局深度研究分析',
    '电子束光刻机-研究报告': '电子束光刻机产业研究报告',
    '导热材料-研究报告': '导热材料产业新变化与新格局研究报告',
    '晶圆代工-研究报告': '晶圆代工产业新变化与新格局深度研究报告',
    '风电-研究报告': '风电产业新格局与供应链深度研究报告',
    '调光膜-研究报告': '调光膜产业新变化与新格局研究报告',
    '骨架膜-研究报告': '骨架膜产业新变化与新格局深度研究报告',
    '量子计算-研究报告': '量子计算产业深度研究：技术路径分化下的产业链重构与投资机会分析',
    '磷酸铁锂产业新变化与新格局研究分析报告': '磷酸铁锂产业新变化与新格局研究分析',
    'AI算力驱动下的MPO光纤连接器产业深度研究报告': 'AI算力驱动下的MPO光纤连接器产业深度研究报告：产业链龙头投资价值解析',
    '光伏玻璃产业新格局深度研究': '光伏玻璃产业新格局深度研究：技术迭代驱动供应链重塑与投资机会分析',
    '高压直流输电（HVDC）产业链深度研究报告': '高压直流输电（HVDC）产业链深度研究报告：产业发展与投资机遇分析',
}


def iter_md_files():
    for sub in ['entities', 'concepts', 'sources']:
        for path in sorted((WIKI / sub).glob('*.md')):
            if '.bak' not in path.name:
                yield path


def replace_links(text):
    counts = {k: 0 for k in MAPPING}
    def repl(match):
        inner = match.group(1)
        if '|' in inner:
            target, display = inner.split('|', 1)
            suffix = '|' + display
        else:
            target, suffix = inner, ''
        if '#' in target:
            base, anchor = target.split('#', 1)
            anchor = '#' + anchor
        else:
            base, anchor = target, ''
        base = base.strip()
        if base not in MAPPING:
            return match.group(0)
        counts[base] += 1
        return f'[[{MAPPING[base]}{anchor}{suffix}]]'
    return re.sub(r'\[\[([^\]\n]+)\]\]', repl, text), {k: v for k, v in counts.items() if v}


def backup(path):
    b = path.with_suffix(path.suffix + '.bak-report-link-batch3')
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')


def main():
    changed_files = []
    total_counts = {}
    for path in iter_md_files():
        text = path.read_text(encoding='utf-8')
        new_text, counts = replace_links(text)
        if new_text == text:
            continue
        backup(path)
        path.write_text(new_text, encoding='utf-8')
        changed_files.append(str(path.relative_to(WIKI)))
        for k, v in counts.items():
            total_counts[k] = total_counts.get(k, 0) + v
    result = {'mapping_size': len(MAPPING), 'changed_file_count': len(changed_files), 'changed_files': changed_files, 'replacement_counts': total_counts, 'total_replacements': sum(total_counts.values())}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
