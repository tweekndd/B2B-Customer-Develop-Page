"""
API 集成测试 — V2.8 P1 新增
使用 FastAPI TestClient 覆盖核心 API，确保路由注册、CRUD、配置读写正确
"""
import pytest
import sys
import os
import json
import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base, get_db, Customer, SearchTask
from app.services.scoring_engine import invalidate_config_cache
from main import app


# ── 测试数据库：独立 SQLite 文件，不影响生产数据 ──
_TEST_DB = os.path.join(os.path.dirname(__file__), "test_api.db")
TEST_DATABASE_URL = f"sqlite:///{_TEST_DB}"
_test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# ── 生产配置文件保护 ──
_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "services")
_CONFIG_BACKUP = {}
_CONFIG_FILES = ["industry_config.json", "country_weights.json"]


def backup_config():
    """备份配置文件以便测试后恢复"""
    global _CONFIG_BACKUP
    _CONFIG_BACKUP = {}
    for fname in _CONFIG_FILES:
        fpath = os.path.join(_CONFIG_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                _CONFIG_BACKUP[fname] = f.read()
        except FileNotFoundError:
            _CONFIG_BACKUP[fname] = None


def restore_config():
    """恢复所有配置文件并清除评分缓存"""
    for fname in _CONFIG_FILES:
        content = _CONFIG_BACKUP.get(fname)
        if content is not None:
            fpath = os.path.join(_CONFIG_DIR, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
    # 清除评分引擎缓存，防止旧缓存影响后续测试
    invalidate_config_cache()


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试函数前重建表，测试后清理"""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)
    # 每个测试后恢复配置文件（防止 config API 测试覆盖生产配置）
    restore_config()


@pytest.fixture(scope="session", autouse=True)
def session_init():
    """测试会话开始时备份配置"""
    backup_config()
    yield


# ═══════════════════════════════════════════════
# 客户 CRUD
# ═══════════════════════════════════════════════

class TestCustomerCRUD:
    """客户列表/详情/删除 API"""

    def _create_test_customer(self, db: Session, **overrides) -> Customer:
        """辅助：直接在 DB 插入客户"""
        data = {
            "company_name": "Test Water Corp",
            "website": "testwater.com",
            "country": "Saudi Arabia",
            "discovery_source": "Manual Import",
            "total_score": 75,
            "priority": "B",
            "created_at": datetime.datetime.utcnow(),
        }
        data.update(overrides)
        c = Customer(**data)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c

    def test_list_empty(self):
        """列表应为空"""
        resp = client.get("/api/customers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["customers"] == []

    def test_list_with_data(self):
        """插入后列表应有 1 条"""
        db = TestSessionLocal()
        self._create_test_customer(db)
        db.close()

        resp = client.get("/api/customers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["customers"][0]["company_name"] == "Test Water Corp"

    def test_get_detail(self):
        """获取客户详情"""
        db = TestSessionLocal()
        c = self._create_test_customer(db)
        db.close()

        resp = client.get(f"/api/customers/{c.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_name"] == "Test Water Corp"
        assert data["total_score"] == 75

    def test_get_detail_not_found(self):
        """不存在的客户应返回 404"""
        resp = client.get("/api/customers/999")
        assert resp.status_code == 404

    def test_delete(self):
        """删除客户"""
        db = TestSessionLocal()
        c = self._create_test_customer(db)
        db.close()

        resp = client.delete(f"/api/customers/{c.id}")
        assert resp.status_code == 200

        # 确认已删除
        resp = client.get(f"/api/customers/{c.id}")
        assert resp.status_code == 404

    def test_list_filter_by_priority(self):
        """按优先级筛选"""
        db = TestSessionLocal()
        self._create_test_customer(db, priority="A", total_score=90)
        self._create_test_customer(db, priority="B", total_score=65)
        db.close()

        resp = client.get("/api/customers?priority=A")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_list_sort_by_score(self):
        """按分数升序排序"""
        db = TestSessionLocal()
        self._create_test_customer(db, total_score=50)
        self._create_test_customer(db, total_score=90)
        db.close()

        resp = client.get("/api/customers?sort_by_score=asc")
        assert resp.status_code == 200
        data = resp.json()
        scores = [c["total_score"] for c in data["customers"]]
        assert scores == sorted(scores)

    def test_list_pagination(self):
        """分页参数"""
        db = TestSessionLocal()
        for i in range(5):
            self._create_test_customer(db, company_name=f"Company {i}")
        db.close()

        resp = client.get("/api/customers?page=1&page_size=10")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["customers"]) == 5
        assert data["total"] == 5
        assert data["total_pages"] == 1


# ═══════════════════════════════════════════════
# 统计数据 API
# ═══════════════════════════════════════════════

class TestStats:
    """统计信息 API"""

    def test_stats_empty(self):
        """空数据库的统计"""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_stats_with_data(self):
        """有数据时的统计"""
        db = TestSessionLocal()
        for p, s in [("A", 90), ("B", 75), ("C", 50), ("D", 25)]:
            db.add(Customer(
                company_name=f"Company {p}",
                country="Saudi Arabia",
                total_score=s,
                priority=p,
                created_at=datetime.datetime.utcnow(),
            ))
        db.commit()
        db.close()

        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert data["priority_distribution"]["A"] == 1
        assert data["priority_distribution"]["B"] == 1


# ═══════════════════════════════════════════════
# 配置管理 API
# ═══════════════════════════════════════════════

class TestConfigAPI:
    """评分配置读写"""

    def test_get_config(self):
        """读取配置（应该始终返回 200）"""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "industry_config" in data
        assert "country_weights" in data
        assert "scoring" in data["industry_config"]

    def test_save_country_weights_valid(self):
        """写入合法的国家权重"""
        weights = {"Saudi Arabia": 15, "UAE": 12}
        resp = client.put("/api/config/country-weights", json=weights)
        assert resp.status_code == 200

        # 读取验证
        resp = client.get("/api/config")
        data = resp.json()
        assert data["country_weights"]["Saudi Arabia"] == 15

    def test_save_country_weights_invalid(self):
        """写入非法权重（超过 100）应拒绝"""
        weights = {"Saudi Arabia": 999}
        resp = client.put("/api/config/country-weights", json=weights)
        assert resp.status_code == 400

    def test_save_industry_config_valid(self):
        """写入合法的行业配置"""
        # 只发送部分字段，校验器应接受可选字段缺失
        config = {
            "scoring": {
                "industry_match": {"max_score": 30, "keywords": {"solar": 5}},
                "project_match": {
                    "max_score": 25,
                    "detection_keywords": ["projects"],
                    "content_keywords": ["solar"],
                },
                "company_type": {
                    "max_score": 20,
                    "types": {"Manufacturer": 12},
                },
                "contact": {
                    "max_score": 10,
                    "tiers": [{"min_emails": 0, "score": 0}, {"min_emails": 1, "score": 3}],
                },
            },
            "priority_rules": {
                "A": {"min": 80},
                "B": {"min": 60},
                "C": {"min": 40},
                "D": {"min": 0},
            },
        }
        resp = client.put("/api/config", json=config)
        assert resp.status_code == 200, resp.text

        # 读取验证
        resp = client.get("/api/config")
        data = resp.json()
        assert data["industry_config"]["scoring"]["industry_match"]["keywords"]["solar"] == 5

    def test_save_industry_config_invalid(self):
        """写入非法配置应拒绝"""
        resp = client.put("/api/config", json={"scoring": "invalid"})
        assert resp.status_code == 400


# ═══════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════

class TestPageRoutes:
    """前端页面路由应返回 HTML"""

    def test_index_page(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_discovery_page(self):
        resp = client.get("/discovery")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_config_page(self):
        resp = client.get("/config")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "评分配置" in resp.text or "评分配置" in resp.text


# ═══════════════════════════════════════════════
# 数据同步 API
# ═══════════════════════════════════════════════

class TestSync:
    """数据同步 API"""

    def test_sync_export_empty(self):
        resp = client.get("/api/sync/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "customers" in data["data"]

    def test_sync_import(self):
        payload = {"data": {
            "customers": [{
                "company_name": "Imported Co",
                "website": "imported.com",
                "country": "UAE",
                "total_score": 85,
                "priority": "A",
            }],
            "search_tasks": [],
            "search_cache": [],
            "website_cache": [],
            "analysis_cache": [],
        }}
        resp = client.post("/api/sync/import", json=payload)
        assert resp.status_code == 200, resp.text

        # 确认已导入
        resp = client.get("/api/customers")
        data = resp.json()
        names = [c["company_name"] for c in data["customers"]]
        assert "Imported Co" in names


# ── 清理测试数据库 ──

def teardown_module(module):
    """模块结束时删除测试数据库文件"""
    db_path = _TEST_DB
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except PermissionError:
        pass  # Windows 可能锁文件，忽略
