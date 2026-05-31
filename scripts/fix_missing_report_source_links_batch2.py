#!/usr/bin/env python3
import json
import re
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
OUT = WIKI / 'raw/theme-radar/missing-report-source-links-batch2-result.json'
MAPPING = {
    '季戊四醇-研究报告': '季戊四醇产业新格局深度研究报告：供需失衡驱动价值重估，技术升级重塑竞争格局',
    '磷化工-研究报告': '磷化工产业新变化与新格局深度研究报告',
    '钙钛矿-研究报告': '钙钛矿产业新变化与新格局深度研究报告',
    '控制器-研究报告': '控制器产业新变化与新格局研究报告：产业链重构下的投资机会分析',
    '高速铜连接-研究报告': '高速铜连接产业新变化和新格局研究分析',
    '钌-研究报告': '钌产业新变化与新格局全面研究分析',
    '工业母机-研究报告': '工业母机产业新变化与新格局深度研究报告',
    '电源芯片-研究报告': '电源芯片全面分析需求描述',
    '露营经济-研究报告': '露营经济产业研究报告：产业链重构下的投资机会分析',
    '电子皮肤-研究报告': '电子皮肤产业新变化与新格局深度分析',
    '国产算力-研究报告': '国产算力产业新变化与新格局深度研究报告',
    '电容产业-研究报告': '电容产业新变化与新格局研究报告',
    '铝离子电池-研究报告': '铝离子电池产业新变化与新格局研究分析',
    '灵巧手-研究报告': '灵巧手产业新变化与新格局全面研究分析',
    '金刚石工具-研究报告': '金刚石工具行业深度研究报告',
    '磁电存储-研究报告': '磁电存储产业新变化与新格局研究报告',
    '超充-研究报告': '超充产业新变化与新格局深度研究报告',
    '高速铜缆-研究报告': '高速铜缆产业新变化和新格局深度研究分析报告',
    '车路协同-研究报告': '车路协同产业研究分析报告',
    '电池防火-研究报告': '电池防火产业新变化与新格局深度研究报告',
    '海底电缆-研究报告': '海底电缆产业新变化与新格局全面研究分析报告',
    '磷酸铁锂-研究报告': '磷酸铁锂产业新变化与新格局研究分析',
    '电极箔-研究报告': '电极箔产业新变化和新格局研究分析',
    '动物疫苗产业研究报告': '动物疫苗产业新变化与新格局深度研究报告',
    '复合铜箔-研究报告': '复合铜箔产业新格局与供应链分析报告',
    '绿色电力-研究报告': '绿色电力产业新变化与新格局研究报告',
    '服务器电源-研究报告': '服务器电源产业新变化与新格局深度研究报告',
    '毫米波雷达产业研究报告': '毫米波雷达产业新变化与新格局深度研究报告',
    '鸿蒙-研究报告': '鸿蒙产业新变化与新格局全面分析报告',
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
    b = path.with_suffix(path.suffix + '.bak-report-link-batch2')
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
