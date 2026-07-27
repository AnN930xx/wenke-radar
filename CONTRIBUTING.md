# 贡献指南

先谢谢你愿意花时间 🙏 这个项目的目标很朴素：**让文科生每天早上少刷几十个招聘官网。**

不会写代码也能贡献：[提个 Issue](../../issues/new/choose) 告诉我们「某个源失效了」或「想加某公司」，
就已经很有帮助了。

---

## 最需要的贡献

| 优先级 | 类型 | 说明 |
|--------|------|------|
| 🔥 **最需要** | **文科对口机构的招聘源** | 美术馆、博物馆、出版社、文化公司、教育机构、咨询公司、非营利组织——这类源现在覆盖最薄 |
| 🔥 | **报告失效的源** | 公司改版官网后抓取会静默变空，你的一条 issue 能让所有人受益 |
| ⭐ | 快消 / 零售 / 新消费品牌的源 | 文科生的主要去向之一 |
| ⭐ | 方向关键词补充 | 发现某个岗位类型没被识别到，欢迎补 `config.KEYWORDS` |
| | Bug 修复、文档改进 | 随时欢迎 |

---

## ⚠️ 先读：合规红线（不可协商）

这个项目能长期活着，靠的是守住这几条。**不符合的 PR 不会被合并**，请别浪费你的时间：

- ❌ **不接需要登录的平台**——BOSS 直聘 / 智联 / 前程无忧 / 脉脉等，抓取违反其使用条款
- ❌ **不绕过反爬机制**——不破解签名、不打码验证码、不伪造登录态
- ❌ **不采集个人信息**——只要岗位信息，不碰候选人 / 员工 / 联系人数据
- ✅ **只调用公开招聘页面自身在用的接口**（浏览器打开该页面时它自己会发的那个请求）
- ✅ **每天一次的频率**，内置限速，对目标站点负载可忽略

判断标准很简单：**你不登录、用浏览器就能看到这些岗位吗？** 能，才可以接。

---

## 环境准备

```bash
git clone https://github.com/你的用户名/wenke-radar.git
cd wenke-radar
pip install -r requirements.txt

# Windows 必须带 PYTHONUTF8=1，否则中文/emoji 会报错
PYTHONUTF8=1 python -m pytest tests/ -q     # 应该 230 个全过
```

---

## 加一个新的招聘源

### 第 1 步：探接口

打开这家公司的招聘页 → F12 打开开发者工具 → Network 标签 → 刷新页面，
找那个返回岗位列表的请求（通常是 XHR/Fetch，响应里能看到岗位名）。

几个常见情况：
- 返回 JSON → 最理想，直接用
- 老站可能是 **form 编码**而不是 JSON（传 JSON 会被静默忽略，返回默认几条）
- 参数不生效 → 在页面里 hook `fetch`/`XHR` 抓真实请求体

### 第 2 步：判断用哪种接法（从省事到费事）

**A. 这家公司用现成的 ATS 平台？→ 加个子类 + 一段配置，不写解析代码**

看域名就能认出来：

| 平台 | 域名特征 | 用哪个基类 |
|------|---------|-----------|
| 北森 | `{公司}.zhiye.com` | `BeisenScraper` |
| 飞书 ATS | `jobs.{公司}.com` / `*.jobs.feishu.cn` | `FeishuAtsScraper` |
| 百库 | `{公司}.hotjob.cn` | `BaikuScraper` / `YiliScraper` |
| Moka | `app.mokahr.com` / 公司自有域名 | `MokaScraper` |

例（加一家北森的公司，全部代码就这些）：

```python
# scrapers/beisen.py
class YourCompanyScraper(BeisenScraper):
    name = "某公司"
```

```python
# config.py
COMPANY_CONFIG = {
    "某公司": {"host": "https://xxx.zhiye.com", "category": 2},  # 2=校招 1=社招
}
```

**B. 标准 JSON 接口？→ 零代码，写一段声明**

在 `config.GENERIC_SOURCES` 里加一段配置即可，格式见 `scrapers/generic.py` 文件顶部。

**C. 全新平台 → 新建 `scrapers/你的模块.py`**

继承 `BaseScraper`，只实现 `_fetch_items()` 返回 `List[JobItem]`：

```python
from .base import BaseScraper, JobItem, guess_category
import config

class YourScraper(BaseScraper):
    name = "某公司"

    def _fetch_items(self):
        items = []
        page = 1
        while True:
            r = self.session.post(URL, json={...}, timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            batch = data.get("list") or []
            if not batch:
                break
            items.extend(batch)
            self.reported_total = data.get("total")   # ← 完整性对账要用，别漏
            if len(items) >= (self.reported_total or 0):
                break
            page += 1
        return [self._parse(it) for it in items]

    def _parse(self, it):
        return JobItem(
            company=self.name,
            job_id=str(it["id"]),          # 必须是平台原生的稳定 id
            title=it["name"],
            category=guess_category(it["name"]),
            location=it.get("city", ""),
            url=f"https://.../job/{it['id']}",
        )
```

### 第 3 步：注册三处

```python
scrapers/__init__.py   →  SCRAPERS = {"某公司": YourScraper, ...}
config.py              →  ENABLED_COMPANIES = {"某公司": True, ...}
report.py              →  COMPANY_ORDER 里加上（社招源放末尾）
```

### 第 4 步：⚠️ 社招源必做

社招源**必须**设 `recruit_type="社招"`（基类通过 config 的 `job_nature` 或类属性设置）。

漏了会导致：届别豁免失效、经验过滤失效、每日新增判断失效——**整套社招逻辑全废**，
而且不会报错，只会静默出错。这是本项目历史上踩过最多次的坑。

### 第 5 步：验收（PR 前请自查）

```bash
# 1. 单独跑一下新源，看抓到多少、性质对不对
PYTHONUTF8=1 python stress_test.py 某公司

# 2. 录 fixture（存一份真实响应样本，之后 CI 离线回放测解析）
PYTHONUTF8=1 python tests/record_fixtures.py 某公司

# 3. 跑全量测试
PYTHONUTF8=1 python -m pytest tests/ -q
```

自查清单：

- [ ] 抓到的岗位数量和官网上看到的**大致对得上**（不是只抓到第一页）
- [ ] `recruit_type` 对（校招/社招）
- [ ] `job_id` 用的是平台原生稳定 id（每次抓同一个岗位要得到同一个 id，否则每天都会误报"新增"）
- [ ] `url` 点开能直接到投递页
- [ ] 抓取日志里没有 `抓取失败` / `Traceback`
- [ ] fixture 已录、`pytest` 全绿

---

## 代码规范

**唯一的硬要求：别混层。** 依赖只能向上，禁止反向或环形（有 `test_layering.py` 用 AST 静态检查兜底）：

```
config → domain → scrapers → filters/scoring → store → report/tracker → push → main
```

自查方法：一个函数如果同时在「抓数据」和「判断合不合格」，
或者同时在「算业务规则」和「拼 Markdown」，就是混了，拆开。

其余：
- 跟着周围代码的风格写（注释密度、命名、习惯用法）
- 注释写**为什么**，不写「这行代码做了什么」
- 不引入新的第三方依赖，除非确实必要（目前只有 5 个）

---

## 提 PR

1. 从 `main` 开个分支：`git checkout -b add-source-某公司`
2. 提交前跑 `pytest` 确认全绿
3. PR 描述里说清楚：**加了什么源 / 抓到多少岗位 / 怎么验证的**
4. CI 会自动跑测试，绿了就可以合

不确定该怎么做？**先开个 Issue 聊聊**，别闷头写完发现方向不对。

---

## 行为准则

这个项目服务的是正在找工作、可能正焦虑的人。请对彼此友善、有耐心。
提问不用道歉，回答不必居高临下。就这样。
