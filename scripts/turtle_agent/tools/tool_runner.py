#!/usr/bin/env python3
"""V12 Tool Runner — 让 Claude Code 通过 Bash 调用 Agent tools。

用法:
    python tool_runner.py list_documents '{"output_dir": "output/01502_金融街物业"}'
    python tool_runner.py write_chapter '{"index": 2, "title": "公司做的是什么生意", "content": "..."}'
"""

import json
import os
import sys

_scripts_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_scripts_dir, "turtle_agent", "tools"))
sys.path.insert(0, os.path.join(_scripts_dir, "turtle_agent"))
sys.path.insert(0, _scripts_dir)

# Import all tool modules
from read_tools import (
    list_documents, read_section, search_report,
    get_financial_statement, get_financial_trends, read_zone_data,
)
from calc_tools import compute_gg, compute_ddm, assess_moat, evaluate_decision
from write_tools import write_chapter, read_chapter, audit_chapter, assemble_report
from phase_tools import (
    run_pre_analysis, download_annual_reports, check_report_completeness,
    compute_bundle_db, extract_pdf_sections, verify_report,
)

TOOLS = {
    # read
    "list_documents": list_documents,
    "read_section": read_section,
    "search_report": search_report,
    "get_financial_statement": get_financial_statement,
    "get_financial_trends": get_financial_trends,
    "read_zone_data": read_zone_data,
    # calc
    "compute_gg": compute_gg,
    "compute_ddm": compute_ddm,
    "assess_moat": assess_moat,
    "evaluate_decision": evaluate_decision,
    # write
    "write_chapter": write_chapter,
    "read_chapter": read_chapter,
    "audit_chapter": audit_chapter,
    "assemble_report": assemble_report,
    # phase
    "run_pre_analysis": run_pre_analysis,
    "download_annual_reports": download_annual_reports,
    "check_report_completeness": check_report_completeness,
    "compute_bundle_db": compute_bundle_db,
    "extract_pdf_sections": extract_pdf_sections,
    "verify_report": verify_report,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Tools: {', '.join(TOOLS.keys())}")
        sys.exit(0)

    tool_name = sys.argv[1]
    if tool_name not in TOOLS:
        print(f"Unknown tool: {tool_name}")
        sys.exit(1)

    args = {}
    if len(sys.argv) > 2:
        args = json.loads(sys.argv[2])

    result = TOOLS[tool_name](**args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
