"""
测试：去重工具 (deduplication)
覆盖公司名标准化、相似度判断
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.deduplication import (
    normalize_company_name,
    is_similar_name,
    find_existing_customer,
)


class TestNormalizeCompanyName:
    """公司名标准化"""

    def test_basic_normalization(self):
        assert normalize_company_name("ABC Water Treatment, Inc.") == "abc water treatment"

    def test_spanish_legal_suffix(self):
        assert normalize_company_name("Agua y Saneamiento S.A. de C.V.") == "agua saneamiento"

    def test_gmbh(self):
        assert normalize_company_name("WaterTech GmbH") == "watertech"

    def test_company_limited(self):
        result = normalize_company_name("ABC Company Limited")
        assert result == "abc"  # "company" 和 "limited" 都被移除

    def test_spanish_sa(self):
        """处理西班牙语 S.A. 后缀"""
        assert normalize_company_name("Tratamiento de Aguas México, S.A.") == "tratamiento aguas méxico"

    def test_whitespace_trimming(self):
        assert normalize_company_name("  XYZ Construction  ") == "xyz construction"

    def test_empty_string(self):
        assert normalize_company_name("") == ""

    def test_none(self):
        assert normalize_company_name(None) == ""

    def test_hyphen_preserved(self):
        """连字符应保留"""
        assert normalize_company_name("Aqua-Tech Industries") == "aqua-tech"

    def test_stop_words_removed(self):
        """停用词（de, del, la, y 等）应移除"""
        assert normalize_company_name("Empresa de Tratamiento del Agua") == "empresa tratamiento agua"

    def test_multiple_suffixes(self):
        """多个后缀同时存在"""
        name = "Water Solutions Ltd. S.A. de C.V."
        result = normalize_company_name(name)
        assert "water solutions" in result


class TestIsSimilarName:
    """公司名相似度判断"""

    def test_exact_same(self):
        assert is_similar_name("ABC Water Treatment", "ABC Water Treatment") is True

    def test_suffix_difference(self):
        assert is_similar_name("ABC Water Treatment Inc.", "ABC Water Treatment") is True

    def test_spanish_variation(self):
        assert is_similar_name(
            "Tratamiento de Aguas México S.A. de C.V.",
            "Tratamiento de Aguas",
        ) is True

    def test_completely_different(self):
        assert is_similar_name("ABC Water Treatment", "XYZ Construction") is False

    def test_empty_first(self):
        assert is_similar_name("", "ABC") is False

    def test_empty_second(self):
        assert is_similar_name("ABC", "") is False

    def test_both_empty(self):
        assert is_similar_name("", "") is False

    def test_one_contains_other_long(self):
        """包含关系且长度比达标"""
        assert is_similar_name(
            "Empresa de Tratamiento de Aguas Residuales S.A.",
            "Tratamiento de Aguas Residuales",
        ) is True

    def test_too_short_contained(self):
        """包含但太短不应算相似（如 'Co.' 匹配 'Company'）"""
        # "Co" 作为后缀被移除后只剩空字符串，但在被比较时会做标准化
        # 这个测试保证不会因为太短的包含关系误判
        result = is_similar_name("Co.", "International Water Solutions Co.")
        assert result is False
