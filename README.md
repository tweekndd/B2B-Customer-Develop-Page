# AI Trade Customer Analyzer V3.2.2

**外贸客户AI分析系统** — 客户发现 + 客户分析 + 客户数据库 + 瀑布式邮箱查找 + SSE 实时流

自动从 Google 发现潜在客户 → AI 分析客户官网 → 规则引擎评分 → Hunter 查找关键联系人邮箱 → 生成开发切入点，一站式完成。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **客户发现** | 输入国家 + 关键词 → AI扩展关键词 → SerpAPI搜索Google → 自动过滤企业官网 |
| **Excel导入** | 上传含 Company Name / Website / Country 三列的 Excel 文件 |
| **官网抓取** | 异步并发抓取 /about /services /projects 等页面，提取纯文本 |
| **邮箱提取** | 自动提取 info / sales / contact / procurement / project / marketing 前缀邮箱 |
| **关键词分析** | 14个正向 + 7个负向行业关键词命中统计 |
| **DeepSeek AI分析** | 识别公司类型、分析原因、生成开发切入点和推荐联系职位 |
| **规则评分引擎** | 5个维度评分：行业匹配度(30) + 项目匹配度(25) + 公司类型(20) + 国家优先级(15) + 联系方式(10) |
| **Prospeo 邮箱发现** | 通过 Prospeo.io Search + Enrich API 查找邮箱（瀑布流第3级），返回人名+职位+LinkedIn+验证状态。Search 1积分/页，Enrich 1积分/邮箱，90天内重复免费 |
| **相似客户扩展** | 输入公司网址 + 目标国家，自动搜索相似客户，支持多语言本地化搜索 |
| **Hunter 邮箱查找** | 通过 Hunter.io API 查找公司内部联系人的工作邮箱。支持域名搜索、姓名精确查找、部门/级别筛选，含本地缓存层和额度优化策略 |
| **Tomba 邮箱查找** | 通过 Tomba.io API 查找邮箱，返回数据更丰富（含领英、电话、部门、置信度评分）。无结果不扣费 |
| **瀑布式邮箱发现** | 四级级联：Hunter → Tomba → Prospeo → 官网抓取兜底，自动按结果数量决定是否触发下一级，最大化免费额度利用率 |
| **智能去重** | 域名 + 标准化公司名双重去重，自动合并重复发现的关键词 |
| **三级缓存** | 搜索缓存(30天) + 官网缓存(7天) + AI分析缓存(内容哈希) — 避免重复消耗 API 配额 |
| **断点续跑** | 搜索任务意外中断后，重新启动自动从断点继续 |
| **批量分析** | 一键分析所有未分析客户 |
| **数据同步** | 多设备间同步数据（通过 iCloud/Dropbox/USB），自动去重合并 |
| **导出Excel** | 导出完整分析报告 |
| **停止分析** | 随时点击停止按钮中止分析任务 |

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

#### DeepSeek API（必填，用于 AI 分析和关键词扩展）
- 前往 https://platform.deepseek.com/ 注册获取 API Key
- 模型默认使用 `deepseek-v4-flash`

#### SerpAPI（搜索发现功能必填）
- 前往 https://serpapi.com/ 注册获取 API Key
- 免费账户每月 250 次搜索查询

#### TAVILY（搜索发现功能必填）
- 前往https://www.tavily.com/)](https://www.tavily.com/) 注册获取 API Key
- 免费账户每月 1000 次搜索查询

#### Hunter.io（邮箱查找功能，可选）
- 前往 https://hunter.io/api-keys 注册获取 API Key
- 免费套餐每月 25 次搜索 + 50 次验证查询
- 测试时可使用 `test-api-key`（返回模拟测试数据）

#### Tomba.io（瀑布式邮箱发现第二数据源，可选）
- 前往 https://tomba.io 注册获取 API Key 和 Secret
- 免费套餐每月 25 次搜索 + 50 次验证
- 无结果不扣费，同一域名 30 天内重复查询只计一次
- 返回数据含领英链接、电话号码、部门信息、置信度评分，比 Hunter 更丰富

#### Prospeo.io（瀑布式邮箱发现第三数据源，可选）
- 前往 https://prospeo.io 注册获取 API Key
- Search Person：1 积分/页（25 人），按 20+ 维度搜索联系人（不含邮箱，需 Enrich 补全）
- Enrich Person：1 积分/邮箱（含个人+公司完整资料），10 积分/手机号
- 90 天内同一人重复 Enrich 免费，无结果不扣费
- 返回数据最丰富：姓名、职位、完整工作经历、LinkedIn、技术栈、公司收入/融资/规模
  
### 4. 启动系统

以下为完整配置示例（包含全部可选 API Key）。最少只需配置 `DEEPSEEK_API_KEY` + 任一搜索引擎（`SERPAPI_API_KEY` 或 `TAVILY_API_KEY`）即可启动，其余为可选功能。

**Windows (CMD):**
```cmd
set DEEPSEEK_API_KEY=sk-your-deepseek-api-key
set SERPAPI_API_KEY=your-serpapi-api-key
set TAVILY_API_KEY=tvly-your-tavily-api-key
set HUNTER_API_KEY=your-hunter-api-key
set TOMBA_API_KEY=ta-your-tomba-key
set TOMBA_API_SECRET=ts-your-tomba-secret
set PROSPEO_API_KEY=your-prospeo-api-key
python main.py
```

**macOS / Linux:**
```bash
export DEEPSEEK_API_KEY=sk-your-deepseek-api-key
export SERPAPI_API_KEY=your-serpapi-api-key
export TAVILY_API_KEY=tvly-your-tavily-api-key
export HUNTER_API_KEY=your-hunter-api-key
export TOMBA_API_KEY=ta-your-tomba-key
export TOMBA_API_SECRET=ts-your-tomba-secret
export PROSPEO_API_KEY=your-prospeo-api-key
python main.py
```

**PowerShell:**
```powershell
$env:DEEPSEEK_API_KEY="sk-your-deepseek-api-key"
$env:SERPAPI_API_KEY="your-serpapi-api-key"
$env:TAVILY_API_KEY="tvly-your-tavily-api-key"
$env:HUNTER_API_KEY="your-hunter-api-key"
$env:TOMBA_API_KEY="ta-your-tomba-key"
$env:TOMBA_API_SECRET="ts-your-tomba-secret"
$env:PROSPEO_API_KEY="your-prospeo-api-key"
python main.py
```

**可选环境变量：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_URL` | `https://api.deepseek.com/v1/chat/completions` | 自定义 API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 自定义模型名称 |
| `SERPAPI_API_KEY` | — | SerpAPI 密钥（二选一） |
| `TAVILY_API_KEY` | — | Tavily 密钥（二选一） |
| `SEARCH_ENGINE` | 自动检测 | 强制指定搜索引擎：`serpapi` 或 `tavily`。未设置时，自动根据已配置的 API Key 决定 |
| `DATABASE_URL` | SQLite | PostgreSQL 连接字符串，如 `postgresql://user:pass@host/db` |
| `HUNTER_API_KEY` | — | Hunter.io API Key。配置后在页面显示"已配置"，可使用邮箱查找功能 |
| `HUNTER_CACHE_TTL` | `604800` (7天) | Hunter 查询结果在本地缓存的秒数 |
| `HUNTER_REQUEST_DELAY` | `0.3` | Hunter API 请求间隔秒数，避免触发速率限制 |
| `TOMBA_API_KEY` | — | Tomba.io API Key（瀑布式查找第二数据源） |
| `TOMBA_API_SECRET` | — | Tomba.io API Secret（与 Key 配对使用） |
| `TOMBA_CACHE_TTL` | `604800` (7天) | Tomba 查询结果在本地缓存的秒数 |
| `PROSPEO_API_KEY` | — | Prospeo.io API Key（瀑布式查找第三数据源） |
| `PROSPEO_CACHE_TTL` | `604800` (7天) | Prospeo 查询结果在本地缓存的秒数 |
| `PROSPEO_REQUEST_DELAY` | `0.5` | Prospeo API 请求间隔秒数，避免触发速率限制 |
| `EMAIL_DISCOVERY_MIN_RESULTS` | `2` | 瀑布式邮箱发现：结果数低于此值才触发下一级 |
| `EMAIL_DISCOVERY_ENABLE_SCRAPING` | `true` | 瀑布式邮箱发现：是否启用官网抓取兜底 |

> **搜索引擎选择说明：** 系统同时支持 SerpAPI 和 Tavily 两种搜索后端。启动时按以下逻辑决定：
> 1. 如果设置了 `SEARCH_ENGINE` 环境变量（`serpapi` 或 `tavily`），则强制使用指定引擎
> 2. 未设置时，自动检测：优先使用 Tavily（如果有 `TAVILY_API_KEY`），否则使用 SerpAPI（如果有 `SERPAPI_API_KEY`）

### 5. 打开浏览器

访问 **http://localhost:8000**

---

## 使用教程

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
3. 点击 **Start Search**
4. 系统自动完成：AI扩展关键词 → 搜索Google → 过滤官网 → 去重 → 官网抓取 → AI分析 → 规则评分 → 保存入库
5. 在 **客户列表** 页查看结果

### 查看详情

点击任意客户名称进入详情页，查看：
- **评分明细**：各维度得分及进度条
- **提取邮箱**：所有发现的邮箱地址
- **关键词分析**：正向/负向关键词命中情况
- **AI分析结果**：公司类型、分析原因
- **开发建议**：开发切入点、推荐联系职位
- **识别项目**：AI 从官网提取的项目信息
- **官网原文**：抓取的纯文本内容

### Hunter 邮箱查找

系统集成 Hunter.io API，可从客户详情页或独立页面查找公司联系人邮箱：

- **详情页集成**：进入客户详情 → 点击「Hunter 查邮箱」按钮 → 系统自动使用该公司域名查询 → 可填写联系人姓名精确查找
- **独立查找页**：导航栏点击「Hunter 邮箱」进入专用页面，直接输入域名和姓名搜索
- **查找策略（额度优化）**：
  1. **Email Count（免费）** — 先查该公司有多少邮箱，total=0 直接返回，不消耗搜索额度
  2. **本地缓存优先** — 结果缓存 7 天，相同查询直接从缓存读取
  3. **Domain Search 自带验证** — 不额外调用 Verifier 消耗验证额度
  4. **智能降级** — 已知姓名时先在 Domain Search 结果中匹配，找不到才触发 Email Finder
  5. **结果过滤** — 可按部门（高管/技术/销售/市场等）和级别（初级/高级/高管）筛选

> **注意：** 使用前需设置 `HUNTER_API_KEY` 环境变量。免费套餐每月 25 次搜索查询。

### 瀑布式邮箱发现（Phase 1）

系统提供多数据源级联邮箱查找，最大化免费额度利用率：

1. **第1级 — Hunter.io**：保留为第一优先级，直接使用已有集成
2. **第2级 — Tomba.io**：Hunter 结果不足时自动触发，返回数据含领英、电话、部门，无结果不扣费
3. **第3级 — 官网抓取兜底**：前两级均无数据时，从官网 HTML 提取 `mailto:` 链接

在客户详情页点击「多源查邮箱」Tab 即可使用，结果按综合得分排序（来源权重 + 验证状态 + 职位级别 + 置信度）。

> **配置：** 需设置 `TOMBA_API_KEY` 和 `TOMBA_API_SECRET` 环境变量启用 Tomba 数据源。自研抓取默认开启，可通过 `EMAIL_DISCOVERY_ENABLE_SCRAPING=false` 关闭。

---

## 项目结构

```
AI-Trade-Customer-Analyzer/
├── main.py                          # FastAPI 主入口（V3.2.2）
├── 产品评审报告-V2.7.md              # 产品评审报告
├── requirements.txt                 # 依赖清单
├── app/
│   ├── database.py                  # 数据库模型（10张表，含 ProspeoCache）
│   ├── database_init.py             # 数据库初始化
│   ├── api/
│   │   ├── __init__.py              # 路由器聚合（V3.2.2 含 Prospeo/瀑布式路由）
│   │   ├── routes.py                # 兼容层
│   │   ├── customers.py             # 客户管理 API
│   │   ├── discovery.py             # 客户发现 API
│   │   ├── sync.py                  # 数据同步 API
│   │   ├── config.py                # 配置管理 API
│   │   ├── hunter.py                # Hunter 邮箱查找 API
│   │   ├── tomba.py                 # Tomba 邮箱查找 API
│   │   └── waterfall.py             # 瀑布式邮箱发现 API（含 Prospeo 状态）
│   ├── services/
│   │   ├── excel_importer.py        # Excel 导入
│   │   ├── website_scraper.py       # 官网抓取（异步）
│   │   ├── email_extractor.py       # 邮箱提取
│   │   ├── keyword_analyzer.py      # 关键词分析
│   │   ├── keyword_expander.py      # AI 关键词扩展
│   │   ├── deepseek_analyzer.py     # DeepSeek AI 分析
│   │   ├── scoring_engine.py        # 规则评分引擎
│   │   ├── google_discovery.py      # SerpAPI / Tavily 搜索
│   │   ├── search_task_service.py   # 搜索任务管理 + 断点续跑
│   │   ├── cache_manager.py         # 四层缓存管理（含 Prospeo）
│   │   ├── url_normalizer.py        # 网址标准化
│   │   ├── company_filter.py        # 结果过滤
│   │   ├── retry_manager.py         # 失败重试
│   │   ├── similar_company_finder.py# 相似客户扩展
│   │   ├── deduplication.py         # 智能去重工具
│   │   ├── hunter_service.py        # Hunter.io API 客户端
│   │   ├── tomba_service.py         # Tomba.io API 客户端
│   │   ├── prospeo_service.py       # Prospeo.io API 客户端（Search+Enrich）
│   │   ├── waterfall_discovery.py   # 瀑布式邮箱发现编排
│   │   ├── industry_config.json     # 行业配置中心
│   │   └── country_weights.json     # 国家权重配置
│   ├── static/css/
│   │   └── style.css
│   └── templates/
│       ├── index.html               # 客户列表页
│       ├── detail.html              # 客户详情页（含 Hunter 邮箱查找）
│       ├── discovery.html           # 客户发现页
│       ├── config.html              # 评分系统配置页
│       └── hunter.html              # Hunter 邮箱查找页
```

---

## 数据库表

| 表名 | 说明 |
|------|------|
| `customers` | 客户数据（含评分、AI分析、发现来源） |
| `search_tasks` | 搜索任务（支持断点续跑） |
| `search_cache` | 搜索结果缓存（30天有效） |
| `website_cache` | 官网抓取缓存（7天有效） |
| `analysis_cache` | AI 分析缓存（内容哈希比对） |
| `hunter_cache` | Hunter 邮箱查询缓存（7天有效，自动记录命中次数） |
| `tomba_cache` | Tomba 邮箱查询缓存（7天有效） |
| `prospeo_cache` | Prospeo Search+Enrich 缓存（7天有效，含 person_id） |
| `email_quota_log` | 邮箱发现配额使用日志（持久化记录各平台消耗） |

---

## 评分系统说明

系统采用 **规则评分引擎**，AI 仅负责信息提取，评分完全由程序计算：

| 维度 | 满分 | 说明 |
|------|------|------|
| 行业匹配度 | 30 | 官网命中行业关键词的数量和权重 |
| 项目匹配度 | 25 | 是否有项目案例页面、是否涉足目标行业 |
| 公司类型 | 20 | EPC=20, Contractor=18, 生产商=12... |
| 国家优先级 | 15 | 从 `country_weights.json` 读取（可配置） |
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
pytest tests/ -v     # 129个测试，详细输出
pytest tests/ -q     # 简洁输出
```

---

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite
- **前端**：Bootstrap 5 + JavaScript
- **AI**：DeepSeek API
- **搜索**：SerpAPI / Tavily
- **邮箱**：Hunter.io + Tomba.io 双数据源 + 官网抓取兜底（瀑布式三级级联）
- **爬虫**：httpx + BeautifulSoup（异步并发）
