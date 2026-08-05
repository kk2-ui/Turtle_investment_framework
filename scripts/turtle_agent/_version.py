"""Turtle V13 — 输出布局常量（单一真相来源）。

所有脚本从此处 import，不得再硬编码 "v12" 字符串。

用法::

    from turtle_agent._version import REPORT_VERSION, CHAPTERS_SUBDIR, REPORTS_SUBDIR
"""

# 报告版本标识：v13 = D1（AV入场費深度）+ D2（管理层资本配置闸门）框架
REPORT_VERSION = "v13"

# 股票输出目录下的子目录名称
CHAPTERS_SUBDIR = "chapters"   # _ch00.md … _ch14.md
REPORTS_SUBDIR  = "reports"    # 组装后的 .md / .html 报告
