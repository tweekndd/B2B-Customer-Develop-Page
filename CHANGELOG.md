# 更新日志

## v3.1.2（2026-06-23）

### 🔗 Hunter × 跟进一体化 — 详情页流程闭环

#### ① 后端新增：保存 Hunter 邮箱到客户 API

**新增 `POST /api/customers/{customer_id}/add-emails`：**
- 参数 `emails`：JSON 数组字符串（要添加的邮箱列表）
- 可选参数 `set_status`：保存后自动更新跟进状态（如 `已发邮件`）
- 去重合并：与客户已有邮箱合并去重，不产生重复记录
- 刷新即用：写入后即刻更新数据库，前端重新加载即可看到最新邮箱列表

#### ② 前端重构：详情页合并「跟进 + Hunter」为统一操作区

**之前**——两个独立的卡片，查完邮箱不能直接保存，互不关联：

```
┌─ 跟进记录 ──┐  ┌─ Hunter 邮箱查找 ──┐
│ 状态/日期    │  │ 姓名/部门 → 查    │
│ 孤立操作     │  │ 结果只能复制       │
└──────────────┘  └───────────────────┘
```

**之后**——一个卡片 + Tab 切换，操作闭环：

```
┌─ 邮箱查找与跟进 ────────────────────────┐
│ [查找邮箱+标记已联系] [精确查找]         │
│ ┌─Tab: 跟进状态 | Hunter查邮箱────────┐ │
│ │ 跟进面板: 状态/日期/备注/评级+保存   │ │
│ │ 快速导入: 上次Hunter结果一键保存      │ │
│ ├─────────────────────────────────────┤ │
│ │ Hunter面板: 域名/姓名/部门/查找      │ │
│ │ 结果表格: 每行可复制/单存; 底部批量   │ │
│ │ [仅保存邮箱] [保存并标记已联系]       │ │
│ └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

**一键工作流：**
1. `查找邮箱 + 标记已联系` → 自动查 Hunter → 保存邮箱 → 设状态为"已发邮件" → 刷新
2. 查到结果后 → 可逐条保存单个邮箱，或批量保存全部
3. 保存后自动切换到跟进面板，直接记录备注和下次跟进日期

#### ③ 周边联动

- **邮箱卡片**：有网站时显示「通过 Hunter 查找」/「Hunter 查更多」按钮，指向 Hunter 面板
- **配置状态**：卡片头实时显示 Hunter API Key 状态（✅已配置 / 🛠️测试模式 / ⚠️未配置）
- **备注建议**：跟进备注增加 `datalist` 快速输入（已发开发信/已加 LinkedIn/已电话沟通 等）
- **域名预填**：根据客户网址自动填充 Hunter 面板的域名

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/api/customers.py` | 修改 — 新增 `POST /api/customers/{id}/add-emails` 端点 |
| `app/templates/detail.html` | 修改 — Hunter × 跟进一体化整合 + 一键操作流程 |
| `app/static/css/style.css` | 修改 — 新增 `.nav-tabs-sm` 小号 Tab 样式 |

---

## v3.2.1（2026-06-25）

### 🌊 Phase 1 — 瀑布式多源邮箱发现

#### 背景

当前邮箱发现仅依赖 Hunter.io（25次/月免费），月中易耗尽。Phase 1 引入 **Tomba.io** 作为第二数据源 + 自研官网抓取兜底，构建三级瀑布式级联，不增加成本提升邮箱发现成功率。

#### 核心思路：瀑布式调用

```
输入：公司域名
       ↓
[第1级] Hunter.io domain search
       ↓ 无结果或 < 2 条
[第2级] Tomba.io domain search（无结果不扣费）
       ↓ 仍无结果
[第3级] 官网 HTML mailto: 抓取兜底
       ↓
结果合并 → 去重 → 评分排序（来源权重+验证状态+职位级别+置信度）
```

#### 新增模块

##### ① Tomba API 客户端 — `app/services/tomba_service.py`

- `TombaClient` 类（结构与 `HunterClient` 一致）
- 双认证：`X-Tomba-Key` + `X-Tomba-Secret`
- 域名搜索 `domain_search()` / 精确查找 `email_finder()`
- 本地 SQLite 缓存层（7天 TTL）
- 配额记录持久化到 `email_quota_log` 表
- 无结果不扣费（Tomba 官方策略）

##### ② Tomba API 路由 — `app/api/tomba.py`

| 接口 | 方法 | 说明 |
|:-----|:-----|:------|
| `/api/tomba/status` | GET | 配置状态 |
| `/api/tomba/domain-search` | GET | 域名搜索（返回含领英/电话/部门） |
| `/api/tomba/find-person` | GET | 精确查找某人 |
| `/api/tomba/usage` | GET | 配额统计 + 缓存统计 |
| `/api/tomba/clear-cache` | POST | 清除缓存 |
| `/api/tomba/cache-entries` | GET | 缓存条目列表 |

##### ③ 瀑布式编排 — `app/services/waterfall_discovery.py`

- `waterfall_email_discovery(website)` — 统一入口
- Hunter → Tomba → 自研抓取三级级联
- 结果数低于 `EMAIL_DISCOVERY_MIN_RESULTS`（默认 2）才触发下一级
- `_merge_and_dedup()` — 多源结果去重（Tomba > Hunter > scraped）
- `_score_and_sort()` — 综合排序（来源权重30/25/10 + 验证状态30/15 + 职位级别 + 置信度）

##### ④ 瀑布式 API — `app/api/waterfall.py`

| 接口 | 方法 | 说明 |
|:-----|:-----|:------|
| `/api/waterfall/email-discovery` | GET | 瀑布式邮箱发现入口 |
| `/api/waterfall/quota-history` | GET | 各平台配额使用历史 |

##### ⑤ 数据库扩展 — `app/database.py`

| 表 | 说明 |
|----|------|
| `tomba_cache` | Tomba 查询缓存（7天 TTL） |
| `email_quota_log` | 邮箱发现配额持久化记录 |

#### 前端

- **客户详情页** — 新增「多源查邮箱」Tab（瀑布式查找）
- 实时显示瀑布级联进度（第1级 Hunter → 第2级 Tomba → 第3级 网页抓取）
- 结果表格展示：邮箱、姓名、职位、部门、来源、评分、领英、操作
- 批量保存邮箱 / 保存并标记已联系
- **Hunter 精确查找 Tab 保留**，作为补充手动查找

#### 配置

```bash
# Tomba（瀑布式第二数据源）
set TOMBA_API_KEY=ta_xxxxxxxxxx
set TOMBA_API_SECRET=ts_xxxxxxxxxx

# 瀑布式行为控制
set EMAIL_DISCOVERY_MIN_RESULTS=2
set EMAIL_DISCOVERY_ENABLE_SCRAPING=true
```

#### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/services/tomba_service.py` | **新建** — Tomba API 客户端 |
| `app/api/tomba.py` | **新建** — Tomba API 路由 |
| `app/services/waterfall_discovery.py` | **新建** — 瀑布式编排引擎 |
| `app/api/waterfall.py` | **新建** — 瀑布式 API 路由 |
| `app/database.py` | 修改 — 新增 TombaCache + EmailQuotaLog 表 |
| `app/api/__init__.py` | 修改 — 注册 Tomba + Waterfall 路由 |
| `app/templates/detail.html` | 修改 — 新增多源查邮箱 Tab + 瀑布式查找 UI |
| `README.md` | 修改 — 功能概览/配置/结构/数据库表更新 |

### 🔄 搜索引擎运行时切换（承接 V3.2）— Tavily / SerpAPI 前端一键切换

**之前：** 搜索引擎在启动时通过 `SEARCH_ENGINE` 环境变量固定，或自动检测已配置的 API Key 决定。要切换引擎必须重启服务。

**之后：** 客户发现页面顶部新增引擎切换器，运行时即可切换，无需重启。项目启动时同时传入两个 API Key，前端随时切换。

#### ① 后端重构（`google_discovery.py`）

- `_SEARCH_ENGINE` 从模块级常量改为 `_current_engine` 运行时变量
- `_init_search_engine()` — 启动时初始化（兼容旧版 `SEARCH_ENGINE` 环境变量）
- `set_search_engine(engine)` — 运行时切换引擎，检查 API Key 是否可用
- `get_search_engine_info()` — 返回当前引擎、可用引擎列表、默认引擎
- `search_google()` 改用 `_current_engine`，不再每次调用 `_detect_search_engine()`

#### ② 新增 API 端点（`discovery.py`）

| 接口 | 方法 | 说明 |
|:-----|:-----|:------|
| `/api/discovery/search-engine` | GET | 获取当前引擎配置 |
| `/api/discovery/search-engine?engine=...` | POST | 运行时切换（tavily / serpapi） |

#### ③ 前端切换 UI（`discovery.html`）

- 「预览扩展关键词」行右侧新增 `搜索 API:` 切换按钮组
- Tavily（☁️） / SerpAPI（🔍） 两个 Pill 按钮，当前选中高亮
- 当前引擎状态指示器 badge（蓝色=Tavily / 绿色=SerpAPI / 灰色=未配置）
- 未配置 API Key 的引擎自动禁用并显示提示
- `loadSearchEngineConfig()` — 页面加载时读取引擎状态
- `switchSearchEngine(engine)` — 点击按钮切换引擎

#### ④ 启动方式

```bash
# 同时传入两个 Key，前端默认使用 Tavily
set TAVILY_API_KEY=your-tavily-key
set SERPAPI_API_KEY=your-serpapi-key
python main.py
```

### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/services/google_discovery.py` | 重构 — 从模块级常量改为运行时可变引擎 |
| `app/api/discovery.py` | 修改 — 新增 `GET/POST /api/discovery/search-engine` 端点 |
| `app/templates/discovery.html` | 修改 — 新增引擎切换 UI + JS 逻辑 |

---

## v3.0.0（2026-06-23）

### 🌟 Hunter.io 邮箱查找集成 — 配额优化 & 智能缓存

#### ① Hunter 服务层（`hunter_service.py`）

**新增 `app/services/hunter_service.py`** — 完整的 Hunter API 客户端，内置 5 层配额优化策略：

| 优化策略 | 说明 |
|:---------|:------|
| **本地缓存优先** | 所有查询结果写入 SQLite `hunter_cache` 表，缓存 7 天，相同查询不消耗额度 |
| **Email Count 预检** | 始终先调用免费 Email Count API，total=0 直接返回，不消耗搜索额度 |
| **Domain Search 自带验证** | 返回结果含 verification，不再额外调用 Email Verifier |
| **智能降级** | 有姓名时先在 Domain Search 缓存中匹配，找不到才触发 Email Finder（低至 1 次搜索/人） |
| **请求间隔控制** | 内置 0.3 秒请求延迟 + 429 自动重试，避免触发 Hunter 速率限制 |

**核心类 `HunterClient`：**
- `email_count(domain)` — 检查数据量（免费）
- `domain_search(domain, department, seniority)` — 按域名全量搜索
- `email_finder(domain, first_name, last_name)` — 按姓名精确查找
- `email_verifier(email)` — 验证邮箱
- `smart_find_emails(domain, first_name, last_name)` — 智能流程（推荐使用）
- `get_usage_stats()` / `get_cache_stats()` — 配额 / 缓存统计

**配额跟踪：** 进程内全局计数器记录 email_count / domain_search / email_finder / email_verifier / cache_hits，用户可实时查看已消耗的搜索和验证次数。

#### ② Hunter API 路由（`api/hunter.py`）

| 接口 | 方法 | 说明 |
|:-----|:-----|:------|
| `/api/hunter/status` | GET | 检查 API Key 配置状态 |
| `/api/hunter/email-count` | GET | 查询域名邮箱总量（免费） |
| `/api/hunter/find-emails` | GET | 智能查找（含额度优化策略） |
| `/api/hunter/find-person` | GET | 精确查找某人邮箱（强制 Email Finder） |
| `/api/hunter/usage` | GET | 配额使用统计 + 缓存统计 |
| `/api/hunter/clear-cache` | POST | 清除所有 Hunter 缓存 |
| `/api/hunter/cache-entries` | GET | 列出缓存条目 |

#### ③ 数据库新增 `HunterCache` 模型

- 字段：`cache_key`（MD5 唯一键）/ `domain` / `query_type` / `result`（JSON）/ `hits`（命中次数）/ `created_at`
- 自动迁移：启动时检查并创建 `hunter_cache` 表，已有数据库无需手动迁移

#### ④ 前端集成

**客户详情页（`detail.html`）：**
- 操作栏新增「Hunter 查邮箱」按钮
- 新增 Hunter 查找卡片（支持输入姓名 + 部门筛选）
- 结果以表格展示（邮箱、姓名、职位、置信度、验证状态、复制按钮）
- 显示本次消耗的搜索额度，帮助用户控制配额

**Hunter 独立页面（`/hunter` 路线）：**
- 快捷查找区：输入域名 + 姓名 + 部门/级别筛选，一键搜索
- 配额统计卡片：实时显示搜索/验证/缓存命中次数
- 缓存管理：查看缓存条目类型分布 + 一键清除
- 完整使用说明：API 配置 / 套餐额度 / 优化策略 / 集成指引

**导航栏：** 新增「Hunter 邮箱」菜单项

#### ⑤ 配置方式

Hunter API Key 通过环境变量配置（与已有 TAVILY_API_KEY / SERPAPI_API_KEY 模式一致）：
```bash
set HUNTER_API_KEY=your_key_here      # Windows cmd
$env:HUNTER_API_KEY="your_key_here"   # PowerShell
export HUNTER_API_KEY=your_key_here   # Linux/Mac
```
测试时使用 `test-api-key`（返回测试数据不消耗额度）。

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/services/hunter_service.py` | **新建** — Hunter API 客户端 + 缓存层 + 配额管理 |
| `app/api/hunter.py` | **新建** — 7 个 API 接口 |
| `app/templates/hunter.html` | **新建** — Hunter 使用教程 + 快捷查找页面 |
| `app/database.py` | 修改 — 新增 HunterCache 模型 + 自动迁移 |
| `app/api/__init__.py` | 修改 — 注册 hunter 路由 |
| `app/templates/base.html` | 修改 — 导航栏新增 Hunter 邮箱链接 |
| `app/templates/detail.html` | 修改 — 操作栏 + 查找卡片 + JS 交互 |
| `main.py` | 修改 — 新增 `/hunter` 路由 + 版本号 V3.0 |
| `app/static/js/app.js` | 无需修改（复用已有工具函数） |
| `CHANGELOG.md` | 修改 — 本次更新日志 |

---

## v2.9.0（2026-06-22）

### 🔧 P1 级优化 — 并发安全 & 行业解耦 & 集成测试

#### ① `_global_stop_flag` 改为按任务独立控制（P1）

**问题**：`search_task_service.py` 使用模块级全局变量 `_global_stop_flag`，停止一个搜索任务或批量分析会导致所有任务被停止，多任务场景下相互干扰。

**修改**：
- 引入 `_task_stop_flags: Dict[int, bool]` 字典，每个搜索任务通过自己的 task_id 独立控制停止
- 引入 `_batch_stop_flag: bool` 代替原全局标志，仅用于客户端批量分析停止（不影响搜索任务）
- 新增 `request_task_stop(task_id)` 和 `should_stop(task_id)` 函数
- 保留 `request_stop()` / `reset_stop_flag()` 向后兼容
- `discovery.py` 中 `pause_task(task_id)` 改为调用 `request_task_stop(task_id)`
- `customers.py` 中 `stop_analysis()` 继续使用 `request_stop()`（映射到 `_batch_stop_flag`）

**影响文件**：
- `app/services/search_task_service.py` — 核心修改
- `app/api/discovery.py` — 更新导入和调用

#### ② 行业配置解耦 — 项目匹配标签外置化（P1）

**问题**：评分引擎 `_score_project_match()` 的显示标签硬编码了「水处理」相关的行业特定术语（"项目涉及水处理"、"项目与水务相关度低"），切换行业需改代码。

**修改**：
- `industry_config.json` → `scoring.project_match` 新增 `has_project_label`、`has_content_label`、`low_relevance_label` 三个可配置的显示标签
- 字段名 `has_water_content` 改为 `has_content_match`（从行业专属改为通用）
- `scoring_engine.py` 读取配置标签代替硬编码字符串
- 同时修复 `_score_country()` 中 `if score == 0:` 覆盖匹配结果的逻辑 bug
- `config.html` 前端编辑器增加 3 个标签输入框 + 提示文字
- `config.py` 校验器增加对新字段的验证

**影响文件**：
- `app/services/industry_config.json` — 新增标签字段
- `app/services/scoring_engine.py` — 读取配置标签 + 修复匹配逻辑
- `app/api/config.py` — 校验新字段
- `app/templates/config.html` — 前端编辑界面

#### ③ API 集成测试（P1）

**问题**：原有 129 个测试覆盖了纯逻辑模块，但零 API 集成测试，核心流程依赖手工验证。

**新增测试**（20 个用例）：
- **客户 CRUD**（8 个）：空列表、有数据列表、详情、404、删除、按优先级筛选、按分数排序、分页
- **统计 API**（2 个）：空库统计、有数据统计
- **配置管理**（5 个）：读取配置、写入合法/非法国家权重、写入合法/非法行业配置
- **页面路由**（3 个）：首页、发现页、配配置页返回 200 + HTML
- **数据同步**（2 个）：空库导出、导入

**保护机制**：测试前后自动备份/恢复 `industry_config.json` 和 `country_weights.json`，防止测试数据污染生产配置。

**影响文件**：
- `tests/test_api_integration.py` — 新建（20 个测试用例）

#### ④ 附带修复

- 修复 `_score_country()` 中模糊匹配到权重为 0 的国家（如 US: 0）后被 `if score == 0:` 分支覆盖为 Other 值的逻辑 bug
- 恢复 `country_weights.json` 为完整配置（含 Mexico、Qatar、US、Other）

---

## v2.8.0（2026-06-22）

### 🏗 架构重构 & 前端健壮性

#### ① routes.py 模块化拆分（P0）

**问题**：`app/api/routes.py` 已膨胀至 1068 行，包含客户管理、搜索发现、跟进状态、数据同步、Excel 导出等全部 API，维护成本线性增长。

**改进**：拆分为四个职责清晰的独立路由模块：

| 新文件 | 职责 | 行数 |
|--------|------|------|
| `app/api/customers.py` | 客户CRUD、分析、导入导出、跟进状态、局部重试 | ~350 |
| `app/api/discovery.py` | 搜索任务管理、关键词扩展、发现结果、相似客户 | ~220 |
| `app/api/sync.py` | 多设备数据同步导出/导入 | ~230 |
| `app/api/config.py` | 评分系统配置读写、校验、缓存清理 | ~190 |

`app/api/__init__.py` 负责聚合全部子路由器，`app/api/routes.py` 保持为薄兼容层。

#### ② 前端轮询架构修复（P0）

**问题**：`index.html`（客户列表页）中所有 `fetch()` 调用均无超时保护、无 AbortController、无安全兜底函数、`statusPollTimer` 在页面关闭时未清理。批量分析等长耗时操作可能在网络异常时永久挂起。

**改进**：
- 新增 `_fetchWithTimeout(url, options, timeout)` 封装（AbortController + 默认 15s 超时）
- 新增 `_esc()` / `_num()` / `_arr()` 安全兜底函数（防 HTML 注入、NaN、类型错误）
- **10 处裸 `fetch()` 全部替换**为带超时封装，长耗时操作使用更长时间（分析 120s / 重抓取 60s / 批量分析 600s）
- 新增 `beforeunload` 监听器确保页面关闭时清理 `statusPollTimer`
- 移除重复的 `_esc` 函数定义

> `discovery.html` 已在之前版本完成同类改造，此次无需额外修改。

#### ③ 配置管理系统（P1 — 解决行业锁定）

**问题**：`keyword_analyzer.py` 中 `POSITIVE_KEYWORDS` 和 `NEGATIVE_KEYWORDS` 为硬编码，无法在运行时修改。评分系统存在水处理行业锁定（`has_water_content` 逻辑），切换行业需改代码。

**改进**：

**A. `keyword_analyzer.py` 改为从 `industry_config.json` 读取**
- 新增 `_load_keywords()` 缓存读取函数
- `analyze_keywords()` 运行时从配置文件加载正向/负向关键词
- 向后兼容：配置缺失时使用硬编码默认值
- 新增 `invalidate_keyword_cache()` 供 API 调用

**B. `scoring_engine.py` 新增缓存清理**
- 新增 `invalidate_config_cache()` 函数，清除 `_load_config` 和 `_load_country_weights` 的 `lru_cache`
- 写入配置后即时生效，无需重启

**C. 配置管理 API（`GET /api/config` / `PUT /api/config` / `PUT /api/config/country-weights`）**
- 支持读取/写入 `industry_config.json` 和 `country_weights.json`
- 全字段 JSON Schema 校验（关键词权重、公司类型分数、国家权重范围等）
- 写入后自动清除所有相关缓存，新评分规则即时生效

**D. 网页配置编辑器（`/config` 页面）**
- **正向关键词**：增删改，实时渲染标签
- **负向关键词**：增删改，实时渲染标签
- **行业匹配权重**：表格编辑，支持批量调整关键词权重（1-5）
- **项目匹配度**：检测关键词、内容关键词、基础分值编辑
- **公司类型评分**：增删改公司类型及其分数
- **联系方式评分**：邮箱数量阶梯编辑
- **国家权重**：增删改国家及其优先级分数
- **优先级规则**：A/B/C/D 档位阈值编辑
- **JSON 预览**：展开查看完整配置内容
- **导航离开提示**：未保存时弹出确认
- **保存反馈**：Toast 通知 + 全链路缓存清理

#### ④ 产品评审报告

新增 `产品评审报告-V2.7.md`，从产品经理视角对项目进行完整审评。

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/api/customers.py` | **新建** |
| `app/api/discovery.py` | **新建** |
| `app/api/sync.py` | **新建** |
| `app/api/config.py` | **新建** — 配置管理系统 API |
| `app/api/__init__.py` | 重写 — 路由器聚合（+config） |
| `app/api/routes.py` | 重写 — 薄兼容层 |
| `app/templates/config.html` | **新建** — 配置编辑器页面 |
| `app/services/keyword_analyzer.py` | 重写 — 从配置文件读取关键词 |
| `app/services/scoring_engine.py` | 修改 — 新增 `invalidate_config_cache()` |
| `main.py` | 修改 — 导入路径 + `/config` 路由 + 版本号 V2.8 |
| `app/templates/index.html` | 修改 — 前端健壮性 + 导航栏加配置入口 |
| `app/templates/discovery.html` | 修改 — 导航栏加配置入口 |
| `app/templates/detail.html` | 修改 — 导航栏加配置入口 |
| `README.md` | 修改 — 版本号更新 |
| `CHANGELOG.md` | 修改 — 本次更新日志 |
| `产品评审报告-V2.7.md` | **新增** |
| `CHANGELOG.md` | 修改 — 本次更新日志 |
| `产品评审报告-V2.7.md` | **新增** |

---

## v2.7.1（2026-06-19）

### 🔧 业务逻辑 & 安全修复

#### ① SSL 验证配置化

`website_scraper.py` 和 `similar_company_finder.py` 中硬编码的 `verify=False`（禁用 SSL 证书验证）改为由环境变量 `SCRAPE_VERIFY_SSL=true` 控制，默认仍为关闭（兼容既有抓取行为），安全敏感场景可开启。

#### ② 去重性能优化

`deduplication.py` 的 `find_existing_customer()` 在公司名匹配时从加载全表改为 Token 预过滤（SQL LIKE + limit 50），大幅减少内存占用和扫描时间。

#### ③ 评分配置缓存

`scoring_engine.py` 的 `_load_config()` 和 `_load_country_weights()` 添加 `@lru_cache`，首次读取后缓存到内存，批量分析时不再重复读磁盘。

#### ④ 发现列表添加分页

`/api/discovery/discovered-customers` 接口新增 `page`/`page_size` 参数，前端表格下方新增上一页/下一页分页控件，筛选变更时重置到第一页。

#### ⑤ 修复 JSON 解析异常

`search_task_service.py` 中 `json.loads(task.expanded_keywords)` 添加 `try/except` 保护，损坏数据触发自动重新扩展而非任务崩溃。

#### ⑥ 同步导入主键安全

`/api/sync/import` 导入 search_tasks 时不再显式指定 `id`，改为按 `(country, keyword)` 业务键去重，避免 PostgreSQL 序列冲突。

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/services/website_scraper.py` | 修改 — SSL 验证环境变量化 |
| `app/services/similar_company_finder.py` | 修改 — SSL 验证环境变量化 |
| `app/services/deduplication.py` | 修改 — Token 预过滤优化 |
| `app/services/scoring_engine.py` | 修改 — 添加 lru_cache |
| `app/services/search_task_service.py` | 修改 — JSON 解析异常保护 |
| `app/api/routes.py` | 修改 — 发现列表分页 + sync 导入主键安全 |
| `app/templates/discovery.html` | 修改 — 分页控件 |
| `CHANGELOG.md` | 修改 — 本次更新日志 |

---

## v2.7.0（2026-06-19）

### 🔧 修复 & 优化

#### ① 统一搜索任务主循环的去重逻辑

**问题**：`run_search_task()` 主循环使用简单的 `Customer.website.ilike(f"%{domain}%")` 进行域名模糊匹配去重，而 `_auto_analyze_and_save()` 已使用统一的 `deduplication.find_existing_customer()`。两处去重逻辑不一致，导致某些场景下去重失效。

**改进**：
- `run_search_task()` 主循环的去重改为调用 `find_existing_customer(db, domain, company_title)`，实现域名精确匹配 + 公司名标准化匹配双重保障
- 发现已存在客户时合并发现关键词（而非简单跳过），与 `_auto_analyze_and_save()` 行为一致
- `analyzed_companies` 计数器仍然递增（已存在的客户也算"已处理"）

#### ② 任务日志写入功能

**问题**：SearchTask 模型的 `task_log` 字段已在 v2.6 添加，但 `run_search_task()` 全程未写入任何日志，前端「查看执行日志」按钮始终显示"暂无日志记录"。

**改进**：
- 新增 `_append_task_log(task, type_, msg)` 辅助函数，追加结构化日志到 `task_log` 字段
- 在任务全生命周期关键节点写入日志：
  - ✅ 任务启动（含国家/关键词）
  - ✅ AI关键词扩展完成（含扩展数量）
  - ✅ 开始搜索每个关键词
  - ✅ 搜索缓存命中/搜索完成（含结果条数）
  - ✅ 过滤非企业官网结果
  - ✅ 跳过重复客户（合并关键词）
  - ✅ 分析失败（含失败原因）
  - ✅ 用户停止信号
  - ✅ 任务异常终止
  - ✅ 任务成功完成（含统计汇总）
- 每条日志包含时间戳 + 类型图标（ℹ️信息/✅成功/⚠️警告/❌错误）

#### ③ 前端版本号统一

main.py、index.html、discovery.html 中的版本号标记分别显示 V2.0 / V2.2，全部统一为 V2.7。

#### ④ 代码清理

移除 `app/api/routes.py` 中 `keyword_analyzer` 和 `scoring_engine` 的重复导入。

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/services/search_task_service.py` | 修改 — 统一去重逻辑 + 添加任务日志写入 |
| `main.py` | 修改 — 版本号 V2.0 → V2.7 |
| `app/templates/index.html` | 修改 — 版本号 V2.2 → V2.7 |
| `app/templates/discovery.html` | 修改 — 版本号 V2.0 → V2.7 |
| `app/api/routes.py` | 修改 — 移除重复导入 |
| `CHANGELOG.md` | 修改 — 本次更新日志 |

---

## v2.0.1（2026-06-06）

### 🛠 修复：停止任务按钮无响应问题

#### 问题描述

点击发现页面的「停止任务」按钮时，页面没有任何视觉反馈，且任务不会立即停止。用户会误以为按钮失效。

#### 原因分析

1. **前端缺少视觉反馈**—— `stopSearchTask()` 只是默默发了 POST 请求，没有在界面上显示任何"停止信号已发送"的提示，用户感觉按钮"没反应"。
2. **后端停止检查点不足**—— 停止信号 `_global_stop_flag` 只在 `run_search_task()` 的以下两个位置被检查：
   - 处理每个**扩展关键词**之前
   - 处理每个**搜索结果**之前

   而每个搜索结果（公司）的完整分析流程 `_auto_analyze_and_save()` 内部——包含官网抓取、邮箱提取、关键词分析、**DeepSeek AI 分析**（最耗时，通常 30-60 秒）——完全没有检查停止标志，导致用户点击停止后仍需等待当前公司的 AI 分析完成才能生效。

#### 修改内容

##### 前端 — `app/templates/discovery.html`

- `stopSearchTask()` 函数增加实时反馈：
  - 点击后按钮立即置灰并显示「⏳ 正在停止...」加载动画
  - 状态栏文字立即更新为「正在停止」
  - 3 秒后自动刷新任务状态，以便前端及时反映后端处理结果
  - 请求失败时弹出错误提示

##### 后端 — `app/services/search_task_service.py`

在 `_auto_analyze_and_save()` 内部新增**两处停止信号检查**：

1. **官网爬取完成后、邮箱提取前**（第 265-270 行）
   - 场景：爬取完成但 AI 分析还未开始
   - 行为：保存已爬取的内容，标记公司为已分析，安全返回

2. **DeepSeek AI 分析调用前**（第 288-293 行）
   - 场景：即将进入最耗时的 AI 分析步骤
   - 行为：跳过 AI 分析，直接保存当前已有数据（邮箱、关键词等），标记公司为已分析，安全返回

同时优化了 `run_search_task()` 的主循环：
- 在每次处理新关键词时重置任务状态为 `Running`，避免状态同步问题

#### 预期效果

- 点击「停止任务」后页面立即显示停止状态反馈
- 任务在 2-3 秒内（而非 30-60 秒）停止响应
- 已抓取但未完成 AI 分析的公司数据不会丢失，会以部分分析状态保存到数据库
- 停止后可通过「恢复」按钮继续未完成的搜索任务（断点续跑）

#### 涉及文件

| 文件 | 修改类型 |
|------|----------|
| `app/templates/discovery.html` | 前端交互优化 |
| `app/services/search_task_service.py` | 后端停止逻辑增强 |

---

---

## v2.2.0（2026-06-12）

### 新增：多语言搜索支持

#### 问题描述

搜索非英语国家（如 Poland、Spain）时，即使输入英文关键词+国家名，Google 搜索结果仍然以美国/英语公司为主。根本原因是：关键词是英文的，搜索参数（hl/lr/cr）也未限制到目标国家语言，导致 Google 优先返回英语世界的结果。

例如：搜索 "Poland" + "wastewater treatment" → 结果全是美国公司。

#### 修改方案

改造整个搜索链路，使系统能根据目标国家自动使用本地语言进行搜索：

1. **创建国家→语言映射表** — 覆盖 60+ 国家，精确映射每个国家的搜索语言和 Google 参数
2. **AI 关键词扩展增加多语言支持** — 输入英文关键词，AI 一次性完成翻译+扩展，生成目标国家语言的关键词列表
3. **SerpAPI 搜索增加国家/语言限制** — 设置 hl（界面语言）、lr（语言限制）、cr（国家限制）三个参数

#### 改造后的工作流

```
输入: 国家="Poland", 关键词="wastewater treatment"
  ↓
AI 翻译+扩展为波兰语关键词（一次API调用）:
["oczyszczalnia ścieków", "przetwarzanie ścieków", ...]
  ↓
SerpAPI 搜索:
hl=pl, lr=lang_pl, cr=countryPL, gl=pl
  ↓
结果: 波兰本地企业
```

#### 新增文件

| 文件 | 说明 |
|------|------|
| `app/services/country_language_map.py` | 国家→语言映射表（60+国家，含西班牙语、波兰语、阿拉伯语、法语、德语、俄语、日语等） |

#### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/services/keyword_expander.py` | `expand_keywords()` 新增 `country` 参数，非英语国家自动使用本地语言扩展 |
| `app/services/google_discovery.py` | 移除旧的 `_get_country_code()` 映射表，改用 `country_language_map`；`_fetch_via_serpapi()` 新增 hl/lr/cr 多语言参数 |
| `app/services/search_task_service.py` | 调用 `expand_keywords` 时传入 `country` |
| `app/api/routes.py` | 预览关键词 API 新增 `country` 参数 |
| `app/templates/discovery.html` | 预览关键词时传入 country，结果显示语言提示 |

#### 支持的语言及对应国家

| 语言 | 覆盖国家 |
|------|----------|
| 西班牙语 | Spain、Mexico、Argentina、Chile、Colombia 等 20 个西语国家 |
| 波兰语 | Poland |
| 阿拉伯语 | Saudi Arabia、UAE、Qatar、Kuwait、Egypt 等 18 个阿拉伯国家 |
| 法语 | France、Belgium、Morocco、Algeria、Tunisia 等 |
| 德语 | Germany、Austria |
| 意大利语 | Italy |
| 葡萄牙语 | Portugal、Brazil、Angola、Mozambique |
| 俄语 | Russia、Kazakhstan、Belarus 等 |
| 日语 | Japan |
| 韩语 | South Korea |
| 土耳其语 | Turkey |
| 泰语 | Thailand |
| 越南语 | Vietnam |
| 中文 | China、Taiwan、Hong Kong |
| 英语（增加国家限制） | UK、Australia、Canada、India、Singapore 等（保持英文但限制国家，不再搜到美国公司） |

---

## v2.2.1（2026-06-12）

### 新增：客户跟进状态管理 & 抓取失败可视化 & 局部重试

基于 V2.2 产品改进文档的两个高优先级方向，实现了 MVP 版本。

---

#### 方向① 客户跟进状态管理

**问题描述：** 系统只能「发现」和「分析」客户，但业务员无处记录跟进进度（如已发邮件、已回复、无效线索等），用完就关，没有复访动机。

**改进目标：** 让系统从「一次性分析工具」升级为「持续使用的客户管理平台」。

**数据层 — `app/database.py`**

Customer 模型新增三个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | String(20) | 跟进状态枚举：待联系（默认）/ 已发邮件 / 已回复 / 无效线索 / 成单 |
| `follow_up_date` | Date | 下次跟进日期 |
| `notes` | Text | 跟进备注文本 |

**后端 API — `app/api/routes.py`**

- `list_customers` 新增 `status` 查询参数，支持按跟进状态筛选
- 列表接口和详情接口均返回 `status` / `follow_up_date` / `notes` 字段
- 新增 `POST /api/customers/{id}/follow-up` 接口：更新跟进状态、日期、备注

**前端 — `app/templates/index.html`（客户列表页）**

- 表头新增「状态」列，每行显示带色块的状态标签（待联系=灰色 / 已发邮件=蓝色 / 已回复=绿色 / 无效线索=黑色 / 成单=黄色）
- 筛选栏新增「所有状态」下拉框，支持按状态筛选

**前端 — `app/templates/detail.html`（客户详情页）**

- 新增「跟进记录」卡片区，包含：跟进状态下拉 + 下次跟进日期输入 + 备注输入框 + 保存按钮
- 保存成功后显示绿色提示「已保存」，2秒后自动消失

---

#### 方向② 抓取失败可视化 & 局部重试

**问题描述：** 分析链路（搜索→抓取→AI分析→评分）较长，每一步都可能失败，但用户看到的结果都是「空数据」——分不清到底是真的没有数据，还是中途出错。

**改进目标：** 让数据状态对用户透明，支持局部重试，不需要重跑整个任务。

**数据层 — `app/database.py`**

Customer 模型新增三个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `scrape_status` | String(20) | 官网抓取状态：success / failed / partial / skipped |
| `ai_status` | String(20) | AI分析状态：success / failed / skipped |
| `fail_reason` | String(500) | 失败原因描述（如超时、反爬、API错误等） |

**后端分析流程写入状态 — `app/services/search_task_service.py`**

`_auto_analyze_and_save()` 中：
- 官网缓存命中 → `scrape_status=success`
- 官网抓取成功 → `scrape_status=success`
- 官网抓取失败 → `scrape_status=failed` + `fail_reason="官网抓取失败（网站可能无法访问或反爬）"`，标记已分析后安全返回
- AI分析成功 → `ai_status=success`
- AI分析失败 → `ai_status=failed` + `fail_reason="AI分析失败（API可能超时）"`

**后端 API — `app/api/routes.py`**

- `analyze_single` 分析过程中写入 `scrape_status` / `ai_status` / `fail_reason`
- 列表和详情接口返回上述状态字段
- 新增 `POST /api/customers/{id}/re-scrape`：重新抓取官网 + 重跑邮箱提取/关键词分析/评分，保留已有AI结果
- 新增 `POST /api/customers/{id}/re-analyze`：仅重新调用DeepSeek AI分析 + 重算评分，不重新抓取

**前端 — `app/templates/index.html`（客户列表页）**

- 来源列后方显示抓取状态图标（✅成功 / ❌失败 / ⚠️部分）+ AI状态图标（🧠成功 / 💀失败 / ⏭️跳过）
- 操作按钮组新增「重新抓取」和「重新AI分析」两个独立按钮（分别调用不同API）
- 鼠标悬停在状态图标上时通过 `title` 属性显示失败原因

**前端 — `app/templates/detail.html`（客户详情页）**

- 操作栏增加「重新抓取」「重新AI分析」按钮
- 基本信息区在发现来源标签旁显示状态图标（抓取成功/失败、分析成功/失败）

---

#### 涉及文件

| 文件 | 修改类型 |
|------|----------|
| `app/database.py` | Customer 模型新增 6 个字段（status/follow_up_date/notes/scrape_status/ai_status/fail_reason） |
| `app/api/routes.py` | 新增 3 个接口（跟进更新/重新抓取/重新分析），列表/详情接口新增状态字段返回，支持 status 筛选 |
| `app/services/search_task_service.py` | `_auto_analyze_and_save` 中写入 scrape_status/ai_status/fail_reason |
| `app/templates/index.html` | 新增状态列+状态筛选+状态图标+重新抓取/重新分析按钮 |
| `app/templates/detail.html` | 新增跟进记录区+状态图标+重新抓取/重新分析按钮 |

---

## v2.2.2（2026-06-12）

### 新增：客户评级、多字段搜索、数据库自动迁移

#### ① 客户自定义评级（重要性标记）

**问题描述：** 用户可以标记跟进状态，但缺乏一个独立于 AI 评分的「自定义重要性」标记。业务员想结合自己的判断给客户打星，区分哪些是自己认为重要的客户。

**改进内容：**

| 层面 | 修改 |
|------|------|
| **数据层** `database.py` | Customer 模型新增 `star_rating` 字段（Integer, 0=未评级, 1-5星），`init_db` 自动迁移添加该列 |
| **API** `routes.py` | 列表/详情接口返回 `star_rating`；`follow-up` 接口新增 `star_rating` 参数，保存时一并提交 |
| **列表页** `index.html` | 表头新增「评级」列，每行显示 ⭐ 星星图标（实心=已评级，空心=未评级） |
| **详情页** `detail.html` | 跟进记录区新增「客户评级」下拉（未评级 / 1星 ~ 5星） |

#### ② 多字段搜索增强

**问题描述：** 搜索框只能搜公司名，输入网址或邮箱找不到任何结果。

**改进内容：**

`app/api/routes.py` — `list_customers` 接口的搜索逻辑从仅匹配 `company_name` 改为 `OR` 匹配三个字段：
- `company_name`（公司名称）
- `website`（官网网址）
- `emails`（邮箱内容，JSON字符串模糊匹配）

现在输入公司名、网址片段或邮箱都能搜到对应的客户。

#### ③ 数据库自动迁移（Bug修复）

**问题描述：** v2.2.1 新增了 6 个字段后，已有的 `customers.db` 文件不会自动加列，运行时报错 `no such column: customers.status`。

**改进内容：**

`app/database.py` — `init_db()` 新增 `_migrate_add_column()` 函数，每次启动时检查 `customers` 表的实际列清单，发现缺失的列自动执行 `ALTER TABLE ADD COLUMN`。支持的自动迁移列：
- `status`、`follow_up_date`、`notes`
- `scrape_status`、`ai_status`、`fail_reason`
- `star_rating`

重启即可自动补齐缺失列，无需手动操作数据库。

---

#### 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `app/database.py` | 新增 `star_rating` 字段；`init_db()` 新增自动迁移逻辑 `_migrate_add_column()` |
| `app/api/routes.py` | 搜索改为多字段 OR（公司名/网址/邮箱）；列表/详情返回 `star_rating`；follow-up 接口支持 `star_rating` 参数 |
| `app/templates/index.html` | 表头新增「评级」列，渲染 ⭐ 星星图标 |
| `app/templates/detail.html` | 跟进记录区新增客户评级下拉；saveFollowUp 提交 `star_rating` |

---

## v2.2.3（2026-06-12）

### 新增：Tavily 搜索引擎支持

支持 Tavily API 作为 Google 搜索替代后端，通过环境变量动态切换。

**新增文件：**

| 文件 | 说明 |
|------|------|
| `app/services/tavily_discovery.py` | Tavily 搜索客户端，调用 `POST /search` 接口，支持分页去重 |

**修改文件：**

| 文件 | 修改内容 |
|------|----------|
| `app/services/google_discovery.py` | 重构为统一入口：`search_google()` 根据 `SEARCH_ENGINE` 环境变量或自动检测选择 SerpAPI / Tavily 实现；原有 SerpAPI 逻辑保留为内部函数 |
| `README.md` | 环境变量表新增 `TAVILY_API_KEY` 和 `SEARCH_ENGINE`，增加搜索引擎选择说明 |

**切换方式（三种）：**

```bash
# 1. 自动检测（优先 Tavily）
set TAVILY_API_KEY=tvly-your-key

# 2. 强制指定
set SEARCH_ENGINE=tavily
set TAVILY_API_KEY=tvly-your-key

# 3. 使用 SerpAPI（默认）
set SEARCH_ENGINE=serpapi
set SERPAPI_API_KEY=your-key
```

---

## v2.5.0（2026-06-16）

### 新增：相似客户扩展（种子客户扩展）

基于公司网址的相似客户扩展模块（V1简化版）。用户输入一个目标公司网址后，系统自动分析该公司业务内容，并在指定国家范围内搜索相似公司。

#### 工作流程

```
输入: https://example-water.com + Mexico
  ↓
抓取官网 → LLM提取行业/产品/关键词
  ↓
生成搜索组合（industry+country, product+country, keyword+companies+country）
  ↓
搜索引擎并发查询 → 去重过滤 → 规则相似度评分
  ↓
输出 Top 50 相似客户（含相似度评分）
```

#### 相似度评分规则

| 维度 | 权重 | 说明 |
|------|------|------|
| 关键词匹配 | 60% | 种子公司关键词在搜索结果标题/摘要中的命中率 |
| 行业一致性 | 30% | 行业词在搜索结果中的匹配度 |
| 内容相似度 | 10% | 是否含 company/service/supplier 等企业标识词 |

#### 新增文件

| 文件 | 说明 |
|------|------|
| `app/services/similar_company_finder.py` | 核心服务：官网抓取→LLM提取→搜索→评分→排序，完整串联5个步骤 |

#### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/api/routes.py` | 新增 `POST /api/discovery/similar-companies` 接口 |
| `app/templates/discovery.html` | 新增「相似客户扩展」卡片（输入框+进度条+结果表格+种子信息展示） |

---

## v2.6.0（2026-06-19）

### 三大改进 + 数据同步

#### ① 去重逻辑强化（搜索发现/Excel导入/相似客户扩展）

**问题**：搜索发现每次创建新客户从不查重，同一个公司被不同关键词搜到会重复入库（674个客户中有大量重复）。

**改进**：

**新增 `app/services/deduplication.py`**
- `normalize_company_name()` — 标准化公司名（去 Inc./Ltd./S.A. de C.V./GmbH 等法律后缀，去停用词）
- `is_similar_name()` — 判断公司名相似度（标准化相等 / 包含关系）
- `find_existing_customer()` — 综合查重（域名精确匹配 → 公司名模糊匹配）

**修改三个入口：**

| 入口 | 之前 | 之后 |
|------|------|------|
| 搜索发现 `search_task_service.py` | 每次创建新记录 | 先查域名+公司名，已存在则合并关键词 |
| Excel导入 `excel_importer.py` | 仅精确匹配公司名 | 域名 + 标准化名双重查重 |
| 相似客户 `similar_company_finder.py` | 仅搜索结果内去重 | 额外排除数据库中已有客户 |

**多语言支持验证：** 相似客户搜索时，种子公司关键词会自动翻译为目标国家本地语言（如 Mexico → 西班牙语），大幅提升非英语国家的匹配精度。

---

#### ② 自动化测试套件（129个测试）

**新增完整测试目录 `tests/`：**

```
tests/
├── test_scoring_engine.py      # 五维评分（29测试）
├── test_email_extractor.py     # 邮箱提取（16测试）
├── test_keyword_analyzer.py    # 关键词分析（15测试）
├── test_url_normalizer.py      # 网址标准化（14测试）
├── test_company_filter.py      # 黑名单过滤（27测试）
├── test_deduplication.py       # 去重工具（22测试）
└── conftest.py
```

覆盖全部核心纯逻辑模块，不依赖外部 API。运行方式：
```bash
source venv/bin/activate && pytest tests/ -v
```

---

#### ③ 数据库支持 PostgreSQL

通过 `DATABASE_URL` 环境变量切换：
```bash
# SQLite（默认，无需配置）
python3 main.py

# PostgreSQL
export DATABASE_URL=postgresql://user:pass@host/dbname
python3 main.py
```

---

#### ④ 多设备数据同步（网盘同步）

**新增同步 API：**

| API | 说明 |
|-----|------|
| `GET /api/sync/export` | 导出全部数据为 JSON（含缓存） |
| `POST /api/sync/import` | 导入数据，自动去重 |

**新增 `sync.sh` — 一键同步脚本：**
```bash
# 设备A：导出到 iCloud
./sync.sh export ~/Library/Mobile\ Documents/com~apple~CloudDocs/TradeData

# 设备B：从 iCloud 导入（自动去重）
./sync.sh import ~/Library/Mobile\ Documents/com~apple~CloudDocs/TradeData
```

支持 iCloud / Dropbox / Google Drive / USB 等多种传输方式，数据含客户信息 + 搜索缓存 + 官网缓存 + AI分析缓存，导入后不消耗额外 API 配额。

---

#### ⑤ 其他修复

- 修复 `SearchTask` 模型缺少 `task_log` 字段导致的 500 错误
- 弃用 `@app.on_event("startup")`，改用 FastAPI 推荐的 `lifespan` 模式

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `app/services/deduplication.py` | **新增** |
| `app/api/routes.py` | 修改 — 加 sync export/import + 去重工具导入 |
| `app/services/search_task_service.py` | 修改 — 搜索入库前去重 |
| `app/services/excel_importer.py` | 修改 — 导入前去重增强 |
| `app/services/similar_company_finder.py` | 修改 — 排除已有客户 + 本地语言相似搜索 |
| `app/database.py` | 修改 — PostgreSQL 支持 + search_tasks.task_log |
| `main.py` | 修改 — lifespan 替代 on_event |
| `requirements.txt` | 修改 — 加 pytest |
| `tests/` | **新增** — 7个文件，129个测试 |
| `sync.sh` | **新增** — 一键同步脚本 |
| `CHANGELOG.md` | 修改 — 本次更新日志 |

---

### 历史版本

- **v2.6.0** —— 去重强化 + 测试套件 + PostgreSQL + 多设备数据同步（当前版本）
- **v2.5.0** —— 相似客户扩展（种子客户）
- **v2.2.3** —— Tavily 搜索引擎支持
- **v2.2.2** —— 客户评级、多字段搜索、数据库自动迁移
- **v2.2.1** —— 客户跟进状态管理 & 抓取失败可视化 & 局部重试
- **v2.2.0** —— 多语言搜索支持
- **v2.0.1** —— 修复：停止任务按钮无响应问题
- **v2.0.0** —— 初始版本：客户发现 + 客户分析 + 客户数据库平台