#!/usr/bin/env python3
import json
import re
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
OUT = WIKI / 'raw/theme-radar/missing-report-source-links-batch1-result.json'
MAPPING = {
    'AI电源产业深度研究': 'AI电源产业深度研究：技术革新驱动供应链重构与投资机遇分析',
    '固态电池产业研究报告': '固态电池产业新格局与供应链深度分析报告',
    '港口航运-研究报告': '港口航运产业新变化与新格局研究分析报告',
    '酒店餐饮-研究报告': '酒店餐饮产业新格局与供应链深度分析报告',
    '短剧-研究报告': '短剧产业新变化和新格局研究分析报告',
    '垃圾发电-研究报告': '垃圾发电产业新变化与新格局研究分析报告',
    '磁悬浮压缩机-研究报告': '磁悬浮压缩机产业深度研究报告：技术革新驱动千亿市场，国产替代迎来黄金窗口期',
    '谷子经济-研究报告': '谷子经济产业新变化与新格局研究分析报告',
    '辅助生殖-研究报告': '辅助生殖产业新格局与投资机会深度研究',
    '火电改造-研究报告': '火电改造产业深度研究：新格局、供应链重构与投资机会分析',
    '电磁弹射-研究报告': '电磁弹射产业新变化与新格局深度分析报告',
    '地下管网-研究报告': '地下管网产业新变化与新格局深度研究报告',
    '混凝土-研究报告': '混凝土产业链深度研究报告：绿色低碳转型与产业链整合重塑竞争格局',
    '超聚变-研究报告': '超聚变产业新格局与供应链深度分析报告',
    '液冷服务器-研究报告': '液冷服务器产业新变化与新格局全面分析报告',
    '大飞机-研究报告': '大飞机产业新变化与新格局全面研究分析报告',
    '灯塔工厂-研究报告': '灯塔工厂产业链投资机会深度研究报告',
    '腱绳材料-研究报告': '腱绳材料产业新变化与新格局深度研究报告',
    '基因检测-研究报告': '基因检测产业新变化和新格局深度研究报告',
    '磷化铟-研究报告': '磷化铟产业新变化与新格局深度研究报告',
    '环氧丙烷-研究报告': '环氧丙烷产业新变化与新格局深度研究报告',
    '海上风电-研究报告': '海上风电产业投资价值分析报告',
    '管道产业-研究报告': '管道产业新变化与新格局深度研究分析报告',
    '轨交设备-研究报告': '轨交设备产业新变化与新格局深度研究报告',
}


def iter_md_files():
    for sub in ['entities', 'concepts', 'sources']:
        base = WIKI / sub
        for path in sorted(base.glob('*.md')):
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
    new_text = re.sub(r'\[\[([^\]\n]+)\]\]', repl, text)
    return new_text, {k: v for k, v in counts.items() if v}


def backup(path):
    b = path.with_suffix(path.suffix + '.bak-report-link-batch1')
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
    result = {'mapping_size': len(MAPPING), 'changed_files': changed_files, 'changed_file_count': len(changed_files), 'replacement_counts': total_counts, 'total_replacements': sum(total_counts.values())}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
