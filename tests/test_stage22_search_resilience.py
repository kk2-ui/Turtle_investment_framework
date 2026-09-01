from __future__ import annotations

from scripts.turtle_agent.tools import search_tools


class _Response:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _Client:
    def __init__(self, text: str) -> None:
        self.text = text

    def get(self, *args, **kwargs):
        return _Response(self.text)


def test_sogou_parser_returns_resolvable_urls_and_clean_text() -> None:
    html = '''
    <div class="vrwrap">
      <h3><a href="/link?url=abc"><em>金融街</em>物业年报</a></h3>
      <p class="str_info">2025 年收入与利润摘要</p>
    </div>
    '''
    rows = search_tools._search_sogou(_Client(html), "金融街物业", 5)
    assert rows == [{
        "title": "金融街物业年报",
        "url": "https://www.sogou.com/link?url=abc",
        "snippet": "2025 年收入与利润摘要",
    }]


def test_web_search_falls_back_and_reports_failed_provider(monkeypatch) -> None:
    def broken(client, query, limit):
        raise RuntimeError("tls eof")

    def working(client, query, limit):
        return [{"title": "官方年报", "url": "https://example.test/report", "snippet": "正文"}]

    monkeypatch.setattr(search_tools, "_SEARCH_PROVIDERS", {"first": broken, "second": working})
    monkeypatch.setenv("TURTLE_WEB_SEARCH_PROVIDERS", "first,second")
    result = search_tools.web_search("公司年报", max_results=3)
    assert result["provider"] == "second"
    assert len(result["results"]) == 1
    assert result["provider_errors"][0]["provider"] == "first"
    assert "tls eof" in result["provider_errors"][0]["error"]


def test_web_search_all_provider_failures_are_semantically_unusable(monkeypatch) -> None:
    monkeypatch.setattr(
        search_tools, "_SEARCH_PROVIDERS",
        {"broken": lambda client, query, limit: []},
    )
    monkeypatch.setenv("TURTLE_WEB_SEARCH_PROVIDERS", "broken")
    result = search_tools.web_search("公司年报")
    assert result["results"] == []
    assert result["error"] == "all_search_providers_failed"
    assert result["provider"] is None


def test_web_authority_marks_social_relays_low_but_keeps_direct_sites_reviewable() -> None:
    assert search_tools._classify_web_authority("https://mp.weixin.qq.com/s/abc") == "LOW"
    assert search_tools._classify_web_authority("https://www.stats.gov.cn/data") == "PRIMARY"
    assert search_tools._classify_web_authority("https://www.daikin.com/investor") == "STANDARD"
