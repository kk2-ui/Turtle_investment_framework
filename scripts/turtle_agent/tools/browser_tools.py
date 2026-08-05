"""ego-lite 浏览器工具 — Agent 可直接控制真实浏览器搜索和下载。
V12.20: 吸收 ego-lite 作为 Agent 的 web 交互能力。
"""

from __future__ import annotations

import json, os, subprocess, tempfile
from typing import Any


_EGO = "ego-browser"
_MAX_OUTPUT_CHARS = 8000


def _run_ego(script: str, timeout: int = 30) -> dict[str, Any]:
    """运行 ego-browser nodejs 脚本。

    ego-browser 通过 stdin 接收 JS 脚本（相当于 heredoc）。
    """
    try:
        # ego-browser 的 cliLog 在非 TTY 下输出到 stderr，stdout 也可能有内容
        result = subprocess.run(
            [_EGO, "nodejs"],
            input=script, capture_output=True, text=True, timeout=timeout,
        )
        output = ((result.stderr or "") + (result.stdout or "")).strip()
        error = ""
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + "\n...(truncated)"
        return {"ok": result.returncode == 0, "output": output, "error": error}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "", "error": f"Timeout after {timeout}s"}
    except FileNotFoundError:
        return {"ok": False, "output": "", "error": "ego-browser not found. Install: ego-lite"}


def browse_web(url: str = "", search_query: str = "", task_name: str = "turtle-agent") -> dict[str, Any]:
    """打开网页或搜索，返回页面文本内容。

    可用于：搜索年报下载页、查看公司IR页面、获取市场数据。

    Args:
        url: 目标 URL。如果为空则用 search_query 在 cninfo 搜索。
        search_query: 搜索关键词（url 为空时使用）。
        task_name: 任务空间名。
    """
    target = url.strip()
    if not target and search_query.strip():
        target = f"https://www.cninfo.com.cn/new/fulltextSearch?notautosubmit=&keyWord={search_query.strip()}&searchType=0"

    if not target:
        return {"ok": False, "error": "需要 url 或 search_query"}

    script = f"""const task = await useOrCreateTaskSpace('{task_name}')
await openOrReuseTab('{target}', {{ wait: true, timeout: 20 }})
const text = await snapshotText()
cliLog(text)"""

    return _run_ego(script, timeout=30)


def browse_screenshot(url: str = "", selector: str = "", task_name: str = "turtle-agent") -> dict[str, Any]:
    """截取网页截图。用于 Agent 需要看图判断时。

    Args:
        url: 目标 URL。
        selector: CSS 选择器（可选，截取特定元素）。
        task_name: 任务空间名。
    """
    target = url.strip()
    if not target:
        return {"ok": False, "error": "需要 url"}

    scr_path = os.path.join(tempfile.gettempdir(), f"ego_ss_{int(__import__('time').time())}.png")
    script = f"""const task = await useOrCreateTaskSpace('{task_name}')
await openOrReuseTab('{target}', {{ wait: true, timeout: 20 }})
const scr = await captureScreenshot({{ path: '{scr_path}' }})
cliLog(JSON.stringify({{ path: scr.path, w: scr.w, h: scr.h }}))"""

    result = _run_ego(script, timeout=30)
    if result["ok"]:
        try:
            meta = json.loads(result["output"].split("\n")[-1])
            result["screenshot_path"] = meta.get("path", scr_path)
            result["dimensions"] = f"{meta.get('w',0)}x{meta.get('h',0)}"
        except Exception:
            result["screenshot_path"] = scr_path
    return result


def browse_download_report(url: str, save_dir: str, filename: str = "") -> dict[str, Any]:
    """在浏览器中点击 PDF 链接触发下载，保存到本地。

    用于 cninfo API 搜不到年报时，Agent 手动下载。

    Args:
        url: 年报 PDF 直接链接或 cninfo 搜索页 URL。
        save_dir: 本地保存目录。
        filename: 保存文件名（可选，默认从 URL 提取）。
    """
    save_dir = os.path.abspath(save_dir)
    os.makedirs(save_dir, exist_ok=True)
    if not filename:
        filename = url.rsplit("/", 1)[-1].split("?")[0] or "report.pdf"
    save_path = os.path.join(save_dir, filename)

    script = f"""const task = await useOrCreateTaskSpace('turtle-download')
await openOrReuseTab('{url}', {{ wait: true, timeout: 25 }})
// 尝试点击 PDF 链接
const text = await snapshotText()
const pdfLink = text.match(/loc=href:([^\s]+\.pdf)/i)
if (pdfLink) {{
  const fullUrl = pdfLink[1].startsWith('http') ? pdfLink[1] : 'https://static.cninfo.com.cn/' + pdfLink[1]
  cliLog(JSON.stringify({{ pdf_url: fullUrl }}))
  // 模拟点击下载
  await click('loc=href:' + pdfLink[1])
  await wait(3)
}}
cliLog(text.slice(0, 5000))"""

    result = _run_ego(script, timeout=35)
    # 尝试从结果中提取 PDF URL
    try:
        for line in result.get("output", "").split("\n"):
            if "pdf_url" in line:
                data = json.loads(line)
                pdf_url = data.get("pdf_url", "")
                if pdf_url:
                    import requests
                    r = requests.get(pdf_url, headers={
                        "User-Agent": "Mozilla/5.0", "Referer": "https://www.cninfo.com.cn/",
                    }, timeout=30)
                    if r.status_code == 200 and len(r.content) > 10000:
                        with open(save_path, "wb") as f:
                            f.write(r.content)
                        return {"ok": True, "saved_to": save_path, "size_kb": len(r.content)//1024,
                                "method": "direct_download", "pdf_url": pdf_url}
    except Exception:
        pass

    return {"ok": False, "output": result.get("output", "")[:2000],
            "error": result.get("error", ""), "note": "未能自动下载PDF，可能需要手动操作"}


browse_web._tool_meta = {"name": "browse_web", "description": "用真实浏览器打开网页获取内容(搜索年报/公司IR/市场数据)", "parameters": {"url": {"type": "string", "description": "目标URL", "optional": True}, "search_query": {"type": "string", "description": "cninfo搜索关键词(url为空时使用)", "optional": True}}}  # type: ignore[attr-defined]
browse_screenshot._tool_meta = {"name": "browse_screenshot", "description": "截取网页截图供Agent视觉分析", "parameters": {"url": {"type": "string", "description": "目标URL"}, "selector": {"type": "string", "description": "CSS选择器", "optional": True}}}  # type: ignore[attr-defined]
browse_download_report._tool_meta = {"name": "browse_download_report", "description": "通过浏览器手动下载年报PDF(cninfo API失败时备用)", "parameters": {"url": {"type": "string", "description": "PDF链接或cninfo搜索页URL"}, "save_dir": {"type": "string", "description": "保存目录"}, "filename": {"type": "string", "description": "文件名", "optional": True}}}  # type: ignore[attr-defined]
