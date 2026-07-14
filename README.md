<div align="center">

# AI Customer Development System

**外贸客户 AI 分析系统** — 客户发现 + AI 分析 + 瀑布式邮箱 + 地理地图 + 权限管控

一站式完成全球 B2B 销售线索挖掘。

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)]()
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)]()

> 🖥️ [**在线预览**](https://tweekndd.github.io/B2B-Customer-Develop-Page/) · 项目介绍落地页 `index.html`

</div>

---

## 📋 目录

- [功能概览](#-功能概览)
- [快速开始](#-快速开始)
- [使用教程](#-使用教程)
- [SearXNG 部署](#-searxng-自托管搜索引擎小白教程)
- [VPS 部署](#%EF%B8%8F-vps-部署生产环境)
- [项目结构](#-项目结构)
- [数据库表](#-数据库表)
- [评分系统](#-评分系统说明)
- [技术栈](#-技术栈)
- [测试](#-运行测试)

---

## 🚀 功能概览

自动通过 SearXNG（自托管无限制）/ Tavily / SerpAPI 发现潜在客户 → AI 分析客户官网 → 规则引擎评分 → Hunter/Tomba/Prospeo 瀑布式查找关键联系人邮箱 → 生成开发切入点，一站式完成。爬虫降级使用 Jina AI Reader（`r.jina.ai`）**完全免费、无需 API Key**。搜索引擎可选 SearXNG 自托管零成本方案。多用户共享数据库，支持管理员对每个用户的搜索配额、搜索深度、AI 分析权限、邮箱查找权限进行精细化管控。

| 功能 | 说明 |
|------|------|
| **客户发现** | 输入国家 + 关键词 → AI 扩展关键词 → SearXNG/Tavily/SerpAPI 搜索 → 自动过滤企业官网 |
| **Excel 导入** | 上传含 Company Name / Website / Country 三列的 Excel 文件 |
| **官网抓取 V2** | 三阶段 URL 发现（33 条 HEAD 预检 + 智能链接发现 + 异步并发 GET），Jina AI Reader 免费降级兜底 |
| **Reader 爬虫降级** | 三层降级统一使用免费的 r.jina.ai API，零成本无需 API Key。支持 JS 渲染兜底，可自托管 Docker 镜像 |
| **邮箱提取** | 自动提取 info / sales / contact / procurement / project / marketing 前缀邮箱 |
| **关键词分析** | 14 个正向 + 7 个负向行业关键词命中统计（从配置文件加载，可运行时编辑） |
| **GLM AI 分析** | 识别公司类型、分析原因、生成开发切入点和推荐联系职位，支持模型自动降级 |
| **规则评分引擎** | 5 个维度评分：行业匹配度(30) + 项目匹配度(25) + 公司类型(20) + 国家优先级(15) + 联系方式(10)，可运行时配置 |
| **Hunter 邮箱查找** | Hunter.io API，支持域名搜索、姓名精确查找、部门/级别筛选，5 层配额优化策略 |
| **Tomba 邮箱查找** | Tomba.io API，返回数据更丰富（含领英、电话、部门、置信度评分），无结果不扣费 |
| **Prospeo 邮箱发现** | Prospeo.io Search + Enrich API，瀑布流第 3 级，90 天内重复免费 |
| **瀑布式邮箱发现** | 四级级联：Hunter → Tomba → Prospeo → 官网抓取兜底，自动按结果数量决定是否触发下一级 |
| **相似客户扩展** | 输入公司网址 + 目标国家，自动搜索相似客户，支持多语言本地化搜索 |
| **客户地理分布地图** | Leaflet.js 地图可视化：城市级定位 + MarkerCluster 聚合 + 暗色/亮色主题自适应 |
| **智能去重** | 域名 + 标准化公司名双重去重，自动合并重复发现的关键词 |
| **三级缓存** | 搜索缓存(30天) + 官网缓存(7天) + AI 分析缓存(内容哈希) |
| **断点续跑** | 搜索任务意外中断后，重新启动自动从断点继续 |
| **用户系统 V4.1** | 多用户登录 + 角色管理（admin/user），管理员可创建/删除用户 |
| **权限控制 V4.1** | 逐用户管理：搜索深度上限、搜索配额、AI 分析开关、邮箱查找开关 |
| **批量分析** | 一键分析所有未分析客户 |
| **数据同步** | 多设备间同步数据（Google Drive / AirDrop / iCloud / USB），自动去重合并 |
| **搜索引擎切换** | 运行时一键切换 SearXNG（免费）/ Tavily / SerpAPI，无需重启 |
| **GLM 模型降级** | 首选模型超时/限流/空内容时自动降级到备用模型（`glm-4.7-flash` → `glm-4-flash-250414`） |

---

## ⚡ 快速开始

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

> **Windows 用户**：从 [python.org](https://www.python.org/downloads/) 下载安装时，**务必勾选** ✅ **Add Python to PATH**，否则 `python` 命令无法在 CMD 中识别。
> 安装后在 CMD / PowerShell 中运行 `python --version` 验证。

### 1. 安装依赖

```bash
git clone https://github.com/tweekndd/B2B-Customer-Develop-Page.git
cd B2B-Customer-Develop-Page
pip install -r requirements.txt
```

### 2. 获取 API Key

| 服务 | 用途 | 费用 | 获取地址 |
|------|------|------|----------|
| **GLM API** | AI 分析 & 关键词扩展 | ✅ 免费 | https://bigmodel.cn/ |
| **SearXNG** | 搜索引擎（自托管） | ✅ 免费 | Docker 一键部署，见下方教程 |
| **Tavily** | 搜索引擎（可选） | 付费 | https://tavily.com/ |
| **SerpAPI** | 搜索引擎（可选） | 付费 | https://serpapi.com/ |
| **Hunter.io** | 邮箱查找（可选） | 免费层 25次/月 | https://hunter.io/ |
| **Tomba.io** | 邮箱查找（可选） | 免费层 25次/月 | https://tomba.io/ |
| **Prospeo.io** | 邮箱查找（可选） | 免费层积分制 | https://prospeo.io/ |

> **零成本运行方案**：只需配置 `GLM_API_KEY`（免费）+ SearXNG 自托管（免费）→ 零 API 费用。
> 旧 `DEEPSEEK_API_KEY` 环境变量自动兼容。

### 3. 配置环境变量并启动

选择合适的终端，按你的操作系统设置环境变量后启动：

<details open>
<summary><b>🐚 Linux / macOS (bash/zsh)</b></summary>

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=your-secure-password
export GLM_API_KEY=your-glm-api-key
# 可选搜索引擎 Key（不设则自动检测 SearXNG / Tavily / SerpAPI）
export SEARXNG_URL=http://127.0.0.1:8888
# 或 export TAVILY_API_KEY=tvly-xxx
# 或 export SERPAPI_API_KEY=xxx
# 可选邮箱查找
export HUNTER_API_KEY=your-hunter-key
export TOMBA_API_KEY=ta-your-tomba-key
export TOMBA_API_SECRET=ts-your-tomba-secret
export PROSPEO_API_KEY=your-prospeo-key

python main.py
```

> 每次打开新终端都要重新设置，建议写入 `~/.bashrc` 或使用 `.env` 文件。
</details>

<details>
<summary><b>🪟 Windows (CMD)</b></summary>

```cmd
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=your-secure-password
set GLM_API_KEY=your-glm-api-key
set SEARXNG_URL=http://127.0.0.1:8888
set TAVILY_API_KEY=tvly-xxx
set SERPAPI_API_KEY=xxx
set HUNTER_API_KEY=your-hunter-key
set TOMBA_API_KEY=ta-your-tomba-key
set TOMBA_API_SECRET=ts-your-tomba-secret
set PROSPEO_API_KEY=your-prospeo-key

python main.py
```

> **注意**：CMD 使用 `set` 而非 `export`，`set` 后**不能有空格**（`set KEY=value` ✅，`set KEY = value` ❌）。
> 每次打开新 CMD 窗口都需要重新设置。
</details>

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="your-secure-password"
$env:GLM_API_KEY="your-glm-api-key"
$env:SEARXNG_URL="http://127.0.0.1:8888"
$env:TAVILY_API_KEY="tvly-xxx"
$env:SERPAPI_API_KEY="xxx"
$env:HUNTER_API_KEY="your-hunter-key"
$env:TOMBA_API_KEY="ta-your-tomba-key"
$env:TOMBA_API_SECRET="ts-your-tomba-secret"
$env:PROSPEO_API_KEY="your-prospeo-key"

python main.py
```

> **注意**：PowerShell 使用 `$env:` 前缀 + `"双引号"` 包裹值，与 CMD 完全不同。
> 每次打开新 PowerShell 窗口都需要重新设置。
</details>

<details>
<summary><b>🪟 Windows (Git Bash)</b></summary>

```bash
# Git Bash 中使用 export（与 Linux 语法一致）
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=your-secure-password
export GLM_API_KEY=your-glm-api-key
export SEARXNG_URL=http://127.0.0.1:8888
export TAVILY_API_KEY=tvly-xxx
export SERPAPI_API_KEY=xxx

python main.py
```

> Git Bash 的语法与 Linux/macOS 完全相同，推荐 Windows 用户使用。
</details>

### 4. 使用 `.env` 文件（推荐，所有平台通用）

将 `.env.example` 复制为 `.env`，填写配置后即可自动加载，**无需每次手动设置环境变量**：

```bash
cp .env.example .env
# 然后用记事本/VSCode 编辑 .env 文件
```

系统启动时自动读取 `.env` 文件中的配置。支持所有平台（Windows / macOS / Linux）。

### 5. 访问系统

启动成功后，浏览器打开 **http://localhost:8000** → 自动跳转登录页，使用管理员账号登录。

### 6. 完整环境变量表

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADMIN_USERNAME` | — | 管理员用户名（必须） |
| `ADMIN_PASSWORD` | — | 管理员密码（必须） |
| `SESSION_SECRET` | `customer-analyzer-session-secret-change-me` | Session 加密密钥 |
| `GLM_API_KEY` | — | 智谱 GLM API Key（也兼容 `DEEPSEEK_API_KEY`） |
| `GLM_MODEL` | `glm-4.7-flash` | 首选模型（免费文本旗舰） |
| `GLM_FALLBACK_MODELS` | `glm-4.7-flash,glm-4-flash-250414` | 模型降级列表 |
| `SEARXNG_URL` | `http://127.0.0.1:8888` | SearXNG 实例地址（推荐，零成本） |
| `SERPAPI_API_KEY` | — | SerpAPI 密钥 |
| `TAVILY_API_KEY` | — | Tavily 密钥 |
| `SEARCH_ENGINE` | 自动检测 | 强制指定搜索引擎 `searxng`/`serpapi`/`tavily` |
| `DATABASE_URL` | SQLite | PostgreSQL 连接字符串 |
| `HUNTER_API_KEY` | — | Hunter.io API Key |
| `TOMBA_API_KEY` | — | Tomba.io API Key |
| `TOMBA_API_SECRET` | — | Tomba.io API Secret |
| `PROSPEO_API_KEY` | — | Prospeo.io API Key |
| `READER_BASE_URL` | `https://r.jina.ai` | Jina AI Reader API 地址 |
| `FIRECRAWL_API_KEY` | — | （可选旧版兜底） |
| `EMAIL_DISCOVERY_MIN_RESULTS` | `2` | 瀑布流结果低于此值触发下一级 |
| `SCRAPE_VERIFY_SSL` | `false` | 爬虫是否验证 SSL 证书 |

> **搜索引擎选择说明**：支持 SearXNG/SerpAPI/Tavily 三种后端。启动时自动检测：优先 SearXNG（有 `SEARXNG_URL`）→ 其次 Tavily → 最后 SerpAPI。运行时可通过客户发现页面一键切换，无需重启。
>
> **Windows 环境变量注意事项**：
> - **CMD**：使用 `set KEY=value`，等号两边**不能有空格**
> - **PowerShell**：使用 `$env:KEY="value"`，值必须用**双引号**包裹
> - **Git Bash**：语法与 Linux 完全一致（`export KEY=value`）
> - **`.env` 文件**：所有平台通用，推荐使用（从 `.env.example` 复制）

---

## 📖 使用教程

### 用户管理与权限设置（V4.0+）

1. **首次启动**：设置 `ADMIN_USERNAME` / `ADMIN_PASSWORD`，自动创建管理员
2. **用户管理**（管理员专属）：新增用户、修改密码、启用/禁用、删除用户
3. **权限设置**（V4.1，逐用户管控）：
   - 搜索深度、搜索配额上限
   - AI 分析开关、邮箱查找开关
   - 管理员不受任何限制

### 手动导入客户

上传含 Company Name / Website / Country 三列的 `.xlsx` 文件 → 列表中点 ⚡ 单个分析或「批量分析」→ 查看评分和优先级。

### 搜索发现客户

1. 导航栏 → **客户发现**
2. 填写国家（如 Saudi Arabia）、行业关键词（如 wastewater contractor）、搜索深度
3. 可选切换搜索引擎
4. 点击 **Start Search** → 系统自动完成全流程
5. **客户列表** 页查看结果

### 客户详情页

点击客户名称进入详情，查看：
- 评分明细 · 提取邮箱 · 关键词分析 · AI 分析结果 · 开发建议 · 官网原文
- 瀑布式邮箱发现（多源级联查找）
- 跟进状态管理 + 客户评级

### 客户地理分布地图

导航栏 → **地图**：Leaflet.js 免费地图，城市级定位，MarkerCluster 聚合，深色/亮色自动适配。

---

## 🔍 SearXNG 自托管搜索引擎（小白教程）

### 一句话

SearXNG 是一个在你电脑上运行的"搜索中转站"，替你向 Google/Bing 等引擎发请求，**无需 API Key、零成本、无搜索次数限制**。

### 一键启动（需安装 Docker）

**Windows (CMD / PowerShell / Git Bash 通用):**
```bash
docker run -d --name searxng -p 127.0.0.1:8888:8080 searxng/searxng:latest
```

> 📥 **安装 Docker Desktop (Windows / Mac)**：https://docs.docker.com/desktop/setup/install/windows-install/
> - Windows 用户安装后启动 **Docker Desktop**，等待底部状态栏出现小鲸鱼图标 ✅
> - 然后在 **CMD / PowerShell / Git Bash** 中运行上述命令

### 启用 JSON API（必须）

使用项目自带的配置（推荐，`docker-compose` 自动加载），或手动编辑：

<details>
<summary><b>🐧 Linux / Mac 进入容器编辑</b></summary>

```bash
docker exec -it searxng bash
apt-get update && apt-get install -y nano
nano /etc/searxng/settings.yml
# 在 search.formats 中添加:
#   - json
# Ctrl+X → Y → 回车保存
docker restart searxng
```
</details>

<details>
<summary><b>🪟 Windows (PowerShell) 进入容器编辑</b></summary>

```powershell
# PowerShell 中进入容器
docker exec -it searxng bash
apt-get update && apt-get install -y nano
nano /etc/searxng/settings.yml
# 在 search.formats 中添加:
#   - json
# Ctrl+X → Y → 回车保存
docker restart searxng
```
</details>

### 验证

<details>
<summary><b>🐧 Linux / Mac</b></summary>

```bash
curl "http://127.0.0.1:8888/search?q=test&format=json"
```
</details>

<details>
<summary><b>🪟 Windows (CMD / PowerShell)</b></summary>

```powershell
# PowerShell (推荐)
curl.exe "http://127.0.0.1:8888/search?q=test&format=json"

# CMD（Windows 10 1803+ 自带 curl）
curl "http://127.0.0.1:8888/search?q=test&format=json"
```

> 💡 PowerShell 的 `curl` 是 `Invoke-WebRequest` 别名，需用 `curl.exe` 调用真正的 curl。
> 如果都没有 curl，直接浏览器打开 `http://127.0.0.1:8888/search?q=test&format=json` 也能验证。
</details>

正常应返回带 `"results"` 的 JSON 文本 ✅

### 日常维护

| 操作 | 命令 |
|------|------|
| 启动 | `docker start searxng` |
| 停止 | `docker stop searxng` |
| 查看状态 | `docker ps` |
| 更新 | `docker pull searxng/searxng:latest && docker restart searxng` |
| 重装 | `docker rm -f searxng` 然后重新 `docker run` |

> **没有 Docker？** 可临时使用公共实例 `SEARXNG_URL=https://searx.be` 测试（可能限流）。

---

## 🖥️ VPS 部署（生产环境）

> 把系统部署到公网服务器，团队 7×24 共享使用。

### 推荐配置

| 配置项 | 最低 | 推荐 |
|--------|------|------|
| CPU | 1核 | 2核+ |
| 内存 | 2GB | 4GB |
| 硬盘 | 20GB | 40GB+ |
| 系统 | Ubuntu 22.04 / Debian 12 | — |

### 一键部署

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | bash

# 2. 克隆项目
cd /opt
git clone https://github.com/tweekndd/B2B-Customer-Develop-Page.git
cd B2B-Customer-Develop-Page

# 3. 配置环境变量
cp .env.example .env
nano .env   # 至少修改 SEARXNG_SECRET_KEY / SESSION_SECRET / ADMIN_PASSWORD / GLM_API_KEY

# 4. 一键启动
bash deploy.sh
```

访问 **http://你的服务器IP:8000** → 用管理员账号登录。

### 服务组件

| 组件 | 容器名 | 端口 |
|------|--------|------|
| FastAPI 应用 | `b2b-app` | `8000`（对外） |
| SearXNG 引擎 | `searxng` | `8888`（内网） |
| PostgreSQL | `b2b-db` | `5432`（可选） |

### 日常管理

```bash
docker compose ps          # 查看状态
docker compose logs -f app # 查看应用日志
docker compose up -d       # 启动所有服务
docker compose down        # 停止
bash deploy.sh update      # 更新代码
bash deploy.sh db-backup   # 备份数据库
```

### Nginx + HTTPS（推荐）

```nginx
# /etc/nginx/sites-available/b2b
server {
    listen 80;
    server_name your-domain.com;
    client_max_body_size 10M;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/b2b /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d your-domain.com   # 免费 SSL 证书
```

### PostgreSQL 升级（生产推荐）

```bash
# 在 .env 中设置
DATABASE_URL=postgresql://b2b:密码@db:5432/b2b_customers

# 通过 profile 启动
COMPOSE_PROFILES=with-db docker compose up -d
```

### 常见问题

**Q: 访问不了？** 检查防火墙：`ufw allow 8000`，同时检查云服务商安全组。

**Q: SQLite 数据会丢吗？** 不会。Docker 命名卷持久化，`docker compose down` 不删除卷，只有 `down -v` 才会。

**Q: 服务器重启后？** 自动启动（`restart: unless-stopped`）。

---

## 📁 项目结构

```
AI-Trade-Customer-Analyzer/
├── index.html                        # 🆕 项目介绍落地页（GitHub Pages）
├── main.py                           # FastAPI 主入口 (V4.1)
├── Dockerfile                        # Docker 镜像构建
├── docker-compose.yml                # 编排：app + searxng + db
├── deploy.sh                         # 一键部署脚本
├── .env.example                      # 环境变量模板
├── requirements.txt                  # Python 依赖
├── website/                          # 界面截图（项目介绍页使用）
├── searxng/
│   └── settings.yml                  # SearXNG 配置
├── app/
│   ├── database.py                   # 13 张数据表
│   ├── auth.py                       # 认证与权限 (V4.1)
│   ├── api/
│   │   ├── customers.py              # 客户 CRUD / 分析 / 导入导出
│   │   ├── discovery.py              # 搜索任务 / 关键词扩展 / 相似客户
│   │   ├── sync.py                   # 数据同步 / 备份恢复
│   │   ├── config.py                 # 评分系统配置
│   │   ├── hunter.py / tomba.py / waterfall.py  # 邮箱查找
│   │   ├── users.py                  # 用户管理
│   │   └── geocode.py                # 地理编码
│   ├── services/
│   │   ├── glm_analyzer.py           # GLM AI 分析（含模型降级）
│   │   ├── google_discovery.py       # 搜索引擎（运行时切换）
│   │   ├── searxng_discovery.py      # SearXNG 搜索客户端
│   │   ├── website_scraper.py        # 官网抓取 V2
│   │   ├── scoring_engine.py         # 规则评分引擎
│   │   ├── hunter_service.py         # Hunter API 客户端
│   │   ├── tomba_service.py          # Tomba API 客户端
│   │   ├── prospeo_service.py        # Prospeo API 客户端
│   │   ├── waterfall_discovery.py    # 瀑布式邮箱编排
│   │   ├── geocoding_service.py      # 地理编码
│   │   ├── firecrawl_service.py      # 爬虫降级兜底
│   │   ├── cache_manager.py          # 缓存管理
│   │   ├── deduplication.py          # 智能去重
│   │   └── ...                       # 更多服务
│   ├── static/js/                    # 6 个 JS 模块
│   └── templates/                    # HTML 模板
└── tests/                            # 129+ 测试用例
```

---

## 🗄️ 数据库表

| 表名 | 说明 |
|------|------|
| `customers` | 客户数据（评分、AI 分析、跟进状态、地理编码） |
| `search_tasks` | 搜索任务（断点续跑 + 任务日志） |
| `search_cache` | 搜索结果缓存（30天） |
| `website_cache` | 官网抓取缓存（7天，内容哈希） |
| `analysis_cache` | AI 分析缓存（内容哈希比对） |
| `hunter_cache` | Hunter 查询缓存（7天，命中计数） |
| `tomba_cache` | Tomba 查询缓存（7天） |
| `prospeo_cache` | Prospeo 缓存（7天，含 person_id） |
| `email_quota_log` | 邮箱发现配额日志 |
| `geocode_cache` | 地理编码缓存（唯一键 + 命中计数） |
| `users` | 用户表（密码哈希 / 角色 / 权限 / 配额） |

---

## ⚙️ 评分系统说明

规则评分引擎，AI 仅负责信息提取，评分由程序计算：

| 维度 | 满分 | 说明 |
|------|------|------|
| 行业匹配度 | 30 | 官网命中行业关键词的数量和权重（可运行时编辑） |
| 项目匹配度 | 25 | 是否有项目案例页面、是否涉足目标行业（标签可配置） |
| 公司类型 | 20 | EPC=20, Contractor=18, 生产商=12...（可编辑） |
| 国家优先级 | 15 | 从 `country_weights.json` 读取（可编辑） |
| 联系方式 | 10 | 1个=3分, 2个=5分, 3个=8分, 4个+=10分 |

**优先级**：A(80-100) / B(60-79) / C(40-59) / D(0-39)

评分规则通过网页 **「评分配置」** 页面或编辑 `app/services/industry_config.json` 调整。切换行业（如水处理 → 光伏）仅需修改配置，无需改代码。

---

## 🛠️ 技术栈

| 领域 | 技术 |
|------|------|
| **后端** | Python 3.10+ · FastAPI · SQLAlchemy · SQLite / PostgreSQL |
| **前端** | JavaScript (ES Modules) · Bootstrap 5 · Leaflet.js |
| **AI** | 智谱 GLM (`glm-4.7-flash`，免费，支持自动降级) |
| **搜索** | SearXNG（免费自托管）/ Tavily / SerpAPI（运行时切换） |
| **邮箱** | Hunter.io + Tomba.io + Prospeo.io + 官网抓取（四级瀑布） |
| **爬虫** | httpx + BeautifulSoup（异步并发）· Jina AI Reader 免费降级 |
| **地图** | Leaflet.js + MarkerCluster + Nominatim |
| **部署** | Docker · Docker Compose · Nginx · Let's Encrypt |
| **测试** | pytest（129+ 纯逻辑 + 20 API 集成测试） |
| **缓存** | 本地 SQLite 多级缓存（搜索 / 官网 / AI 分析 / 邮箱 / 地理编码） |
| **认证** | Session + bcrypt · 多用户 · 逐用户配额管控 |

---

## 🧪 运行测试

```bash
source venv/bin/activate
pytest tests/ -v     # 129+ 测试，详细输出
pytest tests/ -q     # 简洁输出
```

---

<div align="center">

**© 2026 AI Customer Development System** · Apache-2.0 License · [GitHub](https://github.com/tweekndd/B2B-Customer-Develop-Page)

</div>
