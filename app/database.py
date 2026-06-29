"""
数据库配置与模型定义
V2.2：Customer 新增跟进状态（status/follow_up_date/notes）
       新增抓取/分析状态字段（scrape_status/ai_status/fail_reason）
V2.6：支持 PostgreSQL 通过 DATABASE_URL 环境变量切换
"""
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# 数据库连接：优先使用环境变量 DATABASE_URL，否则回退到 SQLite
_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if _DATABASE_URL:
    # PostgreSQL 或其他外部数据库（由环境变量控制）
    DATABASE_URL = _DATABASE_URL
    _engine_kwargs = {"pool_pre_ping": True}
else:
    # SQLite 本地文件（默认）
    DATABASE_URL = "sqlite:///./app/customers.db"
    _engine_kwargs = {"connect_args": {"check_same_thread": False}}

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Customer(Base):
    """客户数据模型（V2.0 新增发现来源字段）"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, index=True, comment="公司名称")
    website = Column(String(500), nullable=True, comment="公司官网")
    country = Column(String(100), nullable=True, comment="国家")

    # V2.0 新增：发现来源记录
    discovery_source = Column(String(50), nullable=True, index=True, comment="发现来源（Google / Manual Import）")
    discovery_keyword = Column(String(200), nullable=True, comment="发现时使用的关键词")
    first_found_at = Column(DateTime, nullable=True, comment="首次发现时间")

    # 邮箱与官网内容
    emails = Column(Text, nullable=True, comment="提取的邮箱列表（JSON格式）")
    website_text = Column(Text, nullable=True, comment="官网爬取的纯文本内容")
    positive_keywords = Column(Text, nullable=True, comment="命中的正向关键词及次数（JSON格式）")
    negative_keywords = Column(Text, nullable=True, comment="命中的负向关键词及次数（JSON格式）")

    # 规则评分引擎字段
    industry_score = Column(Integer, nullable=True, comment="行业匹配度 0-30")
    project_score = Column(Integer, nullable=True, comment="项目匹配度 0-25")
    company_type_score = Column(Integer, nullable=True, comment="公司类型 0-20")
    country_score = Column(Integer, nullable=True, comment="国家优先级 0-15")
    contact_score = Column(Integer, nullable=True, comment="联系方式完整度 0-10")
    total_score = Column(Integer, nullable=True, index=True, comment="总分 0-100")
    priority = Column(String(1), nullable=True, index=True, comment="优先级 A/B/C/D")

    # AI分析字段
    company_type = Column(String(50), nullable=True, comment="AI分析的公司类型")
    ai_summary = Column(Text, nullable=True, comment="AI生成的150字以内摘要（英文）")
    sales_hook = Column(Text, nullable=True, comment="推荐开发切入点（中文）")
    target_position = Column(Text, nullable=True, comment="推荐联系职位（中文）")
    identified_projects = Column(Text, nullable=True, comment="AI识别的项目信息（JSON格式）")
    ai_raw_json = Column(Text, nullable=True, comment="AI返回的原始JSON数据")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")
    analyzed_at = Column(DateTime, nullable=True, index=True, comment="分析完成时间")

    # V2.2 新增：客户跟进状态
    status = Column(String(20), default="待联系", index=True, comment="跟进状态: 待联系/已发邮件/已回复/无效线索/成单")
    follow_up_date = Column(Date, nullable=True, comment="下次跟进日期")
    notes = Column(Text, nullable=True, comment="跟进备注")

    # V2.2 新增：抓取/分析状态（用于失败可视化）
    scrape_status = Column(String(20), nullable=True, comment="官网抓取状态: success/failed/partial/skipped")
    ai_status = Column(String(20), nullable=True, comment="AI分析状态: success/failed/skipped")
    fail_reason = Column(String(500), nullable=True, comment="失败原因描述")

    # V2.2 新增：客户自定义评级（1-5星，0=未评级）
    star_rating = Column(Integer, default=0, comment="客户评级: 0未评级/1-5星")

    # V3.2.5 新增：城市字段（用于地理编码定位到城市级别）
    city = Column(String(200), nullable=True, comment="城市")
    # V3.2.4 新增：Geocoding 地理编码字段
    latitude = Column(Float, nullable=True, default=None, comment="纬度")
    longitude = Column(Float, nullable=True, default=None, comment="经度")
    geocode_status = Column(String(20), default="pending", comment="地理编码状态: pending/done/failed")


class SearchTask(Base):
    """搜索任务（V2.0 新增）"""
    __tablename__ = "search_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    country = Column(String(100), nullable=False, comment="搜索国家")
    keyword = Column(String(200), nullable=False, comment="原始关键词")
    expanded_keywords = Column(Text, nullable=True, comment="AI扩展的关键词列表（JSON数组）")
    search_depth = Column(Integer, default=50, comment="每个关键词期望搜索数量")
    status = Column(String(20), default="Pending", comment="任务状态: Pending/Running/Completed/Failed/Paused")
    found_websites = Column(Integer, default=0, comment="发现的网站数量")
    analyzed_companies = Column(Integer, default=0, comment="已分析的公司数量")
    new_companies = Column(Integer, default=0, comment="新增公司数量")
    current_keyword_index = Column(Integer, default=0, comment="当前处理到第几个扩展关键词（断点续跑）")
    error_message = Column(Text, nullable=True, comment="失败时的错误信息")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")
    finished_at = Column(DateTime, nullable=True, comment="完成时间")
    task_log = Column(Text, nullable=True, comment="任务运行日志")


class SearchCache(Base):
    """搜索结果缓存（V2.0 新增，避免重复搜索相同关键词）"""
    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    keyword = Column(String(200), nullable=False, index=True, comment="搜索关键词")
    country = Column(String(100), nullable=False, index=True, comment="搜索国家")
    website = Column(String(500), nullable=False, comment="发现的企业官网")
    title = Column(String(500), nullable=True, comment="搜索结果标题")
    snippet = Column(Text, nullable=True, comment="搜索结果摘要")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="缓存时间")


class WebsiteCache(Base):
    """官网抓取缓存（V2.0 新增，避免重复抓取相同网站）"""
    __tablename__ = "website_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    website = Column(String(500), nullable=False, unique=True, index=True, comment="网站域名")
    content = Column(Text, nullable=True, comment="抓取的纯文本内容")
    content_hash = Column(String(64), nullable=True, comment="内容哈希值，用于判断内容是否变化")
    last_crawled = Column(DateTime, nullable=True, comment="上次抓取时间")


class HunterCache(Base):
    """Hunter API 查询缓存（V3.0 新增，避免重复消耗搜索/验证额度）"""
    __tablename__ = "hunter_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cache_key = Column(String(500), nullable=False, unique=True, index=True, comment="缓存唯一键: domain|type|params")
    domain = Column(String(255), nullable=False, index=True, comment="公司域名")
    query_type = Column(String(30), nullable=False, comment="查询类型: email_count/domain_search/email_finder/email_verifier")
    result = Column(Text, nullable=False, comment="API 返回结果 (JSON)")
    hits = Column(Integer, default=1, comment="缓存命中次数（辅助统计）")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")


class TombaCache(Base):
    """Tomba API 查询缓存（Phase 1 新增，避免重复消耗搜索额度）"""
    __tablename__ = "tomba_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cache_key = Column(String(500), nullable=False, unique=True, index=True, comment="缓存唯一键: domain|type|params")
    domain = Column(String(255), nullable=False, index=True, comment="公司域名")
    query_type = Column(String(30), nullable=False, comment="查询类型: domain_search/email_finder/email_verifier")
    result = Column(Text, nullable=False, comment="API 返回结果 (JSON)")
    hits = Column(Integer, default=1, comment="缓存命中次数（辅助统计）")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")


class EmailQuotaLog(Base):
    """邮箱发现配额使用日志（Phase 1 新增，持久化记录各平台配额消耗）"""
    __tablename__ = "email_quota_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source = Column(String(30), nullable=False, comment="数据源: hunter/tomba/scraped")
    query_type = Column(String(30), nullable=False, comment="查询类型")
    domain = Column(String(255), nullable=False, comment="查询的域名")
    result_count = Column(Integer, default=0, comment="返回结果数量")
    credits_consumed = Column(Integer, default=0, comment="消耗的配额次数")
    success = Column(Integer, default=1, comment="是否成功: 1成功/0失败")
    error_message = Column(String(500), nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="记录时间")


class AnalysisCache(Base):
    """AI分析缓存（V2.0 新增，避免重复调用DeepSeek）"""
    __tablename__ = "analysis_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    website = Column(String(500), nullable=False, index=True, comment="网站域名")
    content_hash = Column(String(64), nullable=True, comment="对应官网内容的哈希值")
    company_type = Column(String(50), nullable=True, comment="公司类型")
    summary = Column(Text, nullable=True, comment="英文摘要")
    sales_hook = Column(Text, nullable=True, comment="开发切入点")
    target_position = Column(Text, nullable=True, comment="推荐联系职位")
    analysis_reason = Column(Text, nullable=True, comment="分析原因")
    identified_projects = Column(Text, nullable=True, comment="识别的项目信息")
    raw_json = Column(Text, nullable=True, comment="AI返回的原始JSON")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="缓存时间")


class GeocodeCache(Base):
    """地理编码结果缓存（V3.2.5 新增，避免重复请求 Nominatim）"""
    __tablename__ = "geocode_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    query_key = Column(String(500), nullable=False, unique=True, index=True, comment="查询键: city|Country 或 Country")
    country = Column(String(100), nullable=True, comment="国家")
    city = Column(String(200), nullable=True, comment="城市")
    latitude = Column(Float, nullable=False, comment="纬度")
    longitude = Column(Float, nullable=False, comment="经度")
    display_name = Column(String(500), nullable=True, comment="Nominatim 返回的完整地址名")
    hits = Column(Integer, default=1, comment="命中次数")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="缓存时间")


class ProspeoCache(Base):
    """Prospeo API 查询缓存（V3.2.2 新增，避免重复消耗搜索额度）"""
    __tablename__ = "prospeo_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cache_key = Column(String(500), nullable=False, unique=True, index=True, comment="缓存唯一键: domain|type|params")
    domain = Column(String(255), nullable=False, index=True, comment="公司域名")
    query_type = Column(String(30), nullable=False, comment="查询类型: search_person/enrich_person")
    person_id = Column(String(100), nullable=True, comment="Enrich 时对应的人员 ID")
    result = Column(Text, nullable=False, comment="API 返回结果 (JSON)")
    hits = Column(Integer, default=1, comment="缓存命中次数（辅助统计）")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")


def get_db():
    """获取数据库会话的生成器函数"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_indexes(engine):
    """确保关键查询字段存在索引（兼容已有数据库）"""
    import sqlalchemy as sa
    indexes = {
        "idx_customers_country": "CREATE INDEX IF NOT EXISTS idx_customers_country ON customers(country)",
        "idx_customers_priority": "CREATE INDEX IF NOT EXISTS idx_customers_priority ON customers(priority)",
        "idx_customers_status": "CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status)",
        "idx_customers_total_score": "CREATE INDEX IF NOT EXISTS idx_customers_total_score ON customers(total_score)",
        "idx_customers_discovery_source": "CREATE INDEX IF NOT EXISTS idx_customers_discovery_source ON customers(discovery_source)",
        "idx_customers_analyzed_at": "CREATE INDEX IF NOT EXISTS idx_customers_analyzed_at ON customers(analyzed_at)",
        "idx_search_cache_lookup": "CREATE INDEX IF NOT EXISTS idx_search_cache_lookup ON search_cache(keyword, country, created_at)",
        "idx_website_cache_lookup": "CREATE INDEX IF NOT EXISTS idx_website_cache_lookup ON website_cache(website, last_crawled)",
        "idx_analysis_cache_lookup": "CREATE INDEX IF NOT EXISTS idx_analysis_cache_lookup ON analysis_cache(website, content_hash)",
        "idx_cache_expiry_search": "CREATE INDEX IF NOT EXISTS idx_cache_expiry_search ON search_cache(created_at)",
        "idx_cache_expiry_website": "CREATE INDEX IF NOT EXISTS idx_cache_expiry_website ON website_cache(last_crawled)",
        "idx_cache_expiry_analysis": "CREATE INDEX IF NOT EXISTS idx_cache_expiry_analysis ON analysis_cache(created_at)",
        "idx_cache_expiry_hunter": "CREATE INDEX IF NOT EXISTS idx_cache_expiry_hunter ON hunter_cache(created_at)",
        "idx_cache_expiry_tomba": "CREATE INDEX IF NOT EXISTS idx_cache_expiry_tomba ON tomba_cache(created_at)",
        "idx_cache_expiry_quota": "CREATE INDEX IF NOT EXISTS idx_cache_expiry_quota ON email_quota_log(created_at)",
        "idx_cache_expiry_prospeo": "CREATE INDEX IF NOT EXISTS idx_cache_expiry_prospeo ON prospeo_cache(created_at)",
        "idx_prospeo_cache_domain": "CREATE INDEX IF NOT EXISTS idx_prospeo_cache_domain ON prospeo_cache(domain, query_type)",
        "idx_customers_geocode_status": "CREATE INDEX IF NOT EXISTS idx_customers_geocode_status ON customers(geocode_status)",
        "idx_geocode_cache_key": "CREATE INDEX IF NOT EXISTS idx_geocode_cache_key ON geocode_cache(query_key)",
        "idx_customers_map_query": "CREATE INDEX IF NOT EXISTS idx_customers_map_query ON customers(geocode_status, country)",
    }
    with engine.connect() as conn:
        for name, ddl in indexes.items():
            try:
                conn.execute(sa.text(ddl))
            except Exception as e:
                print(f"  索引创建跳过 {name}: {e}")
        conn.commit()


def init_db():
    """初始化数据库：创建所有表 + 自动迁移新增列（V2.2 支持）"""
    Base.metadata.create_all(bind=engine)
    _ensure_indexes(engine)

    # ── 自动迁移：检查并添加缺失的列（SQLite 不支持 DROP COLUMN，但支持 ADD COLUMN）──
    _migrate_add_column(engine, "customers", "status", "VARCHAR(20) DEFAULT '待联系'")
    _migrate_add_column(engine, "customers", "follow_up_date", "DATE")
    _migrate_add_column(engine, "customers", "notes", "TEXT")
    _migrate_add_column(engine, "customers", "scrape_status", "VARCHAR(20)")
    _migrate_add_column(engine, "customers", "ai_status", "VARCHAR(20)")
    _migrate_add_column(engine, "customers", "fail_reason", "VARCHAR(500)")
    _migrate_add_column(engine, "customers", "star_rating", "INTEGER DEFAULT 0")
    # V3.2.4 新增：Geocoding 字段
    _migrate_add_column(engine, "customers", "latitude", "FLOAT")
    _migrate_add_column(engine, "customers", "longitude", "FLOAT")
    _migrate_add_column(engine, "customers", "geocode_status", "VARCHAR(20) DEFAULT 'pending'")
    # V3.2.5 新增：city 字段
    _migrate_add_column(engine, "customers", "city", "VARCHAR(200)")
    # 搜索任务表字段
    _migrate_add_column(engine, "search_tasks", "task_log", "TEXT")
    # Hunter 缓存表字段
    _migrate_add_column(engine, "hunter_cache", "hits", "INTEGER DEFAULT 1")


def _migrate_add_column(engine, table: str, column: str, col_type: str):
    """
    检查表是否存在某列，不存在则添加
    这是为了兼容已有数据库文件，无需手动执行迁移
    """
    import sqlalchemy as sa
    try:
        with engine.connect() as conn:
            # 检查列是否存在
            inspector = sa.inspect(engine)
            columns = [c["name"] for c in inspector.get_columns(table)]
            if column not in columns:
                conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
                print(f"  数据库迁移: {table}.{column} 列已添加")
    except Exception as e:
        print(f"  数据库迁移跳过 {table}.{column}: {e}")
