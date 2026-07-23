# 📡 文科生求职雷达 · WenKe Radar

**面向非技术/泛商业方向求职者的官方岗位增量雷达。**
每天定时抓取 **39 个招聘源**（大厂校招 + 社招官网 API），按你的求职画像过滤出
真正能投的岗位，只报「今日新增」，微信推送到手机——
Fork 仓库、改一份配置、加一个 Secret 就能跑，零服务器、零运维、零费用。

> 你不该每天刷几十个招聘官网；你只需要知道：**今天新放出了哪些我能投的岗。**

## 为谁而做

产品 / 运营 / 电商 / 策展 / 增长营销 / 市场公关 / 媒体内容 / 商业分析 / 人力行政 /
项目管理 / 客户成功——默认方向词表覆盖非技术岗全谱系，文科、商科、艺术背景都适用。
不想看的方向，删掉配置里对应的组即可。

## ✨ 核心能力

- **39 个源官方接口直连**：腾讯/字节/阿里/百度/美团/京东/小红书/B站/小米/滴滴等大厂
  校招+社招，泡泡玛特/名创优品/蒙牛/伊利/欧莱雅/农夫山泉等快消，UCCA 等文化机构，
  牛客/OfferStar 聚合兜底——含 AES 响应解码、动态令牌、老式表单接口等已适配的硬协议
- **只报每日新增**：与历史库对比，今天新出现的岗位才推送；存量不打扰
- **求职画像过滤**：方向 × 城市 × 届别窗口 × 排实习 × 社招排资深
  （含 JD 正文经验年限解析："3-5年"自动排除、"1-3年"保留）
- **可投程度评分**：方向强度/城市/应届友好/经验门槛/新鲜度加权，高分岗排前带 ⭐
- **数据可信三层防线**：抓取完整性对账（防"只抓到一半却当成全量"）、
  归档骤降守卫、新源 bootstrap 静默——不漏报、不乱报、不重复
- **微信精简推送**：只列当天有新岗的公司，岗位名即投递链接；支持多人同时接收
- **投递进度追踪**：登记状态/反馈/下一步，导出带配色的 Excel
- **接新源成本极低**：飞书 ATS / 北森 / 百库 / Moka 平台基类，同平台新公司几行配置；
  标准 JSON 接口用 GenericScraper 零代码声明式接入
- **GitHub Actions 全托管**：每天定时运行（含备份触发点抗 cron 延迟），
  数据库 Actions cache + artifact 快照双保险

## 🚀 五分钟部署

1. **Fork 本仓库**（建议保持私有）
2. **开启 Actions**：仓库 Settings → Actions → 允许运行
3. **配置微信推送**：[sct.ftqq.com](https://sct.ftqq.com/) 微信扫码复制 SendKey →
   仓库 Settings → Secrets → New secret，Name `PUSH_KEY`，Value 填 SendKey
   （多人接收：多个 SendKey 逗号拼接；企业微信机器人用 `WECOM_KEY`）
4. **定制画像**：编辑 `config.py` —— 方向词表 KEYWORDS、目标城市 TARGET_CITIES、
   届别窗口 TARGET_GRAD_YEARS、经验阈值 SOCIAL_MAX_EXPERIENCE_YEARS
5. **手动跑一次**：Actions → 秋招雷达日报 → Run workflow，微信收到推送即部署成功

之后每天北京时间 09:00 自动推送（10:00 备份触发点自动兜底 GitHub cron 延迟）。

### 本地运行

```bash
pip install -r requirements.txt
# Windows 需带 PYTHONUTF8=1
PYTHONUTF8=1 python main.py --full   # 首次全量建库
PYTHONUTF8=1 python main.py          # 日常增量
PYTHONUTF8=1 python -m pytest tests/ -q   # 跑测试（96 个）
```

## ⚙️ 接一个新源

1. 公司用北森/飞书/百库/Moka 平台？→ 加子类 + config 参数即可
2. 标准 JSON 接口？→ `config.GENERIC_SOURCES` 写一段声明，零代码
3. 全新平台 → `scrapers/` 新建模块：继承 `BaseScraper`，`fetch()` 返回 `List[JobItem]`，
   在 `scrapers/__init__.py`、`config.py`、`report.py` 三处注册

改解析代码后跑 `pytest`——31 个源有真实响应 fixture 契约测试，改坏了 CI 会拦住。

## 🛡️ 合规与自律

- 仅调用各公司**公开招聘页面自身使用的官方接口**，不绕过任何登录，不采集个人信息
- 每日一次的抓取频率，对目标站点负载可忽略；内置限速与重试退避
- 涉及的响应解码仅用于读取页面上人人可见的公开岗位数据
- 若目标公司对被收录有异议，提 issue 即从源列表移除
- 使用本工具产生的一切后果由使用者自行承担

## 🙏 致谢

项目思路启发自 [ruyi1/campus-radar](https://github.com/ruyi1/campus-radar)，代码为本项目独立实现。

## License

[MIT](LICENSE)
