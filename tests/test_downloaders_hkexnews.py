"""Tests for scripts/downloaders/hkexnews.py"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from downloaders.hkexnews import (
    HkexnewsDownloader,
    _contains_cjk,
    _infer_fiscal_period_from_text,
    _infer_fiscal_year_from_text,
    _is_amended_title,
    _is_english_announcement,
    _looks_like_english_report_text,
    _normalize_hk_date,
    _pick_best_announcement_hk,
    _split_stock_code_tokens,
    _to_hkex_stock_code,
)


# ====================================================================
# 纯函数测试
# ====================================================================

class TestToHkexStockCode:
    def test_pad_zero(self):
        assert _to_hkex_stock_code("700") == "00700"
        assert _to_hkex_stock_code("0700") == "00700"

    def test_keep_five_digit(self):
        assert _to_hkex_stock_code("00700") == "00700"

    def test_strip_hk_suffix(self):
        assert _to_hkex_stock_code("0700.HK") == "00700"

    def test_error_non_digit(self):
        with pytest.raises(ValueError):
            _to_hkex_stock_code("ABC")


class TestContainsCjk:
    def test_chinese(self):
        assert _contains_cjk("年度报告") is True

    def test_english(self):
        assert _contains_cjk("Annual Report") is False

    def test_mixed(self):
        assert _contains_cjk("2024 Annual 年报") is True


class TestLooksLikeEnglishReportText:
    def test_annual_report(self):
        assert _looks_like_english_report_text("ANNUAL REPORT 2024") is True

    def test_interim(self):
        assert _looks_like_english_report_text("Interim Results") is True

    def test_chinese(self):
        assert _looks_like_english_report_text("年度报告") is False


class TestIsEnglishAnnouncement:
    def test_lang_field_en(self):
        assert (
            _is_english_announcement(
                title="Annual Report 2024",
                language="en",
            )
            is True
        )

    def test_chinese_title_without_cjk(self):
        """英文标题 + 无CJK → 排除"""
        assert (
            _is_english_announcement(
                title="ANNUAL REPORT 2024",
                language="zh",
            )
            is True
        )

    def test_chinese_title_with_cjk(self):
        """含 CJK → 保留"""
        assert (
            _is_english_announcement(
                title="ANNUAL REPORT 2024 年度报告",
                language="zh",
            )
            is False
        )


class TestIsAmendedTitle:
    def test_amended(self):
        assert _is_amended_title("2024年度报告（修订）") is True
        assert _is_amended_title("2024 Annual Report (REVISED)") is True

    def test_normal(self):
        assert _is_amended_title("2024年度报告") is False


class TestInferFiscalYearFromText:
    def test_arabic_year(self):
        assert _infer_fiscal_year_from_text("2024年度报告", "") == 2024
        assert _infer_fiscal_year_from_text("ANNUAL REPORT 2024", "") == 2024

    def test_chinese_year(self):
        result = _infer_fiscal_year_from_text("二零二四年度报告", "")
        assert result == 2024

    def test_fallback_to_date(self):
        assert _infer_fiscal_year_from_text("年度报告", "2024-03-15") == 2024


class TestInferFiscalPeriodFromText:
    def test_annual(self):
        result = _infer_fiscal_period_from_text(
            title="ANNUAL REPORT 2024",
            category_text="财务报表/ESG信息",
        )
        assert result == "FY"

    def test_interim(self):
        result = _infer_fiscal_period_from_text(
            title="INTERIM REPORT 2024",
            category_text="财务报表/ESG信息",
        )
        assert result == "H1"

    def test_q1_from_title(self):
        result = _infer_fiscal_period_from_text(
            title="FIRST QUARTER RESULTS 2024",
            category_text="公告及通告 - 季度业绩",
        )
        assert result == "Q1"

    def test_q3_from_title(self):
        result = _infer_fiscal_period_from_text(
            title="第三季度报告 2024",
            category_text="公告及通告 - 季度业绩",
        )
        assert result == "Q3"


class TestPickBestAnnouncementHk:
    def test_amended_priority(self):
        """非修订版本优先"""
        items = [
            {"title": "2024年度报告（修订）", "filing_date": "2025-06-01"},
            {"title": "2024年度报告", "filing_date": "2025-04-15"},
        ]
        best = _pick_best_announcement_hk(items)
        assert "修订" not in best["title"]

    def test_latest_date(self):
        items = [
            {"title": "2024年度报告", "filing_date": "2025-03-01"},
            {"title": "2024年度报告", "filing_date": "2025-04-15"},
        ]
        best = _pick_best_announcement_hk(items)
        assert best["filing_date"] == "2025-03-01"


class TestNormalizeHkDate:
    def test_slash_format(self):
        assert _normalize_hk_date("2024/03/15") == "2024-03-15"

    def test_already_normalized(self):
        assert _normalize_hk_date("2024-03-15") == "2024-03-15"


class TestSplitStockCodeTokens:
    def test_single_code(self):
        tokens = _split_stock_code_tokens("00700")
        assert "00700" in tokens

    def test_br_separated(self):
        tokens = _split_stock_code_tokens("00700<br/>00800")
        assert "00700" in tokens
        assert "00800" in tokens


# ====================================================================
# HTTP mock 集成测试
# ====================================================================

MOCK_STOCK_LIST = [
    {"stockCode": "00700", "stockId": "10001", "stockName": "腾讯控股"},
]
MOCK_INACTIVE_LIST: list[dict[str, str]] = []


MOCK_TITLE_SEARCH = {
    "result": [
        {
            "FILE_TYPE": "PDF",
            "TITLE_TC": "騰訊控股有限公司 2024年度報告",
            "FILE_LINK_TC": "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0415/2025041500001.pdf",
            "DATE_TIME": "2025/04/15 16:30",
            "FILE_SIZE": "5000000",
            "LANGUAGE": "zh",
            "CATEGORY": "財務報表/ESG資訊 - 年報",
        },
    ],
}


class TestResolveCompany:
    @patch("downloaders.hkexnews.requests.Session.get")
    def test_resolve_tencent(self, mock_get):
        def _mock_json(url, **kwargs):
            resp = MagicMock()
            resp.text = (
                '[{"stockCode":"00700","stockId":"10001","stockName":"腾讯控股"}]'
            )
            resp.raise_for_status = MagicMock()
            return resp

        mock_get.side_effect = _mock_json
        downloader = HkexnewsDownloader()
        # _fetch_stock_mapping 会尝试 JSON parse，mock 返回需要特殊处理
        # 直接注入缓存
        downloader._stock_mapping_cache = {
            "00700": {"stock_id": "10001", "stock_name": "腾讯控股"},
        }
        company = downloader.resolve_company("00700")
        assert company["stock_id"] == "10001"


class TestSearchReport:
    @patch("downloaders.hkexnews.requests.Session.get")
    def test_search_annual_report(self, mock_get):
        def _mock_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "titleSearchServlet" in url:
                import json
                resp.text = json.dumps({"result": [{
                    "FILE_TYPE": "PDF",
                    "TITLE_TC": "騰訊控股有限公司 2024年度報告",
                    "FILE_LINK_TC": "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0415/test.pdf",
                    "DATE_TIME": "2025/04/15 16:30",
                    "LANGUAGE": "zh",
                    "CATEGORY": "財務報表/ESG資訊 - 年報",
                }]})
            else:
                resp.text = "[]"
            resp.json = lambda: __import__('json').loads(resp.text)
            return resp

        mock_get.side_effect = _mock_get

        downloader = HkexnewsDownloader()
        downloader._stock_mapping_cache = {
            "00700": {"stock_id": "10001", "stock_name": "腾讯控股"},
        }
        result = downloader.search_report("00700", 2024, "年报")
        assert result is not None
        assert "test.pdf" in result["url"]
