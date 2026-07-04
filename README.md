# AI Trade Customer Analyzer V4.1

**外贸客户AI分析系统** — 客户发现 + 客户分析 + 客户数据库 + 云共享数据 + 用户与权限管理 + 瀑布式邮箱查找 + SSE 实时流 + 地理分布地图 + Firecrawl 智能降级 + GLM 模型自动降级

自动从 Google 发现潜在客户 → AI 分析客户官网 → 规则引擎评分 → Hunter/Tomba/Prospeo 瀑布式查找关键联系人邮箱 → 生成开发切入点，一站式完成。多用户共享数据库，支持管理员对每个用户的搜索配额、搜索深度、AI分析权限、邮箱查找权限进行精细化管控。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **客户发现** | 输入国家 + 关键词 → AI扩展关键词 → SerpAPI/Tavily搜索Google → 自动过滤企业官网 |
| **Excel导入** | 上传含 Company Name / Website / Country 三列的 Excel 文件 |
| **官网抓取 V2** | 三阶段 URL 发现（33 条 HEAD 预检 + 智能链接发现 + 异步并发 GET），带 Firecrawl 三层智能降级 |
| **Firecrawl 降级** | 免费爬虫失败时自动降级到 Firecrawl（JS 渲染 / 反爬兜底）：首页GET失败→1 credit Scrape，HEAD<50%→~10 credits Crawl，内容<200字符→~10 credits Crawl |
| **邮箱提取** | 自动提取 info / sales / contact / procurement / project / marketing 前缀邮箱 |
| **关键词分析** | 14个正向 + 7个负向行业关键词命中统计（从配置文件加载，可运行时编辑） |
| **GLM AI分析** | 识别公司类型、分析原因、生成开发切入点和推荐联系职位 |
| **规则评分引擎** | 5个维度评分：行业匹配度(30) + 项目匹配度(25) + 公司类型(20) + 国家优先级(15) + 联系方式(10)，可运行时配置 |
| **Hunter 邮箱查找** | 通过 Hunter.io API 查找公司内部联系人的工作邮箱。支持域名搜索、姓名精确查找、部门/级别筛选，含5层配额优化策略（缓存优先/Count预检/自带验证/智能降级/请求间隔控制） |
| **Tomba 邮箱查找** | 通过 Tomba.io API 查找邮箱，返回数据更丰富（含领英、电话、部门、置信度评分）。无结果不扣费 |
| **Prospeo 邮箱发现** | 通过 Prospeo.io Search + Enrich API 查找邮箱（瀑布流第3级），返回人名+职位+LinkedIn+验证状态。Search 1积分/页，Enrich 1积分/邮箱，90天内重复免费 |
| **瀑布式邮箱发现** | 四级级联：Hunter → Tomba → Prospeo → 官网抓取兜底，自动按结果数量决定是否触发下一级，最大化免费额度利用率 |
| **相似客户扩展** | 输入公司网址 + 目标国家，自动搜索相似客户，支持多语言本地化搜索 |
| **客户地理分布地图** | 基于 Leaflet.js 的地图可视化：城市级定位 + MarkerCluster 聚合 + 暗色主题适配 + 国家筛选 + 批量地理编码 |
| **智能去重** | 域名 + 标准化公司名双重去重，自动合并重复发现的关键词 |
| **三级缓存** | 搜索缓存(30天) + 官网缓存(7天) + AI分析缓存(内容哈希) — 避免重复消耗 API 配额 |
| **断点续跑** | 搜索任务意外中断后，重新启动自动从断点继续 |
| **用户系统 V4.1** | 多用户登录 + 角色管理（admin/user），管理员可创建/删除用户 |
| **权限控制 V4.1** | 逐用户管理：搜索深度上限、搜索配额、AI分析开关、邮箱查找开关，管理员不受限制 |
| **批量分析** | 一键分析所有未分析客户 |
| **数据同步** | 多设备间同步数据（通过 Google Drive/AirDrop/iCloud/USB），自动去重合并 |
| **导出Excel** | 导出完整分析报告 |
| **搜索引擎切换** | 运行时一键切换 Tavily / SerpAPI 搜索后端，无需重启 |
| **GLM 模型降级** | 首选模型超时/限流/空内容时自动降级到备用模型（`glm-4.7-flash` → `glm-4-flash-250414`） |

---

## 快速开始

### 1. 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 2. 安装依赖

```bash
cd AI-Trade-Customer-Analyzer
pip install -r requirements.txt
```

### 3. 获取 API Key

#### GLM API（必填，用于 AI 分析和关键词扩展）
- 前往 https://bigmodel.cn/ 注册获取 API Key（智谱开放平台）
- 模型默认使用 `glm-4.7-flash`（免费，文本旗舰模型）
- 也兼容旧环境变量 `DEEPSEEK_API_KEY`（自动向后兼容）

#### SerpAPI（搜索发现功能必填之一）
- 前往 https://serpapi.com/ 注册获取 API Key
- 免费账户每月 250 次搜索查询

#### TAVILY（搜索发现功能必填之一）
- 前往 https://www.tavily.com/ 注册获取 API Key
- 免费账户每月 1000 次搜索查询

#### Firecrawl（可选，网站爬虫降级兜底）
- 前往 https://www.firecrawl.dev/ 注册获取 API Key
- 免费套餐每月 1000 credits，**无需绑卡**
- Scrape API：1 credit/页（`formats=["markdown"]` 成本最低）
- Crawl API：按页面数计费（~10 credits/站）
- 三层降级：仅免费爬虫失败时触发，80% 网站消耗 0 credits

#### Hunter.io（邮箱查找功能，可选）
- 前往 https://hunter.io/api-keys 注册获取 API Key
- 免费套餐每月 25 次搜索 + 50 次验证查询
- 测试时可使用 `test-api-key`（返回模拟测试数据）

#### Tomba.io（瀑布式邮箱发现第二数据源，可选）
- 前往 https://tomba.io 注册获取 API Key 和 Secret
- 免费套餐每月 25 次搜索 + 50 次验证
- 无结果不扣费，同一域名 30 天内重复查询只计一次
- 返回数据含领英链接、电话号码、部门信息、置信度评分

#### Prospeo.io（瀑布式邮箱发现第三数据源，可选）
- 前往 https://prospeo.io 注册获取 API Key
- Search Person：1 积分/页（25 人），按 20+ 维度搜索联系人
- Enrich Person：1 积分/邮箱（含个人+公司完整资料）
- 90 天内同一人重复 Enrich 免费，无结果不扣费

### 4. 配置管理员账号

系统 V4.0 起引入了用户认证。**首次启动前必须设置管理员账号**，否则系统会提示登录且无管理账号可用：

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=your-secure-password
```

> 设置后启动系统，管理员账号会自动创建。之后可通过「用户管理」页面新增普通用户，并分配各自的搜索配额和功能权限。

### 5. 启动系统

以下为完整配置示例（包含全部可选 API Key）。**必须**配置 `ADMIN_USERNAME` + `ADMIN_PASSWORD` 创建管理员账号，以及 `GLM_API_KEY` + 任一搜索引擎（`SERPAPI_API_KEY` 或 `TAVILY_API_KEY`）即可启动，其余为可选功能。旧 `DEEPSEEK_API_KEY` 环境变量会自动兼容。

**Windows (CMD):**
```cmd
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=your-secure-password
set GLM_API_KEY=your-glm-api-key
set SERPAPI_API_KEY=your-serpapi-api-key
set TAVILY_API_KEY=tvly-your-tavily-api-key
set HUNTER_API_KEY=your-hunter-api-key
set TOMBA_API_KEY=ta-your-tomba-key
set TOMBA_API_SECRET=ts-your-tomba-secret
set PROSPEO_API_KEY=your-prospeo-api-key
set FIRECRAWL_API_KEY=fc-your-firecrawl-key
python main.py
```

**macOS / Linux:**
```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=your-secure-password
export GLM_API_KEY=your-glm-api-key
export SERPAPI_API_KEY=your-serpapi-api-key
export TAVILY_API_KEY=tvly-your-tavily-api-key
export HUNTER_API_KEY=your-hunter-api-key
export TOMBA_API_KEY=ta-your-tomba-key
export TOMBA_API_SECRET=ts-your-tomba-secret
export PROSPEO_API_KEY=your-prospeo-api-key
export FIRECRAWL_API_KEY=fc-your-firecrawl-key
python main.py
```

**PowerShell:**
```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="your-secure-password"
$env:GLM_API_KEY="your-glm-api-key"
$env:SERPAPI_API_KEY="your-serpapi-api-key"
$env:TAVILY_API_KEY="tvly-your-tavily-api-key"
$env:HUNTER_API_KEY="your-hunter-api-key"
$env:TOMBA_API_KEY="ta-your-tomba-key"
$env:TOMBA_API_SECRET="ts-your-tomba-secret"
$env:PROSPEO_API_KEY="your-prospeo-api-key"
$env:FIRECRAWL_API_KEY="fc-your-firecrawl-key"
python main.py
```

**可选环境变量：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADMIN_USERNAME` | — | 管理员用户名（**必须**，V4.0 首次启动自动创建管理员） |
| `ADMIN_PASSWORD` | — | 管理员密码（**必须**） |
| `SESSION_SECRET` | `customer-analyzer-session-secret-change-me` | Session 加密密钥，生产环境务必修改为随机字符串 |
| `GLM_API_KEY` | — | 智谱 GLM API Key（必填，也兼容旧的 `DEEPSEEK_API_KEY`）|
| `GLM_API_URL` | `https://open.bigmodel.cn/api/paas/v4/chat/completions` | 自定义 API 地址 |
| `GLM_MODEL` | `glm-4.7-flash` | 首选模型名称（推荐使用免费文本旗舰模型）|
| `GLM_FALLBACK_MODELS` | `glm-4.7-flash,glm-4-flash-250414` | 模型降级列表，超时/限流/空内容时自动降级 |
| `SERPAPI_API_KEY` | — | SerpAPI 密钥（二选一） |
| `TAVILY_API_KEY` | — | Tavily 密钥（二选一） |
| `SEARCH_ENGINE` | 自动检测 | 强制指定搜索引擎：`serpapi` 或 `tavily`；运行时可通过前端切换 |
| `DATABASE_URL` | SQLite | PostgreSQL 连接字符串，如 `postgresql://user:pass@host/db` |
| `HUNTER_API_KEY` | — | Hunter.io API Key |
| `HUNTER_CACHE_TTL` | `604800` (7天) | Hunter 查询缓存 TTL |
| `HUNTER_REQUEST_DELAY` | `0.3` | Hunter API 请求间隔秒数 |
| `TOMBA_API_KEY` | — | Tomba.io API Key |
| `TOMBA_API_SECRET` | — | Tomba.io API Secret |
| `TOMBA_CACHE_TTL` | `604800` (7天) | Tomba 查询缓存 TTL |
| `PROSPEO_API_KEY` | — | Prospeo.io API Key |
| `PROSPEO_CACHE_TTL` | `604800` (7天) | Prospeo 查询缓存 TTL |
| `PROSPEO_REQUEST_DELAY` | `0.5` | Prospeo API 请求间隔秒数 |
| `FIRECRAWL_API_KEY` | — | Firecrawl API Key（免费爬虫降级兜底） |
| `EMAIL_DISCOVERY_MIN_RESULTS` | `2` | 瀑布式邮箱发现：结果数低于此值才触发下一级 |
| `EMAIL_DISCOVERY_ENABLE_SCRAPING` | `true` | 瀑布式邮箱发现：是否启用官网抓取兜底 |
| `SCRAPE_VERIFY_SSL` | `false` | 官网爬虫是否验证 SSL 证书 |

> **搜索引擎选择说明：** 系统同时支持 SerpAPI 和 Tavily 两种搜索后端。启动时按以下逻辑决定：
> 1. 如果设置了 `SEARCH_ENGINE` 环境变量（`serpapi` 或 `tavily`），则强制使用指定引擎
> 2. 未设置时，自动检测：优先使用 Tavily（如果有 `TAVILY_API_KEY`），否则使用 SerpAPI（如果有 `SERPAPI_API_KEY`）
> 3. 运行时可通过客户发现页面的搜索 API 切换器在 Tavily/SerpAPI 间一键切换，无需重启

### 6. 打开浏览器

访问 **http://localhost:8000** → 自动跳转到登录页，使用 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 登录。登录后即可使用全部功能。管理员可在导航栏「用户管理」页面新增用户、管理权限。

---

## 使用教程

### 方式零：用户管理与权限设置（V4.0+）

系统 V4.0 起引入了多用户认证和精细化权限控制：

1. **首次启动**：设置 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 环境变量，首次启动自动创建管理员
2. **登录/注册**：访问首页自动跳转登录页，管理员可在导航栏进入「用户管理」
3. **用户管理**（管理员专属）：
   - **新增用户**：创建普通用户账号
   - **修改密码**：可重置任意用户密码
   - **启用/禁用**：动态控制用户是否可登录
   - **删除用户**：支持删除用户账号（保留至少一个管理员）
4. **权限设置**（V4.1，逐用户精细管控）：
   - **搜索深度**：限制单次搜索的最大深度（默认 50）
   - **搜索配额**：限制用户总的搜索次数（默认 100 次）
   - **AI 分析开关**：控制用户能否使用 AI 分析功能
   - **邮箱查找开关**：控制用户能否使用邮箱查找功能
   - **配额重置**：一键将用户的已用搜索次数归零

> 管理员账号不受任何配额和权限限制，搜索深度上限 999。

### 方式一：手动导入客户名单

1. 点击 **导入Excel**，上传 `.xlsx` 文件（表头含 Company Name / Website / Country）
2. 在列表中点击 ⚡ 按钮分析单个客户，或点击 **批量分析** 分析所有客户
3. 等待分析完成后，查看评分和优先级

### 方式二：Google 搜索发现新客户

1. 点击导航栏 **客户发现** 进入发现页面
2. 填写：
   - **Country**：目标国家（如 Saudi Arabia）
   - **Keyword**：行业关键词（如 wastewater contractor）
   - **Search Depth**：搜索深度（每个关键词获取的结果数，建议 30-50）
3. 可选：在「预览扩展关键词」行右侧切换 **搜索 API**（Tavily / SerpAPI）
4. 点击 **Start Search**
5. 系统自动完成：AI扩展关键词 → 搜索Google → 过滤官网 → 去重 → 官网抓取（含 Firecrawl 自动降级）→ AI分析 → 规则评分 → 保存入库
6. 在 **客户列表** 页查看结果

### 查看详情

点击任意客户名称进入详情页，查看：
- **评分明细**：各维度得分及进度条
- **提取邮箱**：所有发现的邮箱地址
- **关键词分析**：正向/负向关键词命中情况
- **AI分析结果**：公司类型、分析原因、城市信息
- **开发建议**：开发切入点、推荐联系职位
- **识别项目**：AI 从官网提取的项目信息
- **官网原文**：抓取的纯文本内容

### 客户地理分布地图

导航栏点击「地图」进入可视化页面：
- **地图引擎**：Leaflet.js（免费CDN，无需 API Key）
- **城市级定位**：有城市时精确显示到城市坐标，仅国家时在国家中心加随机抖动
- **自动聚合**：MarkerCluster 自动聚合/展开，同坐标客户自动 ±0.3° 分散
- **主题适配**：自动跟随系统深色/亮色模式
- **国家筛选**：下拉框动态筛选
- **批量编码**：一键为所有未编码客户执行地理编码

### 瀑布式邮箱发现

系统提供多数据源级联邮箱查找，最大化免费额度利用率：

1. **第1级 — Hunter.io**：保留为第一优先级，直接使用已有集成
2. **第2级 — Tomba.io**：Hunter 结果不足时自动触发
3. **第3级 — Prospeo.io**：前两级均无数据时触发（Search + Enrich）
4. **第4级 — 官网抓取兜底**：从官网 HTML 提取 `mailto:` 链接

在客户详情页点击「多源查邮箱」Tab 即可使用，结果按综合得分排序（来源权重 + 验证状态 + 职位级别 + 置信度）。

### Hunter 邮箱查找

系统集成 Hunter.io API，可从客户详情页或独立页面查找公司联系人邮箱：

- **详情页集成**：进入客户详情 → 点击「Hunter 查邮箱」按钮 → 系统自动使用该公司域名查询 → 可填写联系人姓名精确查找
- **独立查找页**：导航栏点击「Hunter 邮箱」进入专用页面，直接输入域名和姓名搜索
- **查找策略（额度优化）**：
  1. **Email Count（免费）** — 先查该公司有多少邮箱，total=0 直接返回
  2. **本地缓存优先** — 结果缓存 7 天
  3. **Domain Search 自带验证** — 不额外调用 Verifier
  4. **智能降级** — 已知姓名时先在 Domain Search 结果中匹配
  5. **结果过滤** — 可按部门和级别筛选

---

## 项目结构

```
AI-Trade-Customer-Analyzer/
├── main.py                          # FastAPI 主入口（V4.1，含 Session/登录路由）
├── 产品评审报告-V2.7.md              # 产品评审报告
├── requirements.txt                 # 依赖清单（新增 bcrypt / itsdangerous）
├── sync.sh                          # 一键同步脚本
├── app/
│   ├── database.py                  # 数据库模型（13张表，含 User 表）
│   ├── database_init.py             # 数据库初始化
│   ├── auth.py                      # 认证与授权模块（V4.0/V4.1 权限检查）
│   ├── api/
│   │   ├── __init__.py              # 路由器聚合
│   │   ├── routes.py                # 兼容层
│   │   ├── customers.py             # 客户管理 API
│   │   ├── discovery.py             # 客户发现 API（含搜索引擎切换 + 配额检查）
│   │   ├── sync.py                  # 数据同步 API
│   │   ├── config.py                # 配置管理 API
│   │   ├── hunter.py                # Hunter 邮箱查找 API（含权限检查）
│   │   ├── tomba.py                 # Tomba 邮箱查找 API
│   │   ├── waterfall.py             # 瀑布式邮箱发现 API
│   │   ├── users.py                 # 用户管理 API（V4.0/V4.1 权限设置）
│   │   └── geocode.py               # 地理编码 API（后台任务模式）
│   ├── services/
│   │   ├── firecrawl_service.py     # Firecrawl 爬虫降级服务（scrape_url 单页抓取，1 credit/次）
│   │   ├── website_scraper.py       # 官网抓取 V2（多阶段 URL 发现 + Firecrawl 三层降级）
│   │   ├── email_extractor.py       # 邮箱提取
│   │   ├── keyword_analyzer.py      # 关键词分析（从配置文件加载）
│   │   ├── keyword_expander.py      # AI 关键词扩展（多语言支持，含模型降级）
│   │   ├── glm_analyzer.py          # GLM AI 分析（含重试/降级）
│   │   ├── similar_company_finder.py# 相似客户扩展（含模型降级）
│   │   ├── scoring_engine.py        # 规则评分引擎（缓存化）
│   │   ├── google_discovery.py      # SerpAPI / Tavily 搜索（运行时切换）
│   │   ├── tavily_discovery.py      # Tavily 搜索客户端
│   │   ├── search_task_service.py   # 搜索任务管理 + 断点续跑 + 任务日志
│   │   ├── cache_manager.py         # 四层缓存管理
│   │   ├── url_normalizer.py        # 网址标准化
│   │   ├── company_filter.py        # 结果过滤
│   │   ├── retry_manager.py         # 失败重试
│   │   ├── deduplication.py         # 智能去重工具
│   │   ├── country_language_map.py  # 60+ 国家语言映射表
│   │   ├── hunter_service.py        # Hunter.io API 客户端（5层配额优化）
│   │   ├── tomba_service.py         # Tomba.io API 客户端
│   │   ├── prospeo_service.py       # Prospeo.io API 客户端（Search+Enrich）
│   │   ├── waterfall_discovery.py   # 瀑布式邮箱发现编排
│   │   ├── geocoding_service.py     # 地理编码服务（Nominatim + 缓存）
│   │   ├── excel_importer.py        # Excel 导入（含去重）
│   │   ├── industry_config.json     # 行业配置中心（运行时编辑）
│   │   ├── country_weights.json     # 国家权重配置（运行时编辑）
│   │   └── site_classifier.py       # 网站分类器
│   ├── static/js/
│   │   ├── utils.js                 # 全局工具函数（_fetchWithTimeout / 防抖 / Toast）
│   │   ├── index.js                 # 客户列表页
│   │   ├── detail.js                # 客户详情页
│   │   ├── discovery.js             # 客户发现页
│   │   ├── config.js                # 评分配置页
│   │   ├── hunter.js                # Hunter 邮箱查找页
│   │   └── map.js                   # 地理分布地图页
│   ├── static/css/
│   │   └── style.css
│   └── templates/
│       ├── base.html                # 基础模板（导航栏，含登录状态）
│       ├── login.html               # 登录页（V4.0 新增）
│       ├── index.html               # 客户列表页
│       ├── detail.html              # 客户详情页（跟进/Hunter/瀑布式邮箱一体化）
│       ├── discovery.html           # 客户发现页（搜索引擎切换+相似客户）
│       ├── config.html              # 评分系统配置页
│       ├── hunter.html              # Hunter 邮箱查找页
│       ├── map.html                 # 地理分布地图页
│       ├── sync.html                # 数据同步页面
│       └── users.html               # 用户管理页（V4.0 新增）
```

---

## 数据库表

| 表名 | 说明 |
|------|------|
| `customers` | 客户数据（含评分、AI分析、发现来源、跟进状态、地理编码） |
| `search_tasks` | 搜索任务（支持断点续跑 + 任务日志） |
| `search_cache` | 搜索结果缓存（30天有效） |
| `website_cache` | 官网抓取缓存（7天有效，含 content_hash） |
| `analysis_cache` | AI 分析缓存（内容哈希比对） |
| `hunter_cache` | Hunter 邮箱查询缓存（7天有效，自动记录命中次数） |
| `tomba_cache` | Tomba 邮箱查询缓存（7天有效） |
| `prospeo_cache` | Prospeo Search+Enrich 缓存（7天有效，含 person_id） |
| `email_quota_log` | 邮箱发现配额使用日志（持久化记录各平台消耗） |
| `geocode_cache` | 地理编码结果缓存（UNIQUE query_key + 命中计数） |
| `users` | 用户表（V4.0 新增：用户名/密码哈希/角色/权限字段/配额字段） |

---

## 评分系统说明

系统采用 **规则评分引擎**，AI 仅负责信息提取，评分完全由程序计算：

| 维度 | 满分 | 说明 |
|------|------|------|
| 行业匹配度 | 30 | 官网命中行业关键词的数量和权重（从配置文件加载，可运行时编辑） |
| 项目匹配度 | 25 | 是否有项目案例页面、是否涉足目标行业（标签可配置） |
| 公司类型 | 20 | EPC=20, Contractor=18, 生产商=12...（可运行时编辑） |
| 国家优先级 | 15 | 从 `country_weights.json` 读取（可运行时编辑） |
| 联系方式 | 10 | 1个邮箱=3分, 2个=5分, 3个=8分, 4个+=10分 |

优先级：A(80-100) / B(60-79) / C(40-59) / D(0-39)

评分规则可通过网页「评分配置」页面或直接编辑 `app/services/industry_config.json` 调整。项目匹配的检测关键词和提示文字均已外置到配置文件，切换行业（如从水处理改为光伏）仅需修改配置，无需改动代码。

---

## 多设备数据同步（通过 Google Drive 网页版）

支持在多个设备间同步客户数据，**不需要安装 Google Drive 客户端**，通过网页版上传/下载即可。

### 使用方式

**设备 A（导出数据）：**
```bash
# 1. 导出数据到桌面（生成 trade_data_export.json）
./sync.sh export ~/Desktop/TradeDataSync

# 2. 打开 https://drive.google.com，把该文件上传到 Google Drive
```

**设备 B（导入数据）：**
```bash
# 1. 从 Google Drive 下载 trade_data_export.json 到本地

# 2. 假设下载到 ~/Downloads/TradeDataSync/
./sync.sh import ~/Downloads/TradeDataSync
```

### 同步内容

支持同步客户数据 + 搜索缓存 + 官网抓取缓存 + AI 分析缓存，导入后自动去重合并，无需重复消耗 API 配额。

### 替代传输方式

如果不想用 Google Drive，也可以用：
- **AirDrop**：`./sync.sh export ~/Desktop/TradeDataSync` → AirDrop 文件到另一台 Mac
- **USB**：`./sync.sh export /Volumes/USB/TradeData`
- **iCloud**：`./sync.sh export ~/Library/Mobile\ Documents/com~apple~CloudDocs/TradeData`

---

## 运行测试

```bash
source venv/bin/activate
pytest tests/ -v     # 129+ 测试，详细输出
pytest tests/ -q     # 简洁输出
```

---

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite/PostgreSQL
- **前端**：Bootstrap 5 + JavaScript 模块化（utils/index/detail/discovery/config/hunter/map）
- **AI**：智谱 GLM (`glm-4.7-flash` 免费文本旗舰模型，支持自动降级到 `glm-4-flash-250414`)
- **搜索**：SerpAPI / Tavily（运行时一键切换）
- **邮箱**：Hunter.io + Tomba.io + Prospeo.io + 官网抓取兜底（瀑布式四级级联）
- **爬虫**：httpx + BeautifulSoup（异步并发，多阶段 URL 发现）
- **爬虫降级**：Firecrawl（三层兜底，JS 渲染/反爬网站兜底，免费 1000 credits/月）
- **地图**：Leaflet.js + MarkerCluster + Nominatim 地理编码
- **缓存**：本地 SQLite 多级缓存（搜索/官网/AI分析/邮箱/地理编码）
- **认证**：Session + bcrypt 密码哈希（V4.0 多用户 / V4.1 精细权限控制）
- **测试**：pytest（API 集成测试 + 纯逻辑模块测试）
