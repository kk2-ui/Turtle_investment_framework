"""Tests for scripts/downloaders/cninfo.py"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from downloaders.cninfo import (
    CninfoDownloader,
    _REPORT_TYPE_TO_PERIOD_MAP,
    _report_type_to_period,
)


# ====================================================================
# 纯函数测试
# ====================================================================

class TestReportTypeToPeriod:
    def test_annual(self):
        assert _report_type_to_period("年报") == "FY"
        assert _report_type_to_period("annual") == "FY"

    def test_interim(self):
        assert _report_type_to_period("中报") == "H1"
        assert _report_type_to_period("interim") == "H1"

    def test_q1(self):
        assert _report_type_to_period("一季报") == "Q1"
        assert _report_type_to_period("q1") == "Q1"

    def test_q3(self):
        assert _report_type_to_period("三季报") == "Q3"
        assert _report_type_to_period("q3") == "Q3"

    def test_unknown(self):
        assert _report_type_to_period("周报") is None


class TestCleanCninfoText:
    def test_strip_em_tags(self):
        result = CninfoDownloader._clean_cninfo_text(
            "格力电器<em>2024</em>年度报告"
        )
        assert result == "格力电器2024年度报告"

    def test_no_tags(self):
        assert CninfoDownloader._clean_cninfo_text("2024年度报告") == "2024年度报告"


class TestFormatAnnouncementDate:
    def test_millisecond_timestamp(self):
        # 2024-04-15
        ts = 1713139200000
        result = CninfoDownloader._format_announcement_date(ts)
        assert "2024" in result

    def test_date_string(self):
        result = CninfoDownloader._format_announcement_date("2024-04-15")
        assert result == "2024-04-15"

    def test_zero_timestamp(self):
        result = CninfoDownloader._format_announcement_date(0)
        assert result == "0"


class TestIsTitleBlocked:
    def test_abstract_blocked(self):
        assert CninfoDownloader._is_title_blocked("2024年度报告摘要") is True

    def test_english_version_blocked(self):
        assert CninfoDownloader._is_title_blocked("2024年度报告（英文）") is True
        assert CninfoDownloader._is_title_blocked("2024年度报告英文版") is True

    def test_old_amended_blocked(self):
        """更正前 版本应被排除（只保留更正后）"""
        assert CninfoDownloader._is_title_blocked("2024年度报告（更正前）") is True

    def test_esg_blocked(self):
        assert CninfoDownloader._is_title_blocked("2024年度ESG报告") is True

    def test_normal_report_not_blocked(self):
        assert CninfoDownloader._is_title_blocked("2024年度报告") is False
        assert CninfoDownloader._is_title_blocked("格力电器2024年年报") is False

    def test_amended_not_blocked(self):
        """更正（非"更正前"）不应被黑名单排除"""
        assert CninfoDownloader._is_title_blocked("2024年度报告（更正）") is False

    def test_notice_blocked(self):
        """同时包含财报关键词和公告关键词应被排除"""
        assert CninfoDownloader._is_title_blocked(
            "关于发布2024年度报告的提示性公告"
        ) is True

    def test_audit_report_blocked(self):
        assert CninfoDownloader._is_title_blocked("2024年度审计报告") is True


class TestIsAmended:
    def test_amended_correction(self):
        assert CninfoDownloader._is_amended("2024年度报告（更正）") is True

    def test_amended_revision(self):
        assert CninfoDownloader._is_amended("2024年度报告（修订）") is True

    def test_amended_supplement(self):
        assert CninfoDownloader._is_amended("2024年度报告（补充）") is True

    def test_normal_not_amended(self):
        assert CninfoDownloader._is_amended("2024年度报告") is False


class TestInferFiscalYear:
    def test_standard_format(self):
        assert CninfoDownloader._infer_fiscal_year(
            "2024年年度报告", "2025-04-15"
        ) == 2024

    def test_short_format(self):
        assert CninfoDownloader._infer_fiscal_year(
            "2024年年报", "2025-04-15"
        ) == 2024

    def test_chinese_numeral(self):
        """中文数字年份推断"""
        result = CninfoDownloader._infer_fiscal_year(
            "二零二四年度报告", "2025-04-15"
        )
        assert result == 2024

    def test_fallback_to_date(self):
        assert CninfoDownloader._infer_fiscal_year(
            "年度报告", "2024-03-15"
        ) == 2024

    def test_no_match(self):
        assert CninfoDownloader._infer_fiscal_year(
            "公司公告", "2024-03-15"
        ) == 2024  # fallback to date year


class TestPickBestAnnouncement:
    def test_amended_priority(self):
        """修订版本应优先于原始版本"""
        items = [
            {"title": "2024年度报告", "announcement_date": "2025-04-15"},
            {"title": "2024年度报告（更正）", "announcement_date": "2025-06-01"},
        ]
        best = CninfoDownloader._pick_best_announcement(items)
        assert "更正" in best["title"]

    def test_latest_date_when_same_status(self):
        items = [
            {"title": "2024年度报告", "announcement_date": "2025-03-01"},
            {"title": "2024年度报告", "announcement_date": "2025-04-15"},
        ]
        best = CninfoDownloader._pick_best_announcement(items)
        assert best["announcement_date"] == "2025-03-01"  # amended=False 优先，日期早的排前面

    def test_empty_list(self):
        assert CninfoDownloader._pick_best_announcement([]) is None


class TestResolveMarketParams:
    def test_sz_stock(self):
        column, plate = CninfoDownloader._resolve_market_params("000651")
        assert column == "szse"
        assert plate == "sz"

    def test_sh_stock(self):
        column, plate = CninfoDownloader._resolve_market_params("600887")
        assert column == "sse"
        assert plate == "sh"

    def test_star_market(self):
        column, plate = CninfoDownloader._resolve_market_params("688001")
        assert column == "sse"
        assert plate == "sh"


# ====================================================================
# HTTP mock 集成测试
# ====================================================================

MOCK_STOCK_JSON = {
    "stockList": [
        {
            "code": "000651",
            "orgId": "gssz0000651",
            "zwjc": "格力电器",
            "ssrq": "1996-11-18",
        },
        {
            "code": "600887",
            "orgId": "gssh6000887",
            "zwjc": "伊利股份",
        },
    ]
}

MOCK_ANNOUNCEMENTS_RESP = {
    "announcements": [
        {
            "adjunctType": "PDF",
            "adjunctUrl": "/finalpage/2025-04-15/123456789.pdf",
            "announcementTitle": "格力电器2024年年度报告",
            "announcementTime": 1713139200000,
            "secCode": "000651",
            "announcementId": "ann_001",
        },
        {
            "adjunctType": "PDF",
            "adjunctUrl": "/finalpage/2025-04-15/123456789_correct.pdf",
            "announcementTitle": "格力电器2024年年度报告（更正）",
            "announcementTime": 1715731200000,
            "secCode": "000651",
            "announcementId": "ann_002",
        },
        {
            "adjunctType": "PDF",
            "adjunctUrl": "/finalpage/2025-04-15/123456789_abstract.pdf",
            "announcementTitle": "格力电器2024年年度报告摘要",
            "announcementTime": 1713139200000,
            "secCode": "000651",
            "announcementId": "ann_003",
        },
    ],
    "hasMore": False,
}


class TestResolveCompany:
    @patch("downloaders.cninfo.requests.Session.get")
    def test_resolve_sz_stock(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_STOCK_JSON
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        downloader = CninfoDownloader()
        company = downloader.resolve_company("000651")
        assert company["org_id"] == "gssz0000651"
        assert company["company_name"] == "格力电器"
        assert company["column"] == "szse"

    @patch("downloaders.cninfo.requests.Session.get")
    def test_ticker_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_STOCK_JSON
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        downloader = CninfoDownloader()
        with pytest.raises(ValueError):
            downloader.resolve_company("999999")


class TestSearchReport:
    @patch("downloaders.cninfo.requests.Session.get")
    @patch("downloaders.cninfo.requests.Session.post")
    def test_search_annual_report_amended_priority(self, mock_post, mock_get):
        """测试修订版本优先选取"""
        # Mock stock list
        mock_get_resp = MagicMock()
        mock_get_resp.json.return_value = MOCK_STOCK_JSON
        mock_get_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_get_resp

        # Mock announcements query
        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = MOCK_ANNOUNCEMENTS_RESP
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        downloader = CninfoDownloader()
        result = downloader.search_report("000651", 2024, "年报")

        assert result is not None
        assert "更正" in result["title"]
        assert "cninfo.com.cn" in result["url"]

    @patch("downloaders.cninfo.requests.Session.get")
    @patch("downloaders.cninfo.requests.Session.post")
    def test_search_no_results(self, mock_post, mock_get):
        mock_get_resp = MagicMock()
        mock_get_resp.json.return_value = MOCK_STOCK_JSON
        mock_get_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"announcements": [], "hasMore": False}
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        downloader = CninfoDownloader()
        result = downloader.search_report("000651", 2024, "年报")
        assert result is None
