"""
测试：网址标准化 (url_normalizer)
覆盖去协议、去 www、去路径、边界条件
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.url_normalizer import normalize_url, extract_domain, is_same_domain


class TestNormalizeUrl:
    """URL 标准化"""

    def test_strip_protocol_https(self):
        assert normalize_url("https://example.com") == "example.com"

    def test_strip_protocol_http(self):
        assert normalize_url("http://example.com") == "example.com"

    def test_strip_www(self):
        assert normalize_url("https://www.example.com") == "example.com"

    def test_strip_path(self):
        assert normalize_url("https://example.com/about") == "example.com"

    def test_strip_path_and_params(self):
        assert normalize_url("https://example.com/page?q=1") == "example.com"

    def test_strip_fragment(self):
        assert normalize_url("https://example.com/#section") == "example.com"

    def test_lowercase(self):
        assert normalize_url("HTTPS://EXAMPLE.COM") == "example.com"

    def test_empty_string(self):
        assert normalize_url("") == ""

    def test_none(self):
        assert normalize_url(None) == ""

    def test_already_normalized(self):
        assert normalize_url("example.com") == "example.com"

    def test_no_www_http(self):
        assert normalize_url("http://example.com") == "example.com"

    def test_www_without_protocol(self):
        assert normalize_url("www.example.com") == "example.com"


class TestExtractDomain:
    """域名提取"""

    def test_full_url(self):
        assert extract_domain("https://www.example.com/about") == "example.com"

    def test_without_protocol(self):
        assert extract_domain("www.example.com") == "example.com"

    def test_ip_address(self):
        assert extract_domain("http://192.168.1.1/admin") == "192.168.1.1"

    def test_empty(self):
        assert extract_domain("") == ""


class TestIsSameDomain:
    """域名比较"""

    def test_same_domain(self):
        assert is_same_domain("https://example.com", "http://www.example.com") is True

    def test_different_domains(self):
        assert is_same_domain("https://example.com", "https://other.com") is False

    def test_same_domain_different_path(self):
        assert is_same_domain("https://example.com/about", "http://www.example.com/contact") is True
