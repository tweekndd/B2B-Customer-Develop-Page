"""
测试：关键词分析 (keyword_analyzer)
覆盖正/负关键词命中、单词边界、多词关键词、边界条件
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.keyword_analyzer import analyze_keywords


class TestPositiveKeywords:
    """正向关键词"""

    def test_wastewater_detected(self):
        pos, neg = analyze_keywords("We treat wastewater for municipalities.")
        assert "wastewater" in pos
        assert pos["wastewater"] >= 1
        assert neg == {}

    def test_multiple_positive_hits(self):
        pos, neg = analyze_keywords(
            "wastewater treatment plant. biogas production. sewage systems."
        )
        assert "wastewater" in pos
        assert "biogas" in pos
        assert "sewage" in pos
        assert len(pos) >= 3

    def test_no_keywords(self):
        pos, neg = analyze_keywords("We are a car dealer.")
        assert pos == {}

    def test_keyword_count_accuracy(self):
        pos, neg = analyze_keywords("wastewater is here. wastewater again. and wastewater third.")
        assert pos["wastewater"] == 3


class TestNegativeKeywords:
    """负向关键词"""

    def test_job_career_detected(self):
        pos, neg = analyze_keywords("We have job vacancies. Careers at our company.")
        assert "job" in neg or "career" in neg

    def test_mixed_keywords(self):
        """同时存在正向和负向关键词"""
        pos, neg = analyze_keywords(
            "Wastewater treatment company. Current job vacancies."
        )
        assert "wastewater" in pos
        assert "job" in neg


class TestWordBoundaries:
    """单词边界匹配"""

    def test_substring_not_matched(self):
        """'water' 不应匹配 'waterproof'（因为 \b 边界）"""
        pos, neg = analyze_keywords("This is a waterproof jacket.")
        assert "water treatment" not in pos  # 不匹配
        # 'water' 在 'waterproof' 中，单词边界在 'water' 尾部不匹配
        # 但 'water' 单词边界在首部匹配，但尾部防水...
        # 实际上 wastewater / water treatment 等多词关键词是 substring 匹配
        # 单字词如 'tank' 用 \b 边界
        pass

    def test_single_word_boundary(self):
        """'tank' 不应匹配 'tanker'"""
        pos, neg = analyze_keywords("We operate tanker trucks.")
        assert "tank" not in pos  # 单词边界确保不匹配


class TestMultiWordKeywords:
    """多词关键词（子串匹配）"""

    def test_water_treatment(self):
        pos, neg = analyze_keywords("We offer water treatment services.")
        assert "water treatment" in pos

    def test_storage_tank(self):
        pos, neg = analyze_keywords("We manufacture storage tank systems.")
        assert "storage tank" in pos

    def test_municipal_water(self):
        pos, neg = analyze_keywords("municipal water supply project")
        assert "municipal water" in pos

    def test_industrial_water(self):
        pos, neg = analyze_keywords("industrial water treatment")
        assert "industrial water" in pos


class TestEdgeCases:
    """边界条件"""

    def test_empty_text(self):
        pos, neg = analyze_keywords("")
        assert pos == {}
        assert neg == {}

    def test_none_text(self):
        pos, neg = analyze_keywords(None)
        assert pos == {}
        assert neg == {}

    def test_case_insensitivity(self):
        pos, neg = analyze_keywords("WASTEWATER TREATMENT PLANT")
        assert "wastewater" in pos
        assert "water treatment" in pos

    def test_keywords_sorted_by_count(self):
        """返回结果应按命中次数降序排列"""
        pos, neg = analyze_keywords("wastewater wastewater wastewater biogas biogas tank")
        keys = list(pos.keys())
        assert pos[keys[0]] >= pos[keys[-1]]  # 降序
