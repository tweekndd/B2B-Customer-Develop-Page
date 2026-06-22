"""
pytest 共享 fixtures
"""
import sys
import os

# 确保项目路径在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
