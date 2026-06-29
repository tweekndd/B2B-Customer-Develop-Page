# Hunter API 邮箱查找方案

> 基于 Hunter.io API V2 实现「通过公司域名 + 姓名查找内部联系人邮箱」功能
>
> 适用场景：已有目标公司列表，需要找到公司内特定人员（或全部人员）的邮箱

---

## 一、整体流程

```
用户输入公司域名 / 姓名
       │
       ▼
┌──────────────────────┐
│  Step 1: Email Count  │  ← 免费，先查该域名有多少邮箱
│  (查数据量，决定策略)  │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Step 2: 选择查找模式  │
│                      │
│  ┌─ A: Domain Search │  ← 免费（消耗搜索额度）
│  │  全量拉取公司邮箱   │     按部门/级别筛选
│  │                   │
│  └─ B: Email Finder  │  ← 消耗积分，精确找某人
│     按姓名精确查找     │     域名 + 名 + 姓
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Step 3: Email Verify │  ← 消耗验证额度
│  验证邮箱有效性       │     返回 valid/accept_all/unknown
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  输出结果             │
│  邮箱 + 姓名 + 职位   │
│  + 验证状态 + 来源    │
└──────────────────────┘
```

---

## 二、API 详解

### 2.1 Email Count（查数据量）

> **免费**，不消耗任何额度

```
GET https://api.hunter.io/v2/email-count?domain=stripe.com&api_key=YOUR_KEY
```

**用途：** 在正式搜索前，先查看 Hunter 数据库中有多少该公司的邮箱，判断数据覆盖率。

**返回示例：**
```json
{
  "data": {
    "total": 81,
    "personal_emails": 65,
    "generic_emails": 16,
    "department": {
      "executive": 10,
      "it": 0,
      "finance": 8,
      "sales": 0,
      "marketing": 0,
      "hr": 0,
      ...
    },
    "seniority": {
      "junior": 13,
      "senior": 5,
      "executive": 2
    }
  }
}
```

**关键字段说明：**

| 字段 | 含义 |
|:-----|:------|
| `total` | 该域名下总邮箱数 |
| `personal_emails` | 个人邮箱数（有价值的目标） |
| `generic_emails` | 通用邮箱数（info@, support@ 等） |
| `department.*` | 按部门的邮箱分布 |
| `seniority.*` | 按级别的邮箱分布 |

---

### 2.2 Domain Search（按域名全量搜索）

> **消耗搜索额度**（套餐内免费额度），不消耗验证积分

```
GET https://api.hunter.io/v2/domain-search?domain=intercom.com&api_key=YOUR_KEY
```

**支持筛选参数：**

| 参数 | 类型 | 说明 |
|:-----|:-----|:------|
| `domain` | string | **必填**，公司域名 |
| `company` | string | 公司名称（与 domain 二选一，domain 优先） |
| `type` | string | `personal` 或 `generic`，筛选个人/通用邮箱 |
| `seniority` | string | 级别筛选：`junior` / `senior` / `executive` |
| `department` | string | 部门筛选：`executive` / `it` / `finance` / `sales` / `marketing` / `hr` / `legal` / `support` / `communication` 等 |
| `limit` | int | 每页结果数（Free 用户最大 10） |
| `offset` | int | 分页偏移量（Free 用户 limit + offset ≤ 10） |

**返回示例：**
```json
{
  "data": {
    "domain": "intercom.com",
    "emails": [
      {
        "value": "ciaran@intercom.com",
        "type": "personal",
        "confidence": 92,
        "first_name": "Ciaran",
        "last_name": "Lee",
        "position": "Support Engineer",
        "seniority": "senior",
        "department": "it",
        "linkedin": null,
        "twitter": "ciaran_lee",
        "verification": {
          "date": "2019-12-06",
          "status": "valid"
        },
        "sources": [
          { "domain": "github.com", "uri": "http://github.com/ciaranlee", "extracted_on": "2015-07-29" }
        ]
      }
    ],
    "pattern": "{first}",
    "organization": "Intercom"
  },
  "meta": {
    "results": 35,
    "limit": 10,
    "offset": 0
  }
}
```

**使用场景：**
- ✅ 地毯式搜索某公司**所有人**的邮箱
- ✅ 按部门筛选（只找销售/技术/高管）
- ✅ 按级别筛选（只找总监/高管）
- ⚠️ Free 计划每页最多 10 条，总数限制 10 条

---

### 2.3 Email Finder（按姓名精确查找）

> **消耗搜索额度**，如果找不到邮箱**不扣费**

```
GET https://api.hunter.io/v2/email-finder?domain=reddit.com&first_name=Alexis&last_name=Ohanian&api_key=YOUR_KEY
```

**参数：**

| 参数 | 说明 |
|:-----|:------|
| `domain` | 公司域名（与 `company` / `linkedin_handle` 三选一） |
| `company` | 公司名称 |
| `linkedin_handle` | LinkedIn 个人主页 handle |
| `first_name` | 名（与 `full_name` 二选一） |
| `last_name` | 姓 |
| `full_name` | 全名（拆成 first+last 效果更好） |
| `max_duration` | 最长等待秒数（3-20 秒，默认 10），时间越长准确率越高 |

**返回示例：**
```json
{
  "data": {
    "email": "alexis@reddit.com",
    "first_name": "Alexis",
    "last_name": "Ohanian",
    "position": "Co-Founder",
    "confidence": 99,
    "verification": {
      "date": "2024-01-15",
      "status": "valid"
    },
    "sources": [...]
  }
}
```

**使用场景：**
- ✅ 已知某人姓名 + 公司，精确查找其邮箱
- ✅ 通过 LinkedIn 链接反向查邮箱
- ✅ 找不到不扣费，零成本尝试

---

### 2.4 Email Verifier（邮箱验证）

> **消耗验证额度**

```
GET https://api.hunter.io/v2/email-verifier?email=patrick@stripe.com&api_key=YOUR_KEY
```

**返回状态：**

| 状态 | 含义 |
|:-----|:------|
| `valid` | 邮箱有效 ✅ |
| `accept_all` | 服务器接收所有邮件（无法确定具体地址是否有效）⚠️ |
| `unknown` | 无法验证 ❓ |
| `invalid` | 邮箱无效 ❌ |

**使用场景：**
- ✅ 对 Domain Search / Email Finder 返回的邮箱做二次验证
- ✅ 群发前批量验证，提高送达率

---

## 三、套餐与额度

Hunter 按套餐提供不同的额度（以官方最新价格为准）：

| 套餐 | 搜索额度/月 | 验证额度/月 | 每页最大结果 | 分页 |
|:----|:-----------|:-----------|:-----------|:----|
| Free | 25 | 50 | 10 | ❌（最多 10 条） |
| Starter | 500 | 1,000 | 10 | ❌ |
| Growth | 5,000 | 10,000 | 100 | ✅ |
| Business | 15,000 | 30,000 | 100 | ✅ |
| Enterprise | 50,000 | 100,000 | 100 | ✅ |

> **关键限制：** Free 和 Starter 计划 **不能分页**，只能拿到前 10 条。Growth 以上才能全量拉取。

---

## 四、推荐实现方案

### 方案一：按域名全量搜索（推荐起步）

```
用户输入：公司域名（如 stripe.com）
   │
   ▼
Step 1: Email Count → 看有多少邮箱可查
   │
   ▼
Step 2: Domain Search → 拉取邮箱列表
   │         ├─ 可按 department 筛选（只找 executive / sales）
   │         └─ 可按 seniority 筛选（只找 senior / executive）
   │
   ▼
Step 3: Email Verifier → 批量验证（可选）
   │
   ▼
返回结果：邮箱 + 姓名 + 职位 + 验证状态
```

**适用场景：** 想了解某公司有哪些人、给整个部门发邮件

### 方案二：按姓名精确查找

```
用户输入：公司域名 + 姓名（如 stripe.com + "Patrick Collison"）
   │
   ▼
Step 1: Email Finder（域名 + first_name + last_name）
   │
   ▼
Step 2: Email Verifier（验证结果）
   │
   ▼
返回结果：邮箱 + 验证状态 + 置信度
```

**适用场景：** 已经知道要找谁，只需要补全邮箱

### 方案三：混合模式（批量搜索 + 精确查找）

```
用户输入：公司域名列表
   │
   ▼
Domain Search → 拿到全部人员 → 去重
   │
   ▼
对每个人员 → 如置信度低 → Email Finder 补充查找
   │
   ▼
Email Verifier 批量验证
   │
   ▼
导出最终结果
```

---

## 五、Python 代码示例

### 基础封装

```python
import requests


class HunterClient:
    """Hunter API 客户端"""

    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """通用 GET 请求"""
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        resp = requests.get(f"{self.BASE_URL}/{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()

    def email_count(self, domain: str) -> dict:
        """查询域名下的邮箱数量"""
        return self._get("email-count", {"domain": domain})

    def domain_search(
        self,
        domain: str,
        department: str = None,
        seniority: str = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """按域名搜索邮箱"""
        params = {"domain": domain, "limit": limit, "offset": offset}
        if department:
            params["department"] = department
        if seniority:
            params["seniority"] = seniority
        return self._get("domain-search", params)

    def email_finder(
        self,
        domain: str = None,
        first_name: str = None,
        last_name: str = None,
        full_name: str = None,
        linkedin_handle: str = None,
    ) -> dict:
        """按姓名找邮箱"""
        params = {}
        if domain:
            params["domain"] = domain
        if first_name and last_name:
            params["first_name"] = first_name
            params["last_name"] = last_name
        elif full_name:
            params["full_name"] = full_name
        if linkedin_handle:
            params["linkedin_handle"] = linkedin_handle
        return self._get("email-finder", params)

    def email_verifier(self, email: str) -> dict:
        """验证邮箱"""
        return self._get("email-verifier", {"email": email})
```

### 使用示例

```python
client = HunterClient(api_key="YOUR_API_KEY")

# 1. 先查公司邮箱总量
count = client.email_count("stripe.com")
print(f"Stripe 共有 {count['data']['total']} 个邮箱")
print(f"  高管: {count['data']['department']['executive']} 个")

# 2. 搜索所有高管邮箱
result = client.domain_search("stripe.com", seniority="executive")
for email in result["data"]["emails"]:
    print(f"{email['first_name']} {email['last_name']} - {email['value']}")

# 3. 精确查找某人
result = client.email_finder(domain="stripe.com", first_name="Patrick", last_name="Collison")
print(f"找到邮箱: {result['data']['email']}")

# 4. 验证邮箱
result = client.email_verifier("patrick@stripe.com")
print(f"验证状态: {result['data']['status']}")
```

---

## 六、常见场景与查询策略

### 场景 1：我想找某公司的销售负责人

```python
# 按部门筛选
result = client.domain_search("acme.com", department="sales", seniority="executive")
```

### 场景 2：我想找某公司的 CTO

```python
# 方案 A: Domain Search + 高管级别筛选
result = client.domain_search("acme.com", seniority="executive")

# 方案 B: 如果知道名字，用 Email Finder
result = client.email_finder(domain="acme.com", first_name="John", last_name="Doe")
```

### 场景 3：我有一批公司，想找出所有市场部的人

```python
domains = ["company1.com", "company2.com", "company3.com"]
all_marketing = []

for domain in domains:
    result = client.domain_search(domain, department="marketing")
    all_marketing.extend(result["data"]["emails"])
```

### 场景 4：批量验证邮箱有效性

```python
emails = ["ceo@company.com", "cto@company.com"]
for email in emails:
    result = client.email_verifier(email)
    print(f"{email} → {result['data']['status']}")
```

---

## 七、注意事项

### 1. 速率限制

| API | 限制 |
|:----|:-----|
| Domain Search | 15 请求/秒，500 请求/分 |
| Email Finder | 15 请求/秒，500 请求/分 |
| Email Verifier | 10 请求/秒 |
| Email Count | 15 请求/秒 |
| 所有 API | 429 状态码 = 触发限流，需等待后重试 |

### 2. Free 计划限制

- **搜索总额度 25 次/月**（Domain Search + Email Finder 合计）
- 每页最多 **10 条结果**
- **不支持分页**（limit + offset 不能超过 10）
- 验证额度 50 次/月
- 建议先用 Email Count 评估数据量再决定是否搜索

### 3. 结果不可用时

- Hunter 找不到邮箱返回 **404**（不是空数组）
- Email Finder 找不到 **不扣积分**
- 部分邮箱验证状态为 `accept_all`（服务器接收所有邮件，不一定能到达具体收件箱）

### 4. 数据来源

Hunter 的邮箱来自公开网页抓取，可能**不是最新的**。建议：
- 对重要的联系人多验证一次
- 结合 LinkedIn 等渠道交叉验证

---

## 八、与本项目集成建议

当前项目（AI Trade Customer Analyzer）已有以下服务模块可直接复用：

| 现有模块 | 作用 | 与 Hunter 配合 |
|:---------|:-----|:--------------|
| `website_scraper.py` | 抓取公司网站 | 提取域名给 Hunter |
| `email_extractor.py` | 从网页提取邮箱 | 可作为 Hunter 的补充/验证 |
| `company_filter.py` | 公司筛选过滤 | 筛选后传给 Hunter 查邮箱 |
| `search_task_service.py` | 管理搜索任务 | 可用于管理 Hunter 搜索任务 |

**建议集成位置：**
1. 在 `app/services/` 下新建 `hunter_service.py`，封装上述 HunterClient
2. 在客户详情页增加「查找邮箱」按钮，调用 Hunter API
3. 在客户发现流程中，发现新公司后自动查询其联系人邮箱

---

## 九、参考链接

- Hunter API 官方文档: https://hunter.io/api-documentation/v2
- API Key 管理: https://hunter.io/api-keys
- 套餐价格: https://hunter.io/pricing
- 技术栈列表: https://hunter.io/files/technologies.json
- 行业分类列表: https://hunter.io/files/industries.json
