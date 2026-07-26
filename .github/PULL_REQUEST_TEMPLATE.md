# 这个 PR 做了什么

<!-- 一两句话说清楚。加源的话写：加了哪家公司、走的哪个平台 -->

## 类型

- [ ] 加了新的招聘源
- [ ] 修了失效的源
- [ ] Bug 修复
- [ ] 文档 / 其他

## 如果是加源，请确认

- [ ] 这家公司的岗位**不用登录**、浏览器直接就能看到（合规红线，见 [CONTRIBUTING](../CONTRIBUTING.md)）
- [ ] 抓到的岗位数量和官网上**大致对得上**（不是只抓到第一页）
- [ ] 社招源已设 `recruit_type="社招"`（漏了会让整套社招过滤静默失效）
- [ ] `job_id` 用的是平台原生稳定 id（不是自己拼的、每次都变的）
- [ ] `url` 点开能直接到投递页
- [ ] 已录 fixture：`python tests/record_fixtures.py 某公司`
- [ ] 三处都注册了：`scrapers/__init__.py` / `config.ENABLED_COMPANIES` / `report.COMPANY_ORDER`

## 验证情况

<!-- 贴一下你跑的结果，例如：
PYTHONUTF8=1 python stress_test.py 某公司
→ 抓到 37 个岗位，recruit_type 全是 {'校招'}，官网上是 40 个（3 个是已下线的）
-->

- [ ] `PYTHONUTF8=1 python -m pytest tests/ -q` 全绿
