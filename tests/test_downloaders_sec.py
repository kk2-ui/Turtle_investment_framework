"""Tests for scripts/downloaders/sec.py"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from downloaders.sec import (
    SecDownloader,
    _accession_to_no_dash,
    _normalize_ticker,
    _select_primary_from_index_items,
)


# ====================================================================
# 纯函数测试
# ====================================================================

class TestNormalizeTicker:
    def test_simple(self):
        assert _normalize_ticker("aapl") == "AAPL"

    def test_dot_to_dash(self):
        assert _normalize_ticker("brk.b") == "BRK-B"

    def test_already_normalized(self):
        assert _normalize_ticker("BRK-B") == "BRK-B"


class TestAccessionToNoDash:
    def test_standard(self):
        assert (
            _accession_to_no_dash("0000320193-24-000123")
            == "000032019324000123"
        )


class TestSelectPrimaryFromIndexItems:
    def test_match_by_form_type(self):
        items = [
            {"name": "aapl-20240928.htm", "type": "10-K"},
            {"name": "ex-991.htm", "type": "EX-99.1"},
        ]
        result = _select_primary_from_index_items(items, "10-K")
        assert result == "aapl-20240928.htm"

    def test_fallback_to_first_html(self):
        """无 form type 匹配时回退到第一个非 exhibit HTML"""
        items = [
            {"name": "filing-details.xml", "type": "XML"},
            {"name": "aapl-20240928.htm", "type": ""},
        ]
        result = _select_primary_from_index_items(items, "10-K")
        assert result == "aapl-20240928.htm"

    def test_avoid_ex_files(self):
        """优先避免 ex* 文件"""
        items = [
            {"name": "ex-991.htm", "type": "EX-99.1"},
            {"name": "primary.htm", "type": ""},
        ]
        result = _select_primary_from_index_items(items, "10-K")
        assert result == "primary.htm"


# ====================================================================
# SecDownloader 初始化测试
# ====================================================================

class TestSecDownloaderInit:
    def test_default_user_agent_rejected(self):
        with pytest.raises(ValueError, match="User-Agent"):
            SecDownloader(user_agent="DayuAgent/1.0 unconfigured@example.com")

    def test_custom_user_agent_accepted(self):
        downloader = SecDownloader(user_agent="Test/1.0 test@example.com")
        assert downloader._user_agent == "Test/1.0 test@example.com"


# ====================================================================
# HTTP mock 集成测试
# ====================================================================

MOCK_COMPANY_TICKERS = {
    "0": {"cik_str": "320193", "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": "789019", "ticker": "MSFT", "title": "Microsoft Corp"},
}

MOCK_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "8-K"],
            "filingDate": ["2024-11-01", "2024-05-01", "2024-03-15"],
            "accessionNumber": [
                "0000320193-24-000123",
                "0000320193-24-000089",
                "0000320193-24-000045",
            ],
            "primaryDocument": [
                "aapl-20240928_10k.htm",
                "aapl-20240330_10q.htm",
                "aapl-20240315_8k.htm",
            ],
            "reportDate": ["2024-09-28", "2024-03-30", ""],
            "cik": ["320193", "320193", "320193"],
        }
    }
}

MOCK_INDEX_JSON = {
    "directory": {
        "item": [
            {"name": "aapl-20240928_10k.htm", "type": "10-K",
             "last-modified": "2024-11-01", "size": "15000000"},
            {"name": "ex-991.htm", "type": "EX-99.1",
             "last-modified": "2024-11-01", "size": "100000"},
        ]
    }
}


class TestResolveCompany:
    @patch("downloaders.sec.requests.Session.get")
    def test_resolve_aapl(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_COMPANY_TICKERS
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        downloader = SecDownloader(user_agent="Test/1.0 test@example.com")
        company = downloader.resolve_company("AAPL")
        assert company["cik"] == "320193"
        assert company["cik10"] == "0000320193"
        assert company["company_name"] == "Apple Inc."

    @patch("downloaders.sec.requests.Session.get")
    def test_ticker_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_COMPANY_TICKERS
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        downloader = SecDownloader(user_agent="Test/1.0 test@example.com")
        with pytest.raises(ValueError):
            downloader.resolve_company("ZZZZ")


class TestListFilings:
    @patch("downloaders.sec.requests.Session.get")
    def test_filter_10k(self, mock_get):
        def _mock_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "company_tickers.json" in url:
                resp.json.return_value = MOCK_COMPANY_TICKERS
            elif "submissions" in url:
                resp.json.return_value = MOCK_SUBMISSIONS
            else:
                resp.json.return_value = {}
            return resp

        mock_get.side_effect = _mock_get

        downloader = SecDownloader(user_agent="Test/1.0 test@example.com")
        filings = downloader.list_filings(
            "AAPL", form_types=["10-K"], years=[2024]
        )
        assert len(filings) == 1
        assert filings[0]["form_type"] == "10-K"


class TestSearchReport:
    @patch("downloaders.sec.requests.Session.get")
    def test_search_10k(self, mock_get):
        def _mock_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "company_tickers.json" in url:
                resp.json.return_value = MOCK_COMPANY_TICKERS
            elif "submissions" in url:
                resp.json.return_value = MOCK_SUBMISSIONS
            elif "index.json" in url:
                resp.json.return_value = MOCK_INDEX_JSON
            else:
                # 文件下载
                resp.content = b"<html><body>10-K Filing</body></html>"
            return resp

        mock_get.side_effect = _mock_get

        downloader = SecDownloader(user_agent="Test/1.0 test@example.com")
        result = downloader.search_report("AAPL", 2024, "年报", save_dir=".")

        assert result is not None
        assert result["form_type"] == "10-K"
        assert "filepath" in result
