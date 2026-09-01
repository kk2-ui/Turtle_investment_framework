#!/usr/bin/env python3
"""
Final cleanup: remove template scaffolding markers.
"""
import re
import os

BASE = "/Users/xiami/workspace/analy/Turtle_investment_framework/output/00816_金茂服务"
OUTPUT_FILE = os.path.join(BASE, "金茂服务_00816HK_分析报告_v7_final.md")

with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

original_len = len(content)

# Remove [TABLE] markers
content = re.sub(r'\[TABLE\]', '', content)

# Remove empty brackets []
content = re.sub(r'\[\]', '', content)

# Remove array index markers in brackets like [0-7], [3], [7] where they are standalone
# These are table template remnants
content = re.sub(r'\[0-7\]', '', content)

# Fix [reason] and [score] in Chinese
content = content.replace('[理由]', '理由')
content = content.replace('[评分]', '评分')
content = content.replace('[说明]', '说明')

# Remove [pass/fail] scaffolding
content = content.replace('[pass/fail]', '--')

# Remove standalone [x] markers (not in table rows)
content = re.sub(r'(?<!\d)\[x\](?!\d)', '', content)

# Clean up [0], [1], [3], [4], [5], [7] in table scaffolding
# Only when they are the entire cell content
content = re.sub(r'\| \[(\d)\] \|', r'| \1 |', content)
content = re.sub(r'\| \[(\d)\]', r'| \1', content)

# Fix multiple consecutive blank lines
content = re.sub(r'\n{3,}', '\n\n', content)

# Fix leading/trailing whitespace
content = content.strip() + '\n'

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

lines = content.split('\n')
print(f"Final output: {len(lines)} lines")
print(f"Removed {original_len - len(content)} chars of scaffolding")

# Remaining bracket types
brackets = re.findall(r'\[([^\]]{1,30})\]', content)
unique = sorted(set(brackets))
print(f"Remaining unique bracket types: {len(unique)}")
for b in unique:
    c = content.count(f'[{b}]')
    if c > 1:
        print(f"  {c}x  [{b}]")

# Key stats
q_count = content.count('[?')
print(f"\nRemaining [?]: {q_count}")
