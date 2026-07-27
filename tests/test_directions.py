"""方向覆盖契约测试：保证每个配置的求职方向从检索→过滤→推送全链路正常。

作用：任何人改动 config.KEYWORDS（增删方向、调关键词）后，CI 会检查——
- 每组方向的典型岗位仍能被检索命中并通过过滤链；
- 技术岗仍被正确排除（新词表不会把工程师/算法误纳入）；
- 命中的当天新增岗全部进推送，存量岗一个都不泄漏。
这样扩展方向词表时，"改坏了"会在合并前红，而不是等用户某天发现漏推/误推。
"""
import pytest

import config
import report
from domain.models import JobItem
from filters import filter_jobs, _match_keywords


def job(title, company="测试公司", location="上海", recruit_type="社招"):
    return JobItem(company=company, job_id=title, title=title,
                   location=location, url=f"https://x.com/{title}",
                   recruit_type=recruit_type)


# 每个方向组一个典型岗位标题（改词表时若新增方向，往这里补一行即可）。
# 用标题（而非现成 category）驱动，验证的是"标题兜底匹配"这条最脆弱的链路。
DIRECTION_SAMPLES = {
    "电商": "商家运营（天猫）",
    "产品": "产品经理-用户增长",
    "运营": "内容运营（社区方向）",
    "策展": "展览策划专员",
    "增长营销": "品牌营销经理",
    "市场公关": "品牌公关经理",
    "媒体内容": "内容编辑（时尚方向）",
    "商业分析": "战略分析师",
    "人力行政": "HRBP",
    "项目客户": "客户成功经理",
    "销售": "大客户销售经理",
    "设计创意": "品牌设计（包装方向）",
}

# 只测当前实际启用的方向（用户删组后不会因缺样本而误报失败）
_ACTIVE = [(d, t) for d, t in DIRECTION_SAMPLES.items() if d in config.KEYWORDS]

# 反例：技术岗必须始终被排除
TECH_TITLES = ["后端开发工程师", "资深算法专家", "前端研发", "测试开发工程师"]


@pytest.mark.parametrize("direction,title", _ACTIVE,
                         ids=[d for d, _ in _ACTIVE])
class TestDirectionPipeline:
    def test_keyword_hit(self, direction, title):
        assert _match_keywords(job(title)), f"方向[{direction}]的典型岗位'{title}'未被检索命中"

    def test_passes_filter(self, direction, title):
        assert filter_jobs([job(title)]), f"方向[{direction}]的'{title}'未通过过滤链"

    def test_enters_push(self, direction, title):
        j = job(title)
        content, n = report.generate_push_brief([j], {j.dedup_key})
        assert n == 1 and title in content, f"方向[{direction}]的'{title}'未进推送"


def test_all_configured_directions_have_sample():
    """每个启用的方向都得有测试样本——防止有人加方向却漏了覆盖"""
    missing = [d for d in config.KEYWORDS if d not in DIRECTION_SAMPLES]
    assert not missing, f"这些方向缺测试样本，请在 DIRECTION_SAMPLES 补一行：{missing}"


@pytest.mark.parametrize("title", TECH_TITLES)
def test_tech_jobs_excluded(title):
    assert not filter_jobs([job(title)]), f"技术岗'{title}'不应通过过滤"


def test_stock_not_leaked_only_new_pushed():
    """存量岗（非今日新增）不进推送，只推当天新增——用户的核心承诺"""
    jobs = [job(t) for t in list(DIRECTION_SAMPLES.values())[:6]]
    today_new = {j.dedup_key for j in jobs[:3]}         # 只有前 3 个是今日新增
    content, n = report.generate_push_brief(jobs, today_new)
    assert n == 3
    for stock in jobs[3:]:
        assert stock.title not in content, f"存量岗'{stock.title}'泄漏进了推送"
