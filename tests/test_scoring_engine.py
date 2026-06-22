"""
测试：规则评分引擎 (scoring_engine)
覆盖 5 个评分维度 + 优先级判定 + 边界条件
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.scoring_engine import (
    calculate_scores,
    _score_industry_match,
    _score_project_match,
    _score_company_type,
    _score_country,
    _score_contact,
)


class TestIndustryMatch:
    """行业匹配度（满分30）"""

    def test_water_keywords_hit(self):
        """命中多个水处理关键词"""
        text = "We provide wastewater treatment and sewage solutions. Our biogas systems are efficient."
        score, detail = _score_industry_match(text)
        assert score > 0
        assert score <= 30
        assert "wastewater" in detail or "sewage" in detail or "biogas" in detail

    def test_no_keywords(self):
        """完全不命中关键词"""
        score, detail = _score_industry_match("We are a car manufacturer.")
        assert score == 0

    def test_empty_text(self):
        """空文本"""
        score, detail = _score_industry_match("")
        assert score == 0
        assert "无官网内容" in detail


class TestProjectMatch:
    """项目匹配度（满分25）"""

    def test_has_project_and_content(self):
        """有项目案例且有行业内容匹配"""
        text = "Check our completed projects. We specialize in wastewater treatment plants."
        score, detail = _score_project_match(text)
        assert score >= 20  # has_project_base(10) + has_content_match(15)
        assert score <= 25

    def test_has_project_only(self):
        """有项目但无水处理（加低相关度分）"""
        text = "Our projects include various construction sites."
        score, _ = _score_project_match(text)
        assert score == 15  # has_project_base(10) + low_relevance(5)

    def test_no_project(self):
        """无项目信息"""
        score, detail = _score_project_match("We sell products.")
        assert score == 0
        assert "未识别到项目信息" in detail

    def test_empty_text(self):
        """空文本"""
        score, detail = _score_project_match("")
        assert score == 0
        assert "无官网内容" in detail


class TestCompanyType:
    """公司类型（满分20）"""

    def test_epc(self):
        score, detail = _score_company_type("EPC")
        assert score == 20

    def test_contractor(self):
        score, detail = _score_company_type("Contractor")
        assert score == 18

    def test_water_treatment_company(self):
        score, detail = _score_company_type("Water Treatment Company")
        assert score == 18

    def test_manufacturer(self):
        score, detail = _score_company_type("Manufacturer")
        assert score == 12

    def test_other(self):
        score, detail = _score_company_type("Other")
        assert score == 0

    def test_unknown(self):
        score, detail = _score_company_type("Some Unknown Type")
        assert score == 0

    def test_none(self):
        score, detail = _score_company_type(None)
        assert score == 0
        assert "未识别" in detail


class TestCountryScore:
    """国家优先级（满分15）"""

    def test_saudi_arabia(self):
        score, detail = _score_country("Saudi Arabia")
        assert score == 15

    def test_mexico(self):
        score, detail = _score_country("Mexico")
        assert score == 10

    def test_usa_zero(self):
        score, detail = _score_country("USA")
        assert score == 0

    def test_unknown_country(self):
        score, detail = _score_country("Atlantis")
        assert score == 5  # Other

    def test_none(self):
        score, detail = _score_country(None)
        assert score == 0
        assert "未指定国家" in detail


class TestContactScore:
    """联系方式（满分10）"""

    def test_no_emails(self):
        score, detail = _score_contact([])
        assert score == 0

    def test_one_email(self):
        score, detail = _score_contact(["info@company.com"])
        assert score == 3

    def test_two_emails(self):
        score, detail = _score_contact(["info@c.com", "sales@c.com"])
        assert score == 5

    def test_three_emails(self):
        score, detail = _score_contact(["a@c.com", "b@c.com", "c@c.com"])
        assert score == 8

    def test_four_or_more(self):
        score, detail = _score_contact(["a@c.com", "b@c.com", "c@c.com", "d@c.com"])
        assert score == 10

    def test_seven_emails(self):
        score, detail = _score_contact(["a@c.com", "b@c.com", "c@c.com", "d@c.com", "e@c.com", "f@c.com", "g@c.com"])
        assert score == 10

    def test_none(self):
        score, detail = _score_contact(None)
        assert score == 0


class TestCalculateScores:
    """综合评分"""

    def test_full_score_scenario(self):
        """理想情况下高分"""
        result = calculate_scores(
            website_text="We have projects in wastewater treatment. Our sewage systems are top.",
            positive_keywords={"wastewater": 3, "sewage": 2},
            company_type="EPC",
            country="Saudi Arabia",
            emails=["info@c.com", "sales@c.com", "project@c.com"],
        )
        assert result["total_score"] >= 50
        assert result["priority"] in ("A", "B", "C", "D")
        assert result["industry_score"] >= 0
        assert result["project_score"] >= 0
        assert result["company_type_score"] >= 0
        assert result["country_score"] >= 0
        assert result["contact_score"] >= 0

    def test_minimum_score(self):
        """最差情况"""
        result = calculate_scores(
            website_text="",
            positive_keywords={},
            company_type=None,
            country="USA",
            emails=[],
        )
        assert result["total_score"] == 0
        assert result["priority"] == "D"

    def test_priority_a(self):
        """80分以上应为A级"""
        result = calculate_scores(
            website_text="We provide wastewater treatment projects and sewage effluent systems. "
                         "Our biogas digesters and industrial water solutions are the best. "
                         "Check our completed projects for case studies in municipal water desalination.",
            positive_keywords={"wastewater": 3, "sewage": 2, "effluent": 1, "biogas": 2, "digester": 1},
            company_type="EPC",
            country="Saudi Arabia",
            emails=["info@c.com", "sales@c.com", "procurement@c.com", "project@c.com"],
        )
        assert result["total_score"] >= 80
        assert result["priority"] == "A"

    def test_all_fields_present(self):
        """返回结果包含所有字段"""
        result = calculate_scores(
            website_text="water treatment",
            positive_keywords={"water": 1},
            company_type="Manufacturer",
            country="Germany",
            emails=["info@c.com"],
        )
        expected_keys = [
            "industry_score", "industry_detail",
            "project_score", "project_detail",
            "company_type_score", "company_type_detail",
            "country_score", "country_detail",
            "contact_score", "contact_detail",
            "total_score", "priority",
        ]
        for key in expected_keys:
            assert key in result, f"缺少字段: {key}"
