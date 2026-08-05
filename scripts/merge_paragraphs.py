#!/usr/bin/env python3
"""合并 markdown 中的单句段落为自然段。保留标题/bullet/表格/source/blockquote 结构。"""

import re
import sys


def classify_line(line: str) -> str:
    """分类一行文本的类型。"""
    s = line.strip()
    if not s:
        return "empty"
    if s.startswith("#"):
        return "header"
    if s.startswith("---"):
        return "hr"
    if re.match(r"^[-*]\s", s):
        return "bullet"
    if s.startswith("|"):
        return "table"
    if s.startswith("[source:"):
        return "source"
    if s.startswith(">"):
        return "blockquote"
    if re.match(r"^\*\*.*\*\*[：:]", s):
        return "bold_label"
    if s.startswith("⚠️") or s.startswith("⛔"):
        return "warning"
    if re.match(r"^\d+\.\s", s):
        return "numbered"
    return "body"


def merge_markdown(text: str) -> str:
    """合并单句段落为自然段。"""
    lines = text.split("\n")

    # Step 1: 将文本分组为 blocks（空行分隔）
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "":
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)

    # Step 2: 分类每个 block
    def block_type(block: list[str]) -> str:
        """判断 block 的类型。多行 block 取第一行判断。"""
        if not block:
            return "empty"
        # 检查是否全是 source 行
        if all(classify_line(l) == "source" for l in block):
            return "source"
        return classify_line(block[0])

    # Step 3: 合并连续的 body blocks
    merged: list[list[str]] = []
    i = 0
    while i < len(blocks):
        bt = block_type(blocks[i])

        if bt == "body":
            # 合并连续 body blocks，以及紧跟的 source block
            merged_block = list(blocks[i])
            i += 1
            while i < len(blocks):
                nbt = block_type(blocks[i])
                if nbt == "body":
                    merged_block.extend(blocks[i])
                    i += 1
                elif nbt == "source":
                    # source 附加到合并段落末尾
                    merged_block.extend(blocks[i])
                    i += 1
                    # source 后不继续合并 body（source 是段落结束标记）
                    break
                else:
                    break
            merged.append(merged_block)
        else:
            merged.append(blocks[i])
            i += 1

    # Step 4: 重建文本，在 blocks 之间加空行
    result_lines: list[str] = []
    for block in merged:
        for line in block:
            result_lines.append(line)
        result_lines.append("")  # block 之间的空行

    return "\n".join(result_lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python merge_paragraphs.py <markdown_file>")
        sys.exit(1)

    md_path = sys.argv[1]
    with open(md_path, encoding="utf-8") as f:
        original = f.read()

    merged = merge_markdown(original)

    # 写回
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(merged)

    # 统计
    orig_blocks = len([b for b in original.split("\n\n") if b.strip()])
    merged_blocks = len([b for b in merged.split("\n\n") if b.strip()])
    print(f"原始段落数: {orig_blocks}")
    print(f"合并后段落数: {merged_blocks}")
    print(f"减少: {orig_blocks - merged_blocks} ({((orig_blocks - merged_blocks) / orig_blocks * 100):.0f}%)")
    print(f"已写入: {md_path}")


if __name__ == "__main__":
    main()
