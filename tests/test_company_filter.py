"""
测试：公司结果过滤 (company_filter)
覆盖社交媒体、招聘、新闻、政府/教育域名、正常企业域名放行
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.company_filter import is_blacklisted, filter_search_results


class TestSocialMedia:
    """社交媒体域名应被过滤"""

    def test_linkedin(self):
        assert is_blacklisted("https://linkedin.com/company/abc") is True

    def test_facebook(self):
        assert is_blacklisted("https://facebook.com/abc") is True

    def test_instagram(self):
        assert is_blacklisted("https://instagram.com/abc") is True

    def test_twitter(self):
        assert is_blacklisted("https://x.com/abc") is True

    def test_youtube(self):
        assert is_blacklisted("https://youtube.com/@abc") is True


class TestJobSites:
    """招聘网站应被过滤"""

    def test_indeed(self):
        assert is_blacklisted("https://indeed.com/company/abc") is True

    def test_glassdoor(self):
        assert is_blacklisted("https://glassdoor.com/abc") is True

    def test_infojobs(self):
        assert is_blacklisted("https://infojobs.net/abc") is True

    def test_computrabajo(self):
        assert is_blacklisted("https://computrabajo.com/abc") is True


class TestNewsSites:
    """新闻网站应被过滤"""

    def test_cnn(self):
        assert is_blacklisted("https://cnn.com/2024/abc") is True

    def test_bbc(self):
        assert is_blacklisted("https://bbc.com/news/abc") is True

    def test_reuters(self):
        assert is_blacklisted("https://reuters.com/article/abc") is True

    def test_elpais(self):
        assert is_blacklisted("https://elpais.com/abc") is True

    def test_elmundo(self):
        assert is_blacklisted("https://elmundo.es/abc") is True


class TestGovernmentEducation:
    """政府/教育域名应被过滤"""

    def test_gov_domain(self):
        assert is_blacklisted("https://agency.gov") is True

    def test_gov_ar(self):
        assert is_blacklisted("https://example.gob.ar") is True

    def test_gob_mx(self):
        assert is_blacklisted("https://example.gob.mx") is True

    def test_edu_domain(self):
        assert is_blacklisted("https://university.edu") is True

    def test_edu_mx(self):
        assert is_blacklisted("https://universidad.edu.mx") is True


class TestDirectories:
    """黄页/目录网站应被过滤"""

    def test_yellowpages(self):
        assert is_blacklisted("https://yellowpages.com/abc") is True

    def test_kompass(self):
        assert is_blacklisted("https://kompass.com/abc") is True

    def test_alibaba(self):
        assert is_blacklisted("https://alibaba.com/company/abc") is True


class TestValidCompanyUrls:
    """正常企业域名应放行"""

    def test_water_company(self):
        assert is_blacklisted("https://watertech.com") is False

    def test_manufacturer(self):
        assert is_blacklisted("https://manufacturing-solutions.de") is False

    def test_subdomain_company(self):
        assert is_blacklisted("https://corp.example.com") is False

    def test_long_domain(self):
        assert is_blacklisted("https://water-treatment-systems.co.uk") is False


class TestFilterSearchResults:
    """搜索结果过滤"""

    def test_filters_blacklisted(self):
        results = [
            {"website": "https://watertech.com", "title": "Water Tech"},
            {"website": "https://linkedin.com/company/watertech", "title": "LinkedIn"},
            {"website": "https://facebook.com/watertech", "title": "Facebook"},
        ]
        filtered = filter_search_results(results)
        assert len(filtered) == 1
        assert filtered[0]["website"] == "https://watertech.com"

    def test_empty_results(self):
        assert filter_search_results([]) == []

    def test_all_blacklisted(self):
        results = [
            {"website": "https://twitter.com/abc"},
            {"website": "https://indeed.com/jobs"},
        ]
        assert filter_search_results(results) == []

    def test_skip_empty_website(self):
        results = [
            {"website": "", "title": "No URL"},
            {"website": "https://watertech.com", "title": "Water Tech"},
        ]
        filtered = filter_search_results(results)
        assert len(filtered) == 1
