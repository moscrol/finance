"""从 raw 全文中提取核心观点和关键数据，更新 wiki/sources/ 摘要页。

对每个 fupanhui 研报：
1. 匹配 source 页和 raw 全文文件
2. 从全文提取执行摘要（标题后到第一个大章节之间）
3. 提取关键数字（市场规模、增速、份额等）
4. 插入 source 页的 frontmatter 之后
"""

import json
import os
import re
import sys

RAW_DIR = os.path.expanduser("~/Desktop/c c/知识库/raw")
SOURCES_DIR = os.path.expanduser("~/Desktop/c c/知识库/wiki/sources")


def extract_insights(full_text):
    """从全文提取核心观点和关键数据。"""
    # 去掉开头的元信息（返回研报库、标签、小表格等）
    # 找到第一个有实质内容的段落
    lines = full_text.split("\n")

    # 找到报告正文的开始：通常是标题行之后的第一段有意义的文字
    # 跳过导航、标签、股票表格等
    content_start = 0
    found_title = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 找到标题后的 "执行摘要" 或第一个章节号
        if not found_title and stripped.startswith("返回研报库"):
            found_title = True
            continue
        if found_title:
            # 跳过标题行、日期、标签、股票相关内容
            if any(skip in stripped for skip in [
                "产业分析", "热门", "小表格", "复制图片",
                "885", "共封装", "芯片概念", "数据中心",
                "6G概念", "军工", "光伏", "储能", "新能源",
                "人工智能", "PCB", "PET", "CPO", "HBM",
                "共 ", "只", "复盘会·原创"
            ]):
                continue
            # 找到第一个长段落（>30字符且不是标签/日期）
            if len(stripped) > 30 and not re.match(r'^\d{4}年\d{1,2}月\d{1,2}日', stripped):
                content_start = i
                break

    if content_start == 0:
        return None, []

    # 提取核心观点：从 content_start 到第一个 "一、" 或 "1." 章节标题
    insight_lines = []
    for i in range(content_start, min(content_start + 80, len(lines))):
        stripped = lines[i].strip()
        # 遇到大章节标题就停
        if re.match(r'^[一二三四五六七八九十]+[、.]', stripped):
            break
        if re.match(r'^\d+\.\s', stripped) and len(stripped) < 20:
            break
        if len(stripped) > 15:  # 只保留有实质内容的行
            insight_lines.append(stripped)

    # 取前 2-3 个最有价值的句子
    core_insight = ""
    if insight_lines:
        # 合并成一段，然后取前 2-3 句
        combined = " ".join(insight_lines)
        sentences = re.split(r'[。！？]', combined)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
        # 取前 3 句
        selected = sentences[:3]
        core_insight = "。".join(selected) + "。" if selected else None

    # 提取关键数字
    key_numbers = []
    # 只在全文前半段搜索（避免数据过多）
    search_text = "\n".join(lines[content_start:content_start + 200])

    patterns = [
        # 市场规模
        (r'(\d+\.?\d*)\s*(万?亿|百?千万?)[美元元人民币].*?(市场|规模|产值|收入)', '市场规模'),
        (r'(市场|规模|产值).*?(\d+\.?\d*)\s*(万?亿|百?千万?)[美元元人民币]', '市场规模'),
        # 增长率
        (r'(\d+\.?\d*)%', '增速/占比'),
        # CAGR
        (r'CAGR\s*(?:为|达|约|超|将)?\s*(\d+\.?\d*)%', 'CAGR'),
        # 市占率
        (r'(市占率|市场份额|占比|渗透率).*?(\d+\.?\d*)%', '占比/渗透率'),
        (r'(\d+\.?\d*)%\s*(市占率|市场份额|占比|渗透率)', '占比/渗透率'),
    ]

    seen_numbers = set()
    number_entries = []

    # 从核心观点段落和前几个章节中提取
    for line in search_text.split("\n"):
        line = line.strip()
        if len(line) < 10:
            continue

        # 提取包含数字的关键句子
        nums = re.findall(r'\d+\.?\d*', line)
        has_percent = '%' in line
        has_currency = any(c in line for c in ['亿', '万', '美元', '元'])

        if (has_percent or has_currency) and len(nums) > 0:
            # 简化句子，只保留关键信息
            short = line
            if len(short) > 120:
                # 截取数字附近的内容
                for match in re.finditer(r'\d+\.?\d*[%亿万千美元]', short):
                    start = max(0, match.start() - 40)
                    end = min(len(short), match.end() + 40)
                    short = "..." + short[start:end] + "..."
                    break

            # 去重
            key = re.sub(r'\s+', '', short[:50])
            if key not in seen_numbers:
                seen_numbers.add(key)
                number_entries.append(short)
                if len(number_entries) >= 8:
                    break

    return core_insight, number_entries


def match_files():
    """匹配 source 页和 raw 全文文件。"""
    raw_files = {}
    for f in os.listdir(RAW_DIR):
        if f.endswith("-full.md"):
            base = f[:- len("-full.md")]
            raw_files[base] = os.path.join(RAW_DIR, f)

    source_files = {}
    for f in os.listdir(SOURCES_DIR):
        if f.endswith(".md"):
            base = f[:-3]  # remove .md
            source_files[base] = os.path.join(SOURCES_DIR, f)

    # Match by base name
    matched = []
    for base in source_files:
        if base in raw_files:
            matched.append((base, source_files[base], raw_files[base]))

    return matched


def update_source(source_path, core_insight, key_numbers):
    """在 source 页中插入核心观点和关键数据。"""
    with open(source_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查是否已经有核心观点段落
    if "## 核心观点" in content:
        return False  # 已经更新过

    # 找到 frontmatter 结束位置
    fm_end = content.find("---", 4)  # 跳过开头的 ---
    if fm_end == -1:
        return False
    fm_end += 3  # 跳过 ---

    # 找到第一个 ## 标题（通常是 产业链）
    first_section = content.find("\n## ", fm_end)
    if first_section == -1:
        first_section = len(content)

    # 构建插入内容
    insert_parts = [""]

    if core_insight:
        insert_parts.append("## 核心观点")
        insert_parts.append("")
        insert_parts.append(core_insight)
        insert_parts.append("")

    if key_numbers:
        insert_parts.append("## 关键数据")
        insert_parts.append("")
        for num in key_numbers:
            insert_parts.append(f"- {num}")
        insert_parts.append("")

    insert_text = "\n".join(insert_parts)

    # 插入到第一个 ## 标题之前
    new_content = content[:first_section] + insert_text + content[first_section:]

    # 更新 revision
    revision_match = re.search(r'revision:\s*(\d+)', new_content)
    if revision_match:
        old_rev = int(revision_match.group(1))
        new_content = new_content.replace(f"revision: {old_rev}", f"revision: {old_rev + 1}")

    # 更新 updated 日期
    import time
    today = time.strftime('%Y-%m-%d')
    new_content = re.sub(r'updated:\s*\d{4}-\d{2}-\d{2}', f'updated: {today}', new_content)

    with open(source_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def main():
    dry_run = "--dry-run" in sys.argv
    matched = match_files()
    print(f"Matched {len(matched)} source-raw pairs")

    updated = 0
    skipped = 0
    no_insight = 0

    for i, (base, source_path, raw_path) in enumerate(matched):
        # Read raw full text
        with open(raw_path, "r", encoding="utf-8") as f:
            full_text = f.read()

        # Extract insights
        core_insight, key_numbers = extract_insights(full_text)

        if not core_insight and not key_numbers:
            no_insight += 1
            if i < 5:
                print(f"  [{i+1}] {base[:40]} -> no insight extracted")
            continue

        if dry_run:
            print(f"  [{i+1}] {base[:40]}")
            if core_insight:
                print(f"       观点: {core_insight[:80]}...")
            if key_numbers:
                print(f"       数据: {len(key_numbers)} items")
            updated += 1
            continue

        ok = update_source(source_path, core_insight, key_numbers)
        if ok:
            updated += 1
        else:
            skipped += 1

        if (i + 1) % 50 == 0:
            print(f"  ... {i+1}/{len(matched)} processed ({updated} updated)")

    print(f"\nDone: {updated} updated, {skipped} skipped (already had), {no_insight} no insight")
    if not dry_run:
        print(f"Location: {SOURCES_DIR}")


if __name__ == "__main__":
    main()
