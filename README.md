# AI Trade Customer Analyzer V4.4

**外贸客户AI分析系统** — 客户发现 + 客户分析 + 客户数据库 + 云共享数据 + 用户与权限管理 + 瀑布式邮箱查找 + SSE 实时流 + 地理分布地图 + Reader (Jina AI) 免费爬虫降级 + SearXNG 自托管搜索引擎 + GLM 模型自动降级

自动通过 SearXNG（自托管无限制）/ Tavily / SerpAPI 发现潜在客户 → AI 分析客户官网 → 规则引擎评分 → Hunter/Tomba/Prospeo 瀑布式查找关键联系人邮箱 → 生成开发切入点，一站式完成。爬虫降级使用 Jina AI Reader（`r.jina.ai`）**完全免费、无需 API Key**。搜索引擎可选 SearXNG 自托管零成本方案。多用户共享数据库，支持管理员对每个用户的搜索配额、搜索深度、AI分析权限、邮箱查找权限进行精细化管控。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **客户发现** | 输入国家 + 关键词 → AI扩展关键词 → SearXNG/Tavily/SerpAPI搜索 → 自动过滤企业官网 |
| **Excel导入** | 上传含 Company Name / Website / Country 三列的 Excel 文件 |
| **官网抓取 V2** | 三阶段 URL 发现（33 条 HEAD 预检 + 智能链接发现 + 异步并发 GET），带 Reader (Jina AI) 免费降级兜底 |
| **Reader (Jina AI) 爬虫降级** | 三层降级统一使用免费的 r.jina.ai API 将 URL 转为 Markdown，零成本无需 API Key。支持 JS 渲染兜底。可自托管 Docker 镜像彻底消除外部依赖 |
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
| **搜索引擎切换** | 运行时一键切换 SearXNG（免费本地）/ Tavily（付费）/ SerpAPI（付费）搜索后端，无需重启 |
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

#### Jina AI Reader（推荐，网站爬虫降级兜底 — **免费、零配置**）
爬虫降级已默认使用 [Jina AI Reader](https://r.jina.ai/)（`r.jina.ai`），将任意 URL 转为 LLM 友好的 Markdown：
- **完全免费** — 官方宣称可用于生产环境，无需 API Key
- **无需配置** — 没有环境变量也能直接用
- **支持 JS 渲染** — 通过 `READER_ENGINE=browser` 启用 headless Chrome
- **可自托管** — `docker pull ghcr.io/jina-ai/reader:oss` 彻底消除外部依赖

> 如果希望保留旧版 Firecrawl 作为最后兜底，可继续设置 `FIRECRAWL_API_KEY`，Reader 失败时会自动回退到 Firecrawl。

#### Firecrawl（可选，Reader 失败时的最后兜底） — 已不再必需
- 前往 https://www.firecrawl.dev/ 注册获取 API Key
- 免费套餐每月 1000 credits，**无需绑卡**
- 仅在 Reader 抓取失败且有 `FIRECRAWL_API_KEY` 环境变量时触发

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
| `SEARXNG_URL` | `http://127.0.0.1:8888` | SearXNG 实例地址（**推荐**，自部署完全免费，零API成本） |
| `SERPAPI_API_KEY` | — | SerpAPI 密钥（二选一，有 SearXNG 时非必需） |
| `TAVILY_API_KEY` | — | Tavily 密钥（二选一，有 SearXNG 时非必需） |
| `SEARCH_ENGINE` | 自动检测 | 强制指定搜索引擎：`searxng` / `serpapi` / `tavily`；运行时可通过前端切换 |
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
| `READER_BASE_URL` | `https://r.jina.ai` | Jina AI Reader API 地址（自托管时改为 `http://localhost:3000`） |
| `READER_ENGINE` | `auto` | Reader 抓取引擎：`auto` / `browser`（JS 渲染）/ `curl`（轻量） |
| `FIRECRAWL_API_KEY` | — | （可选旧版兜底）Reader 失败时回退到 Firecrawl |
| `EMAIL_DISCOVERY_MIN_RESULTS` | `2` | 瀑布式邮箱发现：结果数低于此值才触发下一级 |
| `EMAIL_DISCOVERY_ENABLE_SCRAPING` | `true` | 瀑布式邮箱发现：是否启用官网抓取兜底 |
| `SCRAPE_VERIFY_SSL` | `false` | 官网爬虫是否验证 SSL 证书 |

> **搜索引擎选择说明：** 系统同时支持 SearXNG、SerpAPI 和 Tavily 三种搜索后端。启动时按以下逻辑决定：
> 1. 如果设置了 `SEARCH_ENGINE` 环境变量（`searxng` / `serpapi` / `tavily`），则强制使用指定引擎
> 2. 未设置时，自动检测：**优先使用 SearXNG**（如果有 `SEARXNG_URL`，零成本推荐），其次 Tavily（如果有 `TAVILY_API_KEY`），再次 SerpAPI（如果有 `SERPAPI_API_KEY`）
> 3. 运行时可通过客户发现页面的搜索 API 切换器在 SearXNG/Tavily/SerpAPI 间一键切换，无需重启

---

### ⭐ SearXNG 自托管部署（小白教程，完全免费）

> 🎯 **一句话解释**：SearXNG 是一个你自己电脑上运行的"搜索中转站"。它替你向 Google、Bing 等搜索引擎发请求，把结果汇总给你。**不需要任何 API Key，不用花钱，也没有搜索次数限制。**

---

#### 第一步：安装 Docker

SearXNG 需要用 Docker 来运行。如果你电脑上还没有 Docker：

**Windows 用户：**
1. 浏览器打开 https://docs.docker.com/desktop/setup/install/windows-install/
2. 下载 **Docker Desktop for Windows**
3. 双击安装，一路点「下一步」完成安装
4. 安装完成后重启电脑
5. 启动 Docker Desktop（开始菜单搜 Docker，点开等它加载完，右下角出现小鲸鱼图标 ✅）

> 💡 **如何确认 Docker 装好了？** 打开 cmd（命令提示符）或 PowerShell，输入 `docker --version`，显示出版本号就说明装好了。

---

#### 第二步：一键启动 SearXNG

打开 **cmd（命令提示符）**，复制粘贴下面这一整条命令，按回车：

```bash
docker run -d --name searxng -p 127.0.0.1:8888:8080 searxng/searxng:latest
```

看到一串乱码一样的 ID 输出就成功了 ✅

> ⚠️ **常见问题：**
> - 如果提示 `port is already allocated`，说明 8888 端口被占用了，把命令里的 `8888` 改成 `8899` 之类的其他数字
> - 如果提示 `docker: command not found`，说明 Docker 没装好，回到第一步

---

#### 第三步：启用 JSON 格式（必须做！否则搜不了）

SearXNG 默认只能网页浏览，我们需要让它能返回 JSON 数据给本系统。

**找到配置文件：**
1. 打开 Docker Desktop
2. 左侧点 **Containers**
3. 找到 `searxng` 这个容器，点它
4. 点顶部的 **Exec** 标签（或 Terminal 标签）
5. 在弹出的终端里输入：
   ```bash
   apt-get update && apt-get install -y nano
   nano /etc/searxng/settings.yml
   ```
6. 用键盘方向键往下翻，找到类似这样的内容：
   ```yaml
   search:
     formats:
       - html
   ```
7. 用方向键移到 `- html` 下面那行，输入以下内容（注意前面空两格）：
   ```yaml
     - json
   ```
   改完后应该是这样：
   ```yaml
   search:
     formats:
       - html
       - json    # ← 这一行是新加的
   ```
8. 按 `Ctrl+X` → 按 `Y` 确认保存 → 按回车退出

**重启 SearXNG：**
回到 Windows 的 cmd（命令提示符），输入：
```bash
docker restart searxng
```

---

#### 第四步：验证 SearXNG 是否正常工作

在 cmd 里输入：
```bash
curl "http://127.0.0.1:8888/search?q=test&format=json"
```

如果返回了一大段带 `"results"` 的 JSON 文本 ✅ 说明 SearXNG 可以正常使用了。

如果返回 `403` 或其他错误，说明第三步的 JSON 配置没生效，重新检查一下。

---

#### 第五步：在本系统中启用 SearXNG

在你的项目目录里，用记事本打开 `.env` 文件（如果没有就新建一个），添加以下一行：

```bash
SEARXNG_URL=http://127.0.0.1:8888
```

或者在启动系统的 cmd 窗口中输入：
```bash
set SEARXNG_URL=http://127.0.0.1:8888
```

> **💡 原理**：系统启动时会自动检测 `SEARXNG_URL` 这个环境变量，有的话就自动优先使用 SearXNG，不需要任何 Key，零成本无限搜索。

---

#### 第六步：启动本系统，开始使用

正常启动你的系统：
```bash
python main.py
```

打开浏览器访问 **http://localhost:8000**，在客户发现页面的「预览扩展关键词」行右侧，可以看到当前搜索引擎显示为 **SearXNG**。

你也可以随时在下拉菜单中切换回 **Tavily** 或 **SerpAPI**，不需要重启系统。

---

#### 日常维护

| 操作 | 命令 |
|------|------|
| 启动 SearXNG（如果重启过电脑） | `docker start searxng` |
| 停止 SearXNG | `docker stop searxng` |
| 查看是否在运行 | `docker ps`（能看到 searxng 说明在运行） |
| 彻底删除重装 | `docker rm -f searxng` 然后重新跑第二步的命令 |
| 更新到最新版 | `docker pull searxng/searxng:latest && docker restart searxng` |

---

#### 如果没有 Docker 怎么办？（备选方案）

如果你的电脑装不了 Docker，可以临时用公共 SearXNG 实例测试（**仅适合测试，不建议长期使用**）：

1. 打开记事本编辑 `.env` 文件，写入：
   ```bash
   SEARXNG_URL=https://searx.be
   ```
2. 启动系统即可使用

> ⚠️ 公共实例可能限流或无法返回 JSON，如果不好用就还是装 Docker。

---

---

## 🖥️ VPS 部署（生产环境）

> 🎯 **如果你想把这套系统部署到公网服务器上，让团队成员都能使用，而不是只在你自己电脑上运行，就看这里。**

部署后效果：
- 系统在 **公网服务器** 上 7×24 小时运行
- 你和团队成员通过 **http://你的服务器IP:8000** 访问
- SearXNG 搜索引擎也运行在同一台服务器上，零 API 成本
- 所有数据存储在服务器上，多设备共享

---

### 方案选择

| 方案 | 难度 | 说明 |
|------|------|------|
| **Docker 部署（推荐）** | ⭐⭐ | 用 Docker 容器化运行，一键部署，方便更新和维护 |
| 手动部署 | ⭐⭐⭐ | 在服务器上装 Python 环境手动运行（不推荐，维护麻烦） |

以下只介绍 **Docker 部署**方案。

---

### 准备工作

**你需要：**
1. **一台 VPS 服务器**（推荐配置：2核4G，系统 Ubuntu 22.04 / Debian 12）
2. **一个域名**（可选，建议配置 Nginx 反代 + HTTPS，后面会说）
3. **SSH 客户端**（Windows 用 Terminal 或 PuTTY，Mac/Linux 直接在终端连接）

**服务器最低配置：**
| 配置项 | 最低要求 | 推荐 |
|--------|---------|------|
| CPU | 1核 | 2核+ |
| 内存 | 2GB | 4GB |
| 硬盘 | 20GB | 40GB+ |
| 带宽 | 5Mbps | 10Mbps+ |

---

### 第一步：连接 VPS

打开终端（Windows 推荐用 Windows Terminal 或 PowerShell），输入：

```bash
ssh root@你的服务器IP
```

输入密码后就连上了（如果用的是 SSH Key，不需要密码）。

> 💡 **没有 VPS？** 推荐以下云服务商（国内用户免翻）：
> - 阿里云国际 / 腾讯云 / 华为云 — 国内可选
> - 搬瓦工 (BandwagonHost) / RackNerd — 高性价比
> - 甲骨文云 (Oracle Cloud) — 有永久免费套餐

---

### 第二步：安装 Docker（在 VPS 上执行）

连上服务器后，依次执行以下命令安装 Docker：

```bash
# 更新系统包
apt update && apt upgrade -y

# 安装 Docker（官方一键脚本）
curl -fsSL https://get.docker.com | bash

# 验证安装成功
docker --version
# 应该输出类似: Docker version 27.x.x
```

---

### 第三步：上传项目文件到 VPS

**方法 A — 用 Git 克隆（推荐）：**

如果你的 VPS 能访问 GitHub，直接把代码克隆上去：

```bash
# 在 VPS 上执行
cd /opt
git clone https://github.com/tweekndd/B2B-Customer-Develop-Page.git
cd B2B-Customer-Develop-Page
```

**方法 B — 从本地上传（用 scp）：**

在你自己的电脑上打开新终端（不是 VPS 那个终端）：

```bash
# 在本机执行，把项目传到 VPS
cd D:/Personal/Desktop/MatrixPad/AI/开发
scp -r . root@你的服务器IP:/opt/B2B-Customer-Develop-Page
```

> 💡 `D:` 开头的路径是 Windows 格式。如果报错，先在 Git Bash 或 WSL 中执行。

---

### 第四步：配置环境变量

在 VPS 上（回到 SSH 那个终端），复制配置模板并编辑：

```bash
cd /opt/B2B-Customer-Develop-Page
cp .env.example .env
nano .env
```

**必须修改的几项：**

```bash
# 1. SearXNG 秘钥 — 改成任意随机字符串
SEARXNG_SECRET_KEY=用 openssl rand -hex 32 生成一串随机字符

# 2. Session 签名秘钥 — 改成另一串随机字符串
SESSION_SECRET=再生成一串随机字符

# 3. 管理员密码 — 设一个强密码
ADMIN_PASSWORD=你的管理员密码

# 4. GLM API Key（用于 AI 分析）
GLM_API_KEY=你的智谱API Key

# 5. PostgreSQL 密码（如果用 PostgreSQL 的话）
DB_PASSWORD=数据库密码（可选）

# 6. 设置 SearXNG 连接地址（Docker 内网地址，不需要改）
# 保持注释状态即可，docker-compose 会自动配置
# SEARXNG_URL=http://searxng:8080
```

> ⏭️ **其他 API Key（邮箱查找等）** 暂时不填也能用，先跑起来再说。

编辑完按 `Ctrl+X` → `Y` → `回车` 保存退出。

---

### 第五步：一键启动

```bash
# 在 VPS 上执行（项目根目录）
bash deploy.sh
```

脚本会自动完成以下工作：
1. ✅ 检查 Docker 是否安装
2. ✅ 构建 Docker 镜像（下载依赖包，约 2-5 分钟）
3. ✅ 启动 SearXNG 搜索引擎
4. ✅ 启动 FastAPI 应用
5. ✅ 等待服务就绪

看到绿色 **"部署完成！"** 说明成功了 🎉

---

### 第六步：访问系统

打开浏览器，访问：

```
http://你的服务器IP:8000
```

用你在 `.env` 中设置的 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 登录。

---

### 各组件说明

| 组件 | 容器名 | 功能 | 端口 |
|------|--------|------|------|
| **FastAPI 应用** | `b2b-app` | 系统主程序 | `8000`（对外暴露） |
| **SearXNG** | `searxng` | 自托管搜索引擎 | `8888`（仅内网） |
| **PostgreSQL** | `b2b-db` | 数据库（可选） | `5432`（仅内网） |

> SearXNG 监听在 `127.0.0.1:8888`（不对外暴露），应用通过 Docker 内网地址 `http://searxng:8080` 访问它。

---

### 日常管理

```bash
# 查看所有容器状态
docker compose ps

# 查看应用日志（实时）
docker compose logs -f app

# 查看 SearXNG 日志
docker compose logs -f searxng

# 停止所有服务
docker compose down

# 启动所有服务
docker compose up -d

# 重启单个服务
docker compose restart app
```

---

### 更新代码

当你在本地改了代码，想更新到 VPS：

```bash
# 方法 1：如果用的是 Git 克隆
cd /opt/B2B-Customer-Develop-Page
git pull

# 方法 2：如果用的是 scp 上传，重新上传覆盖

# 然后执行更新命令
bash deploy.sh update
```

这会自动拉取最新代码 → 重新构建镜像 → 重启容器。

---

### 备份数据库

SQLite 数据库文件默认存储在 Docker 卷中，使用以下命令备份：

```bash
# 备份到 backups/ 目录
bash deploy.sh db-backup

# 备份文件位置：backups/customers_20241201_120000.db
```

也可以手动从 Docker 卷复制：

```bash
# 直接复制数据库文件到宿主机
docker cp b2b-app:/app/app/customers.db ./backup_customers.db
```

---

### ⭐ 进阶：使用 PostgreSQL（生产环境推荐）

默认使用 SQLite，简单够用。但在生产环境（多人并发使用）建议升级到 PostgreSQL：

**1. 取消注释 `docker-compose.yml` 中的 db 服务：**

编辑 `docker-compose.yml`，找到 `app` 服务的 `depends_on` 部分，取消 db 的注释：

```yaml
depends_on:
  searxng:
    condition: service_healthy
  db:                              # ← 取消注释
    condition: service_healthy     # ← 取消注释
```

**2. 在 `.env` 中设置 PostgreSQL 连接地址：**

```bash
DATABASE_URL=postgresql://b2b:你的密码@db:5432/b2b_customers
```

**3. 通过 profile 启动（推荐方式，不解锁 docker-compose.yml）：**

```bash
# 启用 with-db profile 来启动 PostgreSQL
COMPOSE_PROFILES=with-db docker compose up -d

# 或者设置环境变量让它永久生效
echo "COMPOSE_PROFILES=with-db" >> .env
docker compose up -d
```

> ⚠️ **迁移注意**：从 SQLite 切换到 PostgreSQL 需要先导出数据。建议先用 SQLite 跑起来，确认系统工作正常后再考虑迁移。

---

### ⭐ 进阶：配置 Nginx 反代 + HTTPS（推荐）

通过 IP + 端口访问不够安全。配置域名和 HTTPS 后更专业：

```bash
# 安装 Nginx
apt install nginx -y

# 配置反代
nano /etc/nginx/sites-available/b2b
```

写入以下内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 改成你的域名

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

启用配置并申请 SSL 证书：

```bash
ln -s /etc/nginx/sites-available/b2b /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 申请免费 SSL 证书（需先解析域名到服务器 IP）
apt install certbot python3-certbot-nginx -y
certbot --nginx -d your-domain.com
```

之后就可以用 **https://your-domain.com** 访问了。

---

### 常见问题

**Q: 部署后访问不了，网页打不开？**
A: 检查服务器防火墙是否放行了 8000 端口：
```bash
# Ubuntu / Debian
ufw allow 8000

# 云服务商控制台也要检查安全组/防火墙规则
```

**Q: 使用 SQLite 时数据会丢失吗？**
A: 不会。SQLite 数据库存储在 Docker 命名卷 `sqlite-data` 中，重启容器不会丢失。执行 `docker compose down` 也不会删除卷。只有 `docker compose down -v` 才会删除。

**Q: 服务器重启后需要手动启动吗？**
A: 不需要。所有容器设置了 `restart: unless-stopped`，Docker 服务启动时会自动拉起。

**Q: 如何查看 SearXNG 是否正常工作？**
A:
```bash
curl http://127.0.0.1:8888/search?q=test&format=json
# 应该返回带 "results" 的 JSON
```

**Q: 如何切换搜索引擎？**
A: 登录系统后，在「客户发现」页面右下角的搜索引擎下拉框中切换。或者在 `.env` 中设置 `SEARCH_ENGINE=searxng` 固定使用 SearXNG。

---

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
3. 可选：在「预览扩展关键词」行右侧切换 **搜索 API**（SearXNG / Tavily / SerpAPI）
4. 点击 **Start Search**
5. 系统自动完成：AI扩展关键词 → 搜索（SearXNG/Tavily/SerpAPI） → 过滤官网 → 去重 → 官网抓取（含 Reader 免费降级兜底）→ AI分析 → 规则评分 → 保存入库
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
├── Dockerfile                       # Docker 镜像构建文件（VPS 部署用）
├── docker-compose.yml               # Docker 编排：应用 + SearXNG + 可选 PostgreSQL
├── deploy.sh                        # VPS 一键部署脚本
├── .env.example                     # 环境变量配置模板
├── requirements.txt                 # 依赖清单（新增 bcrypt / itsdangerous）
├── sync.sh                          # 一键同步脚本
├── searxng/
│   └── settings.yml                 # SearXNG 配置文件（启用 JSON API）
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
│   │   ├── firecrawl_service.py     # 爬虫降级服务：Reader (r.jina.ai) 免费降级 + 可选 Firecrawl 兜底
│   │   ├── website_scraper.py       # 官网抓取 V2（多阶段 URL 发现 + Reader/Firecrawl 三层降级）
│   │   ├── email_extractor.py       # 邮箱提取
│   │   ├── keyword_analyzer.py      # 关键词分析（从配置文件加载）
│   │   ├── keyword_expander.py      # AI 关键词扩展（多语言支持，含模型降级）
│   │   ├── glm_analyzer.py          # GLM AI 分析（含重试/降级）
│   │   ├── similar_company_finder.py# 相似客户扩展（含模型降级）
│   │   ├── scoring_engine.py        # 规则评分引擎（缓存化）
│   │   ├── google_discovery.py      # SearXNG / SerpAPI / Tavily 搜索（运行时切换）
│   │   ├── tavily_discovery.py      # Tavily 搜索客户端
│   │   ├── searxng_discovery.py     # SearXNG 自托管搜索客户端（免费）
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
- **搜索**：SearXNG（免费自托管）/ Tavily / SerpAPI（运行时一键切换）
- **邮箱**：Hunter.io + Tomba.io + Prospeo.io + 官网抓取兜底（瀑布式四级级联）
- **爬虫**：httpx + BeautifulSoup（异步并发，多阶段 URL 发现）
- **爬虫降级**：Jina AI Reader（`r.jina.ai`，完全免费零配置，支持自托管 Docker 镜像） + 可选旧版 Firecrawl 兜底
- **地图**：Leaflet.js + MarkerCluster + Nominatim 地理编码
- **缓存**：本地 SQLite 多级缓存（搜索/官网/AI分析/邮箱/地理编码）
- **认证**：Session + bcrypt 密码哈希（V4.0 多用户 / V4.1 精细权限控制）
- **测试**：pytest（API 集成测试 + 纯逻辑模块测试）
