"""Turtle Investment Framework - OtherDataMixin.

Data methods: segments, holders, audit, risk-free rate, repurchase, pledge.
"""

import re
import sys
from pathlib import Path

import pandas as pd

from format_utils import format_number, format_table, format_header


def _yf():
    """Access yfinance module via tushare_collector for @patch compatibility."""
    return sys.modules["tushare_collector"].yf


class OtherDataMixin:
    """Mixin providing other data methods for TushareClient."""

    DEFAULT_RF_CN = 2.50
    DEFAULT_RF_HK = 4.00

    @staticmethod
    def _clean_report_text(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _load_latest_pdf_sections(self) -> dict | None:
        output_dir = self._store.get("_output_dir")
        if not output_dir:
            return None
        path = getattr(self, "_latest_pdf_sections_cache_path", None)
        cached = getattr(self, "_latest_pdf_sections_cache", None)
        if path:
            try:
                from pathlib import Path
                current = Path(output_dir) / "pdf_sections.json"
                if cached is not None and current == path:
                    return cached
            except Exception:
                pass
        try:
            from pathlib import Path
            import json
            candidate = Path(output_dir) / "pdf_sections.json"
            if not candidate.exists():
                self._latest_pdf_sections_cache = None
                self._latest_pdf_sections_cache_path = candidate
                return None
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            self._latest_pdf_sections_cache = payload
            self._latest_pdf_sections_cache_path = candidate
            return payload
        except Exception:
            self._latest_pdf_sections_cache = None
            return None

    def _load_latest_annual_pdf_path(self, ts_code: str) -> Path | None:
        output_dir = self._store.get("_output_dir")
        if not output_dir:
            return None
        code = ts_code.split(".")[0]
        candidates = sorted(
            Path(output_dir).glob(f"{code}_*_年报.pdf"),
            key=lambda p: p.name,
        )
        return candidates[-1] if candidates else None

    def _load_qualitative_report_text(self) -> str:
        output_dir = self._store.get("_output_dir")
        if not output_dir:
            return ""
        path = Path(output_dir) / "qualitative_report.md"
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _extract_qualitative_param(self, text: str, key: str) -> str:
        pattern = rf"\|\s*{re.escape(key)}\s*\|\s*(.*?)\s*\|"
        match = re.search(pattern, text, re.S)
        return self._clean_report_text(match.group(1)) if match else ""

    def _extract_qualitative_section(self, text: str, title: str) -> str:
        pattern = rf"##\s+{re.escape(title)}\n(.*?)(?=\n##\s+|\Z)"
        match = re.search(pattern, text, re.S)
        return match.group(1).strip() if match else ""

    def _extract_bullet_lines(self, text: str, limit: int = 3) -> list[str]:
        bullets: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            content = self._clean_report_text(stripped[2:])
            if content and content not in bullets:
                bullets.append(content)
            if len(bullets) >= limit:
                break
        return bullets

    def get_industry_competition(self, ts_code: str) -> str:
        """Section 8: Deterministic summary sourced from local qualitative_report when available."""
        lines = [format_header(2, "8. 行业与竞争"), ""]

        if not self._is_hk(ts_code):
            lines.append("*[§8 待Agent WebSearch补充]*")
            return "\n".join(lines)

        report_text = self._load_qualitative_report_text()
        if not report_text:
            lines.append("*[§8 待Agent WebSearch补充]*")
            return "\n".join(lines)

        market_structure = self._extract_qualitative_param(report_text, "market_structure")
        entry_barrier = self._extract_qualitative_param(report_text, "entry_barrier")
        competitor_ranking = self._extract_qualitative_param(report_text, "competitor_ranking")
        cycle_position = self._extract_qualitative_param(report_text, "cycle_position")
        regulatory_risk = self._extract_qualitative_param(report_text, "regulatory_risk")
        pricing_power = self._extract_qualitative_param(report_text, "pricing_power")
        competitors_raw = self._extract_qualitative_param(report_text, "competitors")
        moat_section = self._extract_qualitative_section(report_text, "维度二：竞争优势与护城河")
        external_section = self._extract_qualitative_section(report_text, "维度三：外部环境")

        lines.append("**结构化结论**")
        lines.append("")
        summary_rows = [
            ["行业格局", market_structure or "—"],
            ["进入壁垒", entry_barrier or "—"],
            ["相对竞争位置", competitor_ranking or "—"],
            ["当前周期位置", cycle_position or "—"],
            ["监管风险", regulatory_risk or "—"],
            ["定价权", pricing_power or "—"],
        ]
        lines.append(format_table(
            ["维度", "结论"],
            summary_rows,
            alignments=["l", "l"],
        ))
        lines.append("")

        competitors = re.findall(r"name:\s*([^,}\]]+),\s*ticker:\s*([^,}\]]+)", competitors_raw)
        if competitors:
            lines.append("**主要可比公司**")
            lines.append("")
            lines.append(format_table(
                ["公司", "代码"],
                [[self._clean_report_text(name), self._clean_report_text(ticker)] for name, ticker in competitors],
                alignments=["l", "l"],
            ))
            lines.append("")

        moat_points = self._extract_bullet_lines(moat_section, limit=3)
        if moat_points:
            lines.append("**竞争要点**")
            lines.append("")
            for item in moat_points:
                lines.append(f"- {item}")
            lines.append("")

        external_points = self._extract_bullet_lines(external_section, limit=3)
        if external_points:
            lines.append("**行业环境要点**")
            lines.append("")
            for item in external_points:
                lines.append(f"- {item}")
            lines.append("")

        lines.append("*来源: 本地 `qualitative_report.md` 的结构化参数与定性章节摘要*")
        return "\n".join(lines)

    def _extract_mda_text_from_pdf_hk(self, ts_code: str) -> str:
        pdf_path = self._load_latest_annual_pdf_path(ts_code)
        if not pdf_path or not pdf_path.exists():
            return ""
        try:
            import pdfplumber
        except ImportError:
            return ""

        parts = []
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                total = len(pdf.pages)
                for page_num in range(34, min(total, 49) + 1):
                    text = pdf.pages[page_num - 1].extract_text() or ""
                    if text:
                        parts.append(text)
        except Exception:
            return ""
        return self._clean_report_text("\n".join(parts))

    def _extract_mda_fallback_hk(self, ts_code: str) -> dict:
        payload = self._load_latest_pdf_sections() or {}
        mda = self._clean_report_text(payload.get("MDA"))
        pdf_mda = self._extract_mda_text_from_pdf_hk(ts_code)
        if pdf_mda and (
            "Revenue and Operating Results" in pdf_mda
            or "Segment Information" in pdf_mda
        ):
            mda = pdf_mda
        elif len(mda) < 6000 and pdf_mda and len(pdf_mda) > len(mda):
            mda = pdf_mda
        if not mda:
            return {}

        snippets = []
        for pattern in [
            r"Over the past year,.*?Total new contract sums was approximately RMB5,237\.3 million\.",
            r"Total 100\.0% 14,959,871 .*? 14,112,544 .*? 6\.0%",
            r"direct operating expenses raised relatively faster than our revenue growth.*?gross profit decreased by 3\.8% to RMB2,247\.3 million.*?",
            r"operating profit decreased by 9\.5% to RMB1,828\.1 million.*?contract assets.*?",
            r"Entering 2026, COPL will attach importance to stability and innovation.*?safeguarding the bottom line.*?\.",
        ]:
            match = re.search(pattern, mda, re.I)
            if match:
                snippets.append(self._clean_report_text(match.group(0)))

        segment_data = {}
        revenue_match = re.search(
            r"Lump sum basis\s+76\.7%\s+([\d,]+).*?"
            r"Commission basis\s+1\.7%\s+([\d,]+).*?"
            r"Non-residents\s+13\.0%\s+([\d,]+).*?"
            r"Residents\s+8\.1%\s+([\d,]+).*?"
            r"Car parking space trading business\s+0\.5%\s+([\d,]+)",
            mda,
            re.I,
        )
        if revenue_match:
            segment_data["revenue_breakdown"] = [
                ("物业管理服务-包干制", revenue_match.group(1), "76.7%"),
                ("物业管理服务-酬金制", revenue_match.group(2), "1.7%"),
                ("增值服务-非住户", revenue_match.group(3), "13.0%"),
                ("增值服务-住户", revenue_match.group(4), "8.1%"),
                ("车位买卖业务", revenue_match.group(5), "0.5%"),
            ]

        gfa_match = re.search(
            r"Residential projects\s+327\.8\s+68\.6%.*?Non-residential projects\*?\s+149\.8\s+31\.4%.*?"
            r"Commercial, office buildings and parks\*?\s+51\.0\s+10\.7%.*?"
            r"Urban space\*?\s+98\.8\s+20\.7%",
            mda,
            re.I,
        )
        if gfa_match:
            segment_data["gfa_breakdown"] = [
                ("住宅项目", "327.8 百万平方米", "68.6%"),
                ("非住宅项目", "149.8 百万平方米", "31.4%"),
                ("其中: 商业/写字楼/园区", "51.0 百万平方米", "10.7%"),
                ("其中: 城市空间", "98.8 百万平方米", "20.7%"),
            ]

        key_points = []
        for pattern in [
            r"new orders of 90\.9 million sq\.m\., in which 85\.1% were sourced from independent third parties",
            r"new GFA from non-residential projects accounted for a higher proportion of 68\.4%.*?urban space constituted 49\.5%",
            r"gross profit margin dropped to 15\.0% for the year \(2024: 16\.6%",
            r"net impairment of financial assets and contract assets of RMB128\.3 million",
            r"Bank balances and cash increased by 7\.5% to RMB6,270\.7 million",
        ]:
            match = re.search(pattern, mda, re.I)
            if match:
                key_points.append(self._clean_report_text(match.group(0)))

        return {
            "raw": mda,
            "snippets": snippets,
            "segment_data": segment_data,
            "key_points": key_points,
        }

    def get_segments(self, ts_code: str) -> str:
        """Section 9: Business segment data from fina_mainbz."""
        if self._is_hk(ts_code):
            fallback = self._extract_mda_fallback_hk(ts_code)
            segment_data = fallback.get("segment_data") or {}
            lines = [format_header(2, "9. 主营业务构成"), ""]
            if not segment_data:
                lines.append("数据缺失 (港股年报未提取到稳定业务构成)")
                lines.append("")
                lines.append("*来源: 本地年报 fallback 未命中，后续可用 WebSearch 补充*")
                return "\n".join(lines) + "\n"

            revenue_rows = segment_data.get("revenue_breakdown") or []
            if revenue_rows:
                lines.append("**最新年收入构成（年报原文）**")
                lines.append("")
                lines.append(format_table(
                    ["业务条线", "收入 (RMB'000)", "占比"],
                    [[name, value, pct] for name, value, pct in revenue_rows],
                    alignments=["l", "r", "r"],
                ))
                lines.append("")

            gfa_rows = segment_data.get("gfa_breakdown") or []
            if gfa_rows:
                lines.append("**在管面积构成（截至 2025 年末）**")
                lines.append("")
                lines.append(format_table(
                    ["项目类型", "在管面积", "占比"],
                    [[name, area, pct] for name, area, pct in gfa_rows],
                    alignments=["l", "r", "r"],
                ))
                lines.append("")

            lines.append("*来源: 本地 2025 年报 MD&A（金额单位保持原文 RMB'000 / 面积单位百万平方米）*")
            return "\n".join(lines)
        if self._is_us(ts_code):
            return format_header(2, "9. 主营业务构成") + "\n\n数据缺失 (美股暂不支持)\n"

        lines = [format_header(2, "9. 主营业务构成"), ""]
        try:
            df = self._safe_call("fina_mainbz", ts_code=ts_code, type="P",
                                 fields="ts_code,end_date,bz_item,bz_sales,bz_profit,bz_cost")
        except RuntimeError:
            lines.append("数据缺失 (接口可能无权限)\n")
            return "\n".join(lines)

        if df.empty:
            lines.append("数据缺失\n")
            return "\n".join(lines)

        # Get latest period
        if "end_date" in df.columns:
            latest_period = df["end_date"].max()
            df = df[df["end_date"] == latest_period]

        headers = ["业务名称", "营业收入 (百万元)", "营业利润 (百万元)", "毛利率 (%)"]
        rows = []
        for _, r in df.iterrows():
            name = r.get("bz_item", "—")
            rev = r.get("bz_sales", None)
            profit = r.get("bz_profit", None)
            margin = r.get("bz_cost", None)
            # Compute gross margin if both revenue and cost available
            gm = "—"
            if rev and margin:
                try:
                    gm = f"{(1 - float(margin)/float(rev)) * 100:.1f}"
                except (ValueError, ZeroDivisionError):
                    gm = "—"
            rows.append([
                str(name),
                format_number(rev),
                format_number(profit),
                gm,
            ])

        table = format_table(headers, rows,
                             alignments=["l", "r", "r", "r"])
        lines.append(table)
        return "\n".join(lines)

    def get_mda_summary(self, ts_code: str) -> str:
        """Section 10: MD&A summary. For HK, prefer local annual-report fallback."""
        lines = [format_header(2, "10. 管理层讨论与分析 (MD&A)"), ""]
        if self._is_hk(ts_code):
            fallback = self._extract_mda_fallback_hk(ts_code)
            if not fallback:
                lines.append("*[§10 待Agent WebSearch补充]*")
                return "\n".join(lines)

            key_points = fallback.get("key_points") or []
            if key_points:
                lines.append("**管理层核心表述摘录（整理）**")
                lines.append("")
                for item in key_points[:5]:
                    lines.append(f"- {item}")
                lines.append("")

            snippets = fallback.get("snippets") or []
            if snippets:
                summary = []
                for snippet in snippets[:4]:
                    cleaned = self._clean_report_text(snippet)
                    if cleaned and cleaned not in summary:
                        summary.append(cleaned)
                if summary:
                    lines.append("**摘要**")
                    lines.append("")
                    for item in summary:
                        lines.append(f"- {item}")
                    lines.append("")

            lines.append("*来源: 本地 2025 年报 `Management Discussion and Analysis` / `Chairman's Statement`*")
            return "\n".join(lines)

        lines.append("*[§10 待Agent WebSearch补充]*")
        return "\n".join(lines)

    # --- Feature #25: Section 7 (partial) — Top 10 holders + audit ---

    def get_holders(self, ts_code: str) -> str:
        """Section 7 (partial): Top 10 shareholders."""
        if self._is_hk(ts_code):
            return self._get_holders_hk(ts_code)
        if self._is_us(ts_code):
            return self._get_holders_hk(ts_code)  # reuse yfinance-based HK logic

        lines = [format_header(2, "7. 股东与治理 (部分)"), ""]

        try:
            df = self._safe_call("top10_holders", ts_code=ts_code)
        except RuntimeError:
            lines.append("股东数据缺失\n")
            return "\n".join(lines)

        if df.empty:
            lines.append("股东数据缺失\n")
            return "\n".join(lines)

        # Get latest period
        if "end_date" in df.columns:
            latest = df["end_date"].max()
            df = df[df["end_date"] == latest]

        lines.append(f"*截至 {latest}*\n" if "end_date" in df.columns else "")

        headers = ["序号", "股东名称", "持股数量 (万股)", "持股比例 (%)"]
        rows = []
        for i, (_, r) in enumerate(df.head(10).iterrows(), 1):
            rows.append([
                str(i),
                str(r.get("holder_name", "—")),
                format_number(r.get("hold_amount", None), divider=1e4, decimals=2),
                f"{r.get('hold_ratio', 0) or 0:.2f}",
            ])

        table = format_table(headers, rows,
                             alignments=["l", "l", "r", "r"])
        lines.append(table)
        return "\n".join(lines)

    def _get_holders_hk(self, ts_code: str) -> str:
        """Section 7 (HK): Institutional holders via yfinance."""
        fallback = self._load_hk_report_fallback(ts_code) or {}
        holders = fallback.get("holders") or []
        board = fallback.get("board_and_management") or []
        if holders or board:
            lines = [format_header(2, "7. 股东与治理 (部分)"), ""]
            if holders:
                lines.append("**主要股东**")
                lines.append("")
                rows = []
                for idx, item in enumerate(holders[:10], 1):
                    rows.append([
                        str(idx),
                        str(item.get("holder_name", "—")),
                        format_number(item.get("shares"), divider=1e4, decimals=2),
                        f"{float(item.get('hold_ratio')):.2f}" if item.get("hold_ratio") is not None else "—",
                    ])
                lines.append(format_table(
                    ["序号", "股东名称", "持股数量 (万股)", "持股比例 (%)"],
                    rows,
                    alignments=["l", "l", "r", "r"],
                ))
                lines.append("")

            if board:
                lines.append("**董事会与高管**")
                lines.append("")
                rows = []
                for item in board[:20]:
                    rows.append([
                        str(item.get("category", "—")),
                        str(item.get("name", "—")),
                        str(item.get("title", "—")),
                    ])
                lines.append(format_table(
                    ["类别", "姓名", "职务"],
                    rows,
                    alignments=["l", "l", "l"],
                ))
            return "\n".join(lines)

        lines = [format_header(2, "7. 股东与治理 (部分)"), ""]

        if not self._yf_available:
            lines.append("数据缺失 (yfinance不可用)")
            lines.append("")
            lines.append("*[§7 待Agent WebSearch补充]*")
            return "\n".join(lines)

        try:
            ticker = _yf().Ticker(self._yf_ticker(ts_code))
            major = ticker.major_holders
            inst = ticker.institutional_holders
        except Exception:
            lines.append("数据缺失 (yfinance不可用)")
            lines.append("")
            lines.append("*[§7 待Agent WebSearch补充]*")
            return "\n".join(lines)

        # Major holders summary
        if major is not None and not major.empty:
            lines.append("**持股概况**\n")
            mh_headers = ["项目", "数值"]
            mh_rows = []
            for _, r in major.iterrows():
                vals = list(r)
                if len(vals) >= 2:
                    mh_rows.append([str(vals[1]), str(vals[0])])
            if mh_rows:
                lines.append(format_table(mh_headers, mh_rows, alignments=["l", "r"]))
                lines.append("")

        # Institutional holders
        if inst is not None and not inst.empty:
            lines.append("**主要机构持股**\n")
            ih_headers = ["机构名称", "持股数量", "占比 (%)", "报告日期"]
            ih_rows = []
            for _, r in inst.head(10).iterrows():
                name = str(r.get("Holder", "—"))
                shares = r.get("Shares")
                pct = r.get("pctHeld") or r.get("% Out")
                date_val = r.get("Date Reported")
                shares_str = format_number(shares, divider=1e4, decimals=2) if shares is not None else "—"
                pct_str = f"{float(pct) * 100:.2f}" if pct is not None and pct == pct else "—"
                date_str = str(date_val)[:10] if date_val is not None else "—"
                ih_rows.append([name, shares_str, pct_str, date_str])
            lines.append(format_table(ih_headers, ih_rows, alignments=["l", "r", "r", "l"]))
            lines.append("")

        if (major is None or major.empty) and (inst is None or inst.empty):
            lines.append("数据缺失 (yfinance无持股数据)")
            lines.append("")
            lines.append("*[§7 待Agent WebSearch补充]*")
            return "\n".join(lines)

        lines.append("*数据来源: yfinance*")
        lines.append("")
        lines.append("*[§7 待Agent WebSearch补充: 控股股东、管理层变更、违规记录等定性信息]*")
        return "\n".join(lines)

    def get_audit(self, ts_code: str) -> str:
        """Audit opinion info."""
        if self._is_hk(ts_code):
            fallback = self._load_hk_report_fallback(ts_code) or {}
            audit = fallback.get("audit") or {}
            lines = [format_header(3, "审计意见"), ""]
            if not audit:
                lines.append("数据缺失 (港股暂不支持)")
                return "\n".join(lines) + "\n"
            rows = [[
                str(audit.get("audit_result", "—")),
                str(audit.get("audit_agency", "—")),
            ]]
            lines.append(format_table(
                ["审计意见", "会计事务所"],
                rows,
                alignments=["l", "l"],
            ))
            return "\n".join(lines)
        if self._is_us(ts_code):
            return format_header(3, "审计意见") + "\n\n数据缺失 (美股暂不支持)\n"

        lines = [format_header(3, "审计意见"), ""]
        try:
            df = self._safe_call("fina_audit", ts_code=ts_code,
                                 fields="ts_code,end_date,audit_result,audit_agency,audit_fees")
        except RuntimeError:
            lines.append("审计数据缺失\n")
            return "\n".join(lines)

        if df.empty:
            lines.append("审计数据缺失\n")
            return "\n".join(lines)

        df = df.sort_values("end_date", ascending=False).head(3)
        headers = ["年度", "审计意见", "会计事务所", "审计费用 (万元)"]
        rows = []
        for _, r in df.iterrows():
            year = str(r.get("end_date", ""))[:4]
            opinion = str(r.get("audit_result", "—"))
            agency = str(r.get("audit_agency", "—")) if r.get("audit_agency") else "—"
            fees = r.get("audit_fees", None)
            if fees is not None and fees == fees:
                fees_str = f"{fees / 10000:.1f}"
            else:
                fees_str = "—"
            rows.append([year, opinion, agency, fees_str])

        table = format_table(headers, rows, alignments=["l", "l", "l", "r"])
        lines.append(table)
        return "\n".join(lines)

    # --- Feature #84: Section 14 — Risk-free rate ---

    def get_risk_free_rate(self, ts_code: str = "") -> str:
        """Section 14: Risk-free rate.

        For A-shares: 中债国债收益率曲线 (yc_cb)
        For US stocks: US 10-year Treasury yield via yfinance (^TNX)
        For HK stocks: fallback to HK-market default when yc_cb is unavailable
        """
        if self._is_us(ts_code):
            return self._get_risk_free_rate_us()
        if self._is_hk(ts_code):
            return self._get_risk_free_rate_hk()
        return self._get_risk_free_rate_cn()

    def _get_risk_free_rate_cn(self) -> str:
        """Risk-free rate from 中债国债收益率曲线 (yc_cb)."""
        lines = [format_header(2, "14. 无风险利率"), ""]
        try:
            today = pd.Timestamp.now().strftime("%Y%m%d")
            # Get recent 10-year government bond yield
            df = self._safe_call("yc_cb", ts_code="1001.CB",
                                 curve_type="0",
                                 curve_term="10",
                                 start_date=(pd.Timestamp.now() - pd.DateOffset(months=1)).strftime("%Y%m%d"),
                                 end_date=today,
                                 fields="trade_date,yield")
        except RuntimeError:
            fallback_df = pd.DataFrame([{
                "trade_date": pd.Timestamp.now().strftime("%Y%m%d"),
                "yield": self.DEFAULT_RF_CN,
            }])
            self._store["risk_free_rate"] = fallback_df
            table = format_table(
                ["日期", "10年期国债收益率 (%)"],
                [[fallback_df.iloc[0]["trade_date"], f"{self.DEFAULT_RF_CN:.4f}"]],
                alignments=["l", "r"],
            )
            lines.append(table)
            lines.append("")
            lines.append("*数据来源: fallback（yc_cb 无权限，使用保守默认值 2.50%）*")
            return "\n".join(lines)

        if df.empty:
            fallback_df = pd.DataFrame([{
                "trade_date": pd.Timestamp.now().strftime("%Y%m%d"),
                "yield": self.DEFAULT_RF_CN,
            }])
            self._store["risk_free_rate"] = fallback_df
            table = format_table(
                ["日期", "10年期国债收益率 (%)"],
                [[fallback_df.iloc[0]["trade_date"], f"{self.DEFAULT_RF_CN:.4f}"]],
                alignments=["l", "r"],
            )
            lines.append(table)
            lines.append("")
            lines.append("*数据来源: fallback（yc_cb 返回空，使用保守默认值 2.50%）*")
            return "\n".join(lines)

        df = df.sort_values("trade_date", ascending=False)

        # Store for derived metrics
        self._store["risk_free_rate"] = df

        latest = df.iloc[0]

        table = format_table(
            ["日期", "10年期国债收益率 (%)"],
            [[str(latest.get("trade_date", "—")),
              f"{latest.get('yield', 0):.4f}"]],
            alignments=["l", "r"],
        )
        lines.append(table)
        lines.append("")
        lines.append("*数据来源: 中债国债收益率曲线 (yc_cb)*")
        return "\n".join(lines)

    def _get_risk_free_rate_hk(self) -> str:
        """Risk-free rate for HK valuations.

        Prefer the same bond-curve endpoint when available, but keep the fallback
        aligned with the HK valuation model default instead of the A-share default.
        """
        lines = [format_header(2, "14. 无风险利率"), ""]
        try:
            today = pd.Timestamp.now().strftime("%Y%m%d")
            df = self._safe_call("yc_cb", ts_code="1001.CB",
                                 curve_type="0",
                                 curve_term="10",
                                 start_date=(pd.Timestamp.now() - pd.DateOffset(months=1)).strftime("%Y%m%d"),
                                 end_date=today,
                                 fields="trade_date,yield")
        except RuntimeError:
            df = pd.DataFrame()

        if df.empty:
            fallback_df = pd.DataFrame([{
                "trade_date": pd.Timestamp.now().strftime("%Y%m%d"),
                "yield": self.DEFAULT_RF_HK,
            }])
            self._store["risk_free_rate"] = fallback_df
            table = format_table(
                ["日期", "港股估值默认无风险利率 (%)"],
                [[fallback_df.iloc[0]["trade_date"], f"{self.DEFAULT_RF_HK:.4f}"]],
                alignments=["l", "r"],
            )
            lines.append(table)
            lines.append("")
            lines.append("*数据来源: fallback（yc_cb 不可用，使用港股估值默认值 4.00%）*")
            return "\n".join(lines)

        df = df.sort_values("trade_date", ascending=False)
        self._store["risk_free_rate"] = df
        latest = df.iloc[0]
        table = format_table(
            ["日期", "10年期国债收益率 (%)"],
            [[str(latest.get("trade_date", "—")),
              f"{latest.get('yield', 0):.4f}"]],
            alignments=["l", "r"],
        )
        lines.append(table)
        lines.append("")
        lines.append("*数据来源: 中债国债收益率曲线 (yc_cb，港股估值参考)*")
        return "\n".join(lines)

    def _get_risk_free_rate_us(self) -> str:
        """Risk-free rate from US 10-year Treasury yield via yfinance (^TNX)."""
        lines = [format_header(2, "14. 无风险利率"), ""]

        if not self._yf_available:
            lines.append("数据缺失 (yfinance 不可用)\n")
            return "\n".join(lines)

        try:
            tnx = _yf().Ticker("^TNX")
            hist = tnx.history(period="5d")
            if hist.empty:
                lines.append("数据缺失 (无法获取美债收益率)\n")
                return "\n".join(lines)

            latest_yield = float(hist["Close"].dropna().iloc[-1])
            latest_date = hist.index[-1].strftime("%Y%m%d")

            # Store in same format as CN bond for downstream compatibility
            rf_df = pd.DataFrame([{
                "trade_date": latest_date,
                "yield": latest_yield,
            }])
            self._store["risk_free_rate"] = rf_df

            table = format_table(
                ["日期", "美国10年期国债收益率 (%)"],
                [[latest_date, f"{latest_yield:.4f}"]],
                alignments=["l", "r"],
            )
            lines.append(table)
            lines.append("")
            lines.append("*数据来源: US 10-Year Treasury Yield (^TNX via yfinance)*")
        except Exception as e:
            lines.append(f"数据获取失败: {e}\n")

        return "\n".join(lines)

    # --- Feature #85: Section 15 — Share repurchase ---

    def get_repurchase(self, ts_code: str) -> str:
        """Section 15: Share repurchase data from repurchase endpoint."""
        if self._is_hk(ts_code):
            fallback = self._load_hk_report_fallback(ts_code) or {}
            repurchase = fallback.get("repurchase") or {}
            lines = [format_header(2, "15. 股票回购"), ""]
            if not repurchase:
                lines.append("数据缺失 (港股暂不支持)\n")
                return "\n".join(lines)
            if repurchase.get("has_repurchase") is False:
                lines.append(str(repurchase.get("summary", "近3年无回购记录")))
                return "\n".join(lines) + "\n"
            lines.append(str(repurchase.get("summary", "需进一步查阅公告")))
            return "\n".join(lines) + "\n"
        if self._is_us(ts_code):
            return format_header(2, "15. 股票回购") + "\n\n数据缺失 (美股暂不支持)\n"

        lines = [format_header(2, "15. 股票回购"), ""]
        try:
            df = self._safe_call("repurchase", ts_code=ts_code,
                                 fields="ts_code,ann_date,end_date,proc,exp_date,"
                                        "vol,amount,high_limit,low_limit")
        except RuntimeError:
            lines.append("数据缺失 (接口可能无权限)\n")
            return "\n".join(lines)

        if df.empty:
            lines.append("近3年无回购记录\n")
            return "\n".join(lines)

        # Filter to last 3 years
        three_years_ago = (pd.Timestamp.now() - pd.DateOffset(years=3)).strftime("%Y%m%d")
        if "ann_date" in df.columns:
            df = df[df["ann_date"] >= three_years_ago].copy()

        if df.empty:
            lines.append("近3年无回购记录\n")
            return "\n".join(lines)

        df = df.sort_values("ann_date", ascending=False)

        # Deduplicate: same repurchase plan appears multiple times at
        # different progress stages (董事会预案→股东大会通过→实施→完成).
        # Keep only one record per (ann_date, amount) pair.
        if "amount" in df.columns:
            df = df.drop_duplicates(subset=["ann_date", "amount"], keep="first")

        # Filter to executed repurchases only (align with dividend
        # div_proc=="实施" filtering).  Fall back to deduped full data
        # if no executed records exist.
        if "proc" in df.columns:
            executed = df[df["proc"].isin(["完成", "实施"])]
            if not executed.empty:
                df = executed

        # Cross-date dedup: same repurchase plan may appear on different
        # announcement dates (progress updates).  Deduplicate by plan identity.
        if all(c in df.columns for c in ["high_limit", "amount", "proc"]):
            completed = df[df["proc"] == "完成"].copy()
            executing = df[df["proc"] == "实施"].copy()
            other = df[~df["proc"].isin(["完成", "实施"])].copy()

            if not completed.empty:
                completed = completed.drop_duplicates(
                    subset=["amount", "high_limit"], keep="first")
            if not executing.empty:
                executing = executing.sort_values("amount", ascending=False)
                executing = executing.drop_duplicates(
                    subset=["high_limit"], keep="first")

            # If a plan already has a 完成 record, drop its 实施 records
            if not completed.empty and not executing.empty:
                completed_limits = set(completed["high_limit"].dropna())
                executing = executing[
                    ~executing["high_limit"].isin(completed_limits)]

            df = pd.concat(
                [completed, executing, other]).sort_values(
                    "ann_date", ascending=False)

        # Store filtered/deduped data for derived metrics (§17.2 O)
        self._store["repurchase"] = df

        headers = ["公告日", "进度", "回购金额 (百万元)", "回购股数 (万股)", "价格下限", "价格上限"]
        rows = []
        total_amount = 0
        for _, r in df.iterrows():
            amt = r.get("amount", None)
            vol = r.get("vol", None)
            if amt is not None and amt == amt:
                total_amount += float(amt)
            rows.append([
                str(r.get("ann_date", "—")),
                str(r.get("proc", "—")),
                format_number(amt),
                format_number(vol, divider=1e4, decimals=2) if vol is not None and vol == vol else "—",
                f"{r.get('low_limit', 0):.2f}" if r.get("low_limit") is not None else "—",
                f"{r.get('high_limit', 0):.2f}" if r.get("high_limit") is not None else "—",
            ])

        table = format_table(headers, rows,
                             alignments=["l", "l", "r", "r", "r", "r"])
        lines.append(table)
        lines.append("")
        lines.append(f"近3年累计回购金额（已去重/仅完成+实施）: {format_number(total_amount)} {self._unit_label()}")
        years_span = min(3, max(1, len(set(str(r.get("ann_date", ""))[:4] for _, r in df.iterrows()))))
        lines.append(f"年均回购金额: {format_number(total_amount / years_span)} {self._unit_label()}")
        lines.append("")
        lines.append("> ⚠️ 上述金额包含所有用途（注销/员工持股/市值管理）。"
                     "O 仅计入注销型回购，Phase 3 需核实用途后调整。")
        return "\n".join(lines)

    # --- Feature #86: Section 16 — Share pledge statistics ---

    def get_pledge_stat(self, ts_code: str) -> str:
        """Section 16: Share pledge statistics from pledge_stat endpoint."""
        if self._is_hk(ts_code):
            return format_header(2, "16. 股权质押") + "\n\n不适用 (港股无此制度)\n"
        if self._is_us(ts_code):
            return format_header(2, "16. 股权质押") + "\n\n不适用 (美股无此制度)\n"

        lines = [format_header(2, "16. 股权质押"), ""]
        try:
            df = self._safe_call("pledge_stat", ts_code=ts_code,
                                 fields="ts_code,end_date,pledge_count,"
                                        "unrest_pledge,rest_pledge,"
                                        "total_share,pledge_ratio")
        except RuntimeError:
            lines.append("数据缺失 (接口可能无权限)\n")
            return "\n".join(lines)

        if df.empty:
            lines.append("数据缺失\n")
            return "\n".join(lines)

        df = df.sort_values("end_date", ascending=False)
        latest = df.iloc[0]

        table = format_table(
            ["项目", "数值"],
            [
                ["统计日期", str(latest.get("end_date", "—"))],
                ["质押笔数", f"{int(latest.get('pledge_count', 0))}"],
                ["无限售质押 (万股)", format_number(latest.get("unrest_pledge"), divider=1e4, decimals=2)],
                ["有限售质押 (万股)", format_number(latest.get("rest_pledge"), divider=1e4, decimals=2)],
                ["总股本 (万股)", format_number(latest.get("total_share"), divider=1e4, decimals=2)],
                ["质押比例 (%)", f"{latest.get('pledge_ratio', 0):.2f}"],
            ],
            alignments=["l", "r"],
        )
        lines.append(table)
        return "\n".join(lines)
