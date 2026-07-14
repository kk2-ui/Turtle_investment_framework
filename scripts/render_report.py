#!/usr/bin/env python3
"""render_report.py — V10：多格式报告渲染模块。

支持将分析报告 Markdown 转换为：
- HTML（增强 CSS，暗色模式，KPI 卡片）
- PDF（Pandoc → HTML → Chrome Headless）
- Word (.docx)（Pandoc + reference.docx）

从 Dayu 的 render/render.py 裁剪而来。
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any


def render_to_html(
    md_path: str,
    output_path: str | None = None,
    report_meta: dict[str, Any] | None = None,
) -> str:
    """将 Markdown 报告渲染为增强 HTML。

    Args:
        md_path: Markdown 文件路径。
        output_path: 输出 HTML 路径（默认与 md 同目录同名 .html）。
        report_meta: 报告元信息（title, code, date 等）。

    Returns:
        输出文件路径。
    """
    if output_path is None:
        output_path = md_path.replace(".md", ".html")

    with open(md_path, encoding="utf-8") as f:
        md_content = f.read()

    # 尝试使用 Pandoc 转换
    html_body = _pandoc_md_to_html(md_content)

    # 包装为完整 HTML
    title = (report_meta or {}).get("title", "龟龟投资策略 · 分析报告")
    full_html = _wrap_html(html_body, title)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    return output_path


def render_to_pdf(
    md_path: str,
    output_path: str | None = None,
) -> str:
    """将 Markdown 报告渲染为 PDF。

    使用 Pandoc 将 Markdown → HTML，再用 Chrome Headless 打印为 PDF。

    Args:
        md_path: Markdown 文件路径。
        output_path: 输出 PDF 路径。

    Returns:
        输出文件路径。

    Raises:
        RuntimeError: 当 Pandoc 或 Chrome 不可用时。
    """
    if output_path is None:
        output_path = md_path.replace(".md", ".pdf")

    # Step 1: Markdown → HTML
    html_path = md_path.replace(".md", "_print.html")
    render_to_html(md_path, html_path)

    # Step 2: HTML → PDF via Chrome
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome", "chromium", "chromium-browser",
    ]
    chrome = None
    for p in chrome_paths:
        if os.path.exists(p) or subprocess.call(["which", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            chrome = p
            break

    if chrome:
        try:
            subprocess.run([
                chrome, "--headless", "--disable-gpu",
                f"--print-to-pdf={output_path}",
                f"file://{os.path.abspath(html_path)}",
            ], check=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    # Fallback: Pandoc direct to PDF
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        try:
            subprocess.run([
                "pandoc", md_path, "-o", output_path,
                "--pdf-engine=xelatex", "-V", "CJKmainfont=Songti SC",
            ], check=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            raise RuntimeError(f"无法生成 PDF。请安装 Pandoc 和 Chrome/XeLaTeX。")

    # 清理中间文件
    if os.path.exists(html_path):
        os.remove(html_path)

    return output_path


def render_to_docx(
    md_path: str,
    output_path: str | None = None,
) -> str:
    """将 Markdown 报告渲染为 Word 文档。

    Args:
        md_path: Markdown 文件路径。
        output_path: 输出 .docx 路径。

    Returns:
        输出文件路径。

    Raises:
        RuntimeError: 当 Pandoc 不可用时。
    """
    if output_path is None:
        output_path = md_path.replace(".md", ".docx")

    try:
        subprocess.run(["pandoc", md_path, "-o", output_path], check=True, timeout=30)
    except FileNotFoundError:
        raise RuntimeError("Pandoc 不可用。请安装 Pandoc: brew install pandoc")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Pandoc 转换失败: {e}")

    return output_path


def _pandoc_md_to_html(md_content: str) -> str:
    """使用 Pandoc 将 Markdown 转换为 HTML。

    Args:
        md_content: Markdown 文本。

    Returns:
        HTML 正文。
    """
    try:
        result = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "html", "--no-highlight"],
            input=md_content, capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            html = result.stdout
            # V12: Pandoc 输出也包 section + 去 <hr> → section 分隔
            html = html.replace("<hr />", "</section>\n<section>")
            if "<section>" not in html:
                html = "<section>\n" + html + "\n</section>"
            return html
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: 简单 Markdown → HTML 转换
    return _simple_md_to_html(md_content)


def _simple_md_to_html(md: str) -> str:
    """增强 Markdown → HTML 转换。去掉 --- 横线，表格包 card 容器。"""
    import re

    html = md

    # 去掉 --- 分隔线（用 section 间距替代）
    html = re.sub(r"\n---\n", "\n</section>\n<section>\n", html)

    # 标题
    html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # 加粗 / 斜体
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # 代码块
    html = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", html, flags=re.DOTALL)
    # 行内代码
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # 表格组：连续的表格行包进 <div class="table-card">
    lines = html.split("\n")
    result: list[str] = []
    in_table = False
    table_buf: list[str] = []
    for line in lines:
        stripped = line.strip()
        is_table_line = bool(re.match(r"^\|.+\|$", stripped))
        is_sep = bool(re.match(r"^\|[-: |]+\|$", stripped))

        if is_table_line:
            if not in_table:
                in_table = True
                table_buf = ['<div class="table-card"><table>']
            # 跳过分隔行
            if not is_sep:
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                tag = "th" if (in_table and len(table_buf) <= 2) else "td"
                row = "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
                table_buf.append(row)
        else:
            if in_table:
                table_buf.append("</table></div>")
                result.extend(table_buf)
                table_buf = []
                in_table = False
            result.append(line)

    if in_table:
        table_buf.append("</table></div>")
        result.extend(table_buf)

    html = "\n".join(result)

    # 列表项
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    # 连续 <li> 包 <ul>
    html = re.sub(r"(<li>.*?</li>\n?)+", r"<ul>\g<0></ul>", html)

    # 段落：非 HTML 标签开头的连续文本
    paragraphs = html.split("\n\n")
    out: list[str] = []
    for p in paragraphs:
        s = p.strip()
        if not s:
            continue
        if s.startswith("<"):
            out.append(s)
        else:
            out.append(f"<p>{s}</p>")
    html = "\n".join(out)

    # 确保所有 <section> 正确闭合，未闭合的自动补全
    open_sections = html.count("<section>") - html.count("</section>")
    if open_sections > 0:
        html += "\n</section>" * open_sections
    # 确保至少有一个 section 包裹
    if "<section>" not in html:
        html = "<section>\n" + html + "\n</section>"

    return html


def _wrap_html(body: str, title: str) -> str:
    """将 HTML 正文包装为完整 HTML 页面，含增强 CSS。

    Args:
        body: HTML 正文。
        title: 页面标题。

    Returns:
        完整 HTML 字符串。
    """
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --bg: #fffff8;
    --text: #333333;
    --text-light: #666666;
    --heading: #1a1a1a;
    --border: #e0d8cc;
    --accent: #8b0000;
    --accent-light: #faf5f0;
    --link: #8b0000;
    --code-bg: #f8f5f0;
    --table-stripe: #faf7f2;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #1c1c1a;
      --text: #d4d0c8;
      --text-light: #999588;
      --heading: #e8e4d8;
      --border: #3d3830;
      --accent: #c77d4d;
      --accent-light: #2a2420;
      --link: #c77d4d;
      --code-bg: #252320;
      --table-stripe: #22201c;
    }}
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: "Charter", "Georgia", "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "PingFang SC", serif;
    max-width: 780px;
    margin: 0 auto;
    padding: 3em 2em 6em 2em;
    background: var(--bg);
    color: var(--text);
    line-height: 1.8;
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
  }}

  h1 {{
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 1.8em;
    font-weight: 700;
    color: var(--heading);
    text-align: center;
    margin-bottom: 0.3em;
    letter-spacing: 0.02em;
  }}

  h2 {{
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 1.2em;
    font-weight: 700;
    color: var(--heading);
    margin: 2.5em 0 0.8em 0;
    padding-bottom: 0.4em;
    border-bottom: 1px solid var(--border);
  }}

  h3 {{
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 1.05em;
    font-weight: 600;
    color: var(--heading);
    margin: 1.5em 0 0.5em 0;
  }}

  h4 {{
    font-size: 1em;
    font-weight: 600;
    color: var(--text-light);
    margin: 1.2em 0 0.3em 0;
  }}

  p {{ margin: 0.6em 0; text-align: justify; }}

  ul, ol {{ margin: 0.5em 0 0.5em 1.8em; }}
  li {{ margin: 0.25em 0; }}

  strong {{ color: var(--heading); }}

  blockquote {{
    margin: 1em 0;
    padding: 0.6em 1.2em;
    border-left: 3px solid var(--accent);
    background: var(--accent-light);
    color: var(--text-light);
    font-size: 0.95em;
  }}

  /* 表格 — 保留框线，经典风格 */
  .table-card {{
    margin: 1.2em 0;
    overflow-x: auto;
  }}

  table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 0.9em;
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  }}

  thead {{ border-bottom: 2px solid var(--heading); }}

  th {{
    font-weight: 600;
    padding: 8px 14px 6px 14px;
    text-align: left;
    color: var(--heading);
    white-space: nowrap;
    font-size: 0.88em;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }}

  td {{
    padding: 7px 14px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}

  tr:last-child td {{ border-bottom: none; }}
  tr:nth-child(even) td {{ background: var(--table-stripe); }}

  code {{
    background: var(--code-bg);
    padding: 1px 5px;
    border-radius: 2px;
    font-size: 0.9em;
    font-family: "SF Mono", "Consolas", monospace;
  }}

  pre {{
    background: var(--code-bg);
    padding: 1em;
    overflow-x: auto;
    margin: 0.8em 0;
    font-size: 0.88em;
    line-height: 1.5;
  }}
  pre code {{ background: none; padding: 0; }}

  hr {{
    border: none;
    text-align: center;
    margin: 2em 0;
    color: var(--border);
  }}
  hr::after {{
    content: "···";
    letter-spacing: 0.6em;
    color: var(--border);
  }}

  /* 打印 */
  @media print {{
    body {{ max-width: none; font-size: 11pt; padding: 0; }}
    h2 {{ page-break-before: always; }}
    .table-card {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="V10 多格式报告渲染")
    ap.add_argument("input", help="Markdown 报告文件路径")
    ap.add_argument("--format", "-f", choices=["html", "pdf", "docx"], default="html", help="输出格式")
    ap.add_argument("--output", "-o", help="输出文件路径")
    ap.add_argument("--title", help="报告标题")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    meta = {"title": args.title or "龟龟投资策略 · 分析报告"}

    try:
        if args.format == "html":
            out = render_to_html(args.input, args.output, meta)
        elif args.format == "pdf":
            out = render_to_pdf(args.input, args.output)
        elif args.format == "docx":
            out = render_to_docx(args.input, args.output)
        else:
            print(f"ERROR: 不支持的格式 {args.format}", file=sys.stderr)
            sys.exit(1)
        print(f"✅ 渲染完成: {out}")
    except Exception as e:
        print(f"❌ 渲染失败: {e}", file=sys.stderr)
        sys.exit(1)
