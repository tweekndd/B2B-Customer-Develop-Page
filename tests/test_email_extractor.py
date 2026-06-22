"""
测试：邮箱提取 (email_extractor)
覆盖目标前缀提取、mailto 解析、通用回退、边界条件
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.email_extractor import extract_emails_from_text


class TestTargetPrefixEmails:
    """目标前缀邮箱提取"""

    def test_info_email(self):
        emails = extract_emails_from_text("Contact us at info@watertech.com")
        assert "info@watertech.com" in emails

    def test_sales_email(self):
        emails = extract_emails_from_text("Sales: sales@company.com")
        assert "sales@company.com" in emails

    def test_contact_email(self):
        emails = extract_emails_from_text("Email: contact@company.com")
        assert "contact@company.com" in emails

    def test_all_target_prefixes(self):
        text = "info@a.com sales@a.com contact@a.com procurement@a.com project@a.com marketing@a.com"
        emails = extract_emails_from_text(text)
        assert len(emails) >= 6
        assert "info@a.com" in emails
        assert "sales@a.com" in emails
        assert "contact@a.com" in emails
        assert "procurement@a.com" in emails
        assert "project@a.com" in emails
        assert "marketing@a.com" in emails


class TestMailtoExtraction:
    """mailto 链接提取"""

    def test_mailto_link(self):
        text = '<a href="mailto:sales@company.com">Send email</a>'
        emails = extract_emails_from_text(text)
        assert "sales@company.com" in emails

    def test_mailto_with_multiple(self):
        text = """
        <a href="mailto:info@company.com">Info</a>
        <a href="mailto:support@company.com">Support</a>
        """
        emails = extract_emails_from_text(text)
        assert "info@company.com" in emails
        assert "support@company.com" in emails


class TestGeneralEmailFallback:
    """少于3个目标邮箱时回退到通用提取"""

    def test_general_fallback(self):
        """只有1个目标前缀邮箱，应额外提取所有邮箱"""
        text = "Email: ceo@water.com and anyone@water.com also info@water.com and test@water.com"
        emails = extract_emails_from_text(text)
        # 应提取到 ceo@water.com、anyone@water.com、info@water.com、test@water.com
        assert "ceo@water.com" in emails
        assert "anyone@water.com" in emails
        assert "info@water.com" in emails

    def test_no_general_fallback_when_enough(self):
        """4个目标前缀邮箱，不应回退到通用提取"""
        text = "info@a.com sales@a.com contact@a.com procurement@a.com and some random test@a.com"
        emails = extract_emails_from_text(text)
        # 4个目标前缀邮箱 ≥ 3，不触发通用回退，所以 test@a.com 不被提取
        assert "info@a.com" in emails
        assert "test@a.com" not in emails  # 没有 info/sales/contact/procurement 前缀


class TestEdgeCases:
    """边界条件"""

    def test_empty_text(self):
        emails = extract_emails_from_text("")
        assert emails == []

    def test_none_text(self):
        emails = extract_emails_from_text(None)
        assert emails == []

    def test_no_emails(self):
        emails = extract_emails_from_text("This is a company website with no email addresses.")
        assert emails == []

    def test_duplicate_emails(self):
        """重复邮箱应去重"""
        text = "info@company.com and also info@company.com again"
        emails = extract_emails_from_text(text)
        assert len(emails) == 1
        assert emails == ["info@company.com"]

    def test_email_with_subdomain(self):
        emails = extract_emails_from_text("sales@sub.water.com")
        assert "sales@sub.water.com" in emails

    def test_case_insensitive(self):
        emails = extract_emails_from_text("INFO@COMPANY.COM")
        assert "info@company.com" in emails  # 返回小写
