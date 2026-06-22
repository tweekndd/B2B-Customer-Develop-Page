# 更新日志

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