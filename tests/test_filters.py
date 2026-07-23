"""过滤层单元测试——全部纯函数，钉死历史上踩过坑的规则。

覆盖：届别解析、届别分桶、经验年限判定（含"1-3年取下限"回归坑）、
校招/社招两条过滤链、城市/实习/资深/技术岗排除。
"""
from domain.models import JobItem
from filters import parse_recruit_year, campus_year_bucket, filter_jobs
from scrapers.base import demands_senior_experience


def job(title, company="测试公司", location="上海", category="", tags="",
        recruit_type="校招"):
    return JobItem(company=company, job_id=title, title=title, category=category,
                   location=location, tags=tags, recruit_type=recruit_type)


# ==================== 届别解析 ====================

class TestParseRecruitYear:
    def test_full_year(self):
        assert parse_recruit_year("2026届管培生") == "2026"

    def test_short_year_with_suffix(self):
        assert parse_recruit_year("26届秋招") == "2026"
        assert parse_recruit_year("27秋招聘") == "2027"
        assert parse_recruit_year("26春招") == "2026"

    def test_multi_year(self):
        assert parse_recruit_year("2026/2027届联合招聘") == "2026/2027"

    def test_no_year_is_rolling(self):
        assert parse_recruit_year("管培生（滚动招聘）") == "不限"
        assert parse_recruit_year("") == "不限"

    def test_salary_number_not_matched(self):
        # (?<!\d) 断言：薪资数字里不应解析出届别
        assert parse_recruit_year("月薪20000起") == "不限"


class TestCampusYearBucket:
    def test_2026_priority_over_2027(self):
        # 双届岗归入更受关注的 2026 桶
        assert campus_year_bucket(job("2026/2027届产品培训生")) == "2026"

    def test_2027_bucket(self):
        assert campus_year_bucket(job("2027届秋招提前批")) == "2027"

    def test_rolling_bucket(self):
        assert campus_year_bucket(job("产品管培生")) == "不限·其他"


# ==================== 经验年限判定 ====================

class TestSeniorExperience:
    def test_over_threshold(self):
        assert demands_senior_experience("3年以上产品经验", max_years=2)
        assert demands_senior_experience("5年+运营经验", max_years=2)

    def test_range_takes_lower_bound(self):
        # 历史回归坑（错误日志#15）："1-3年"按下限 1 年算，应保留
        assert not demands_senior_experience("1-3年经验", max_years=2)
        assert demands_senior_experience("3-5年相关经验", max_years=2)

    def test_chinese_numerals(self):
        assert demands_senior_experience("三年以上工作经验", max_years=2)
        assert not demands_senior_experience("两年运营经历", max_years=2)

    def test_graduation_year_not_confused(self):
        # "2026年" 里的 "26年" 不能被当成经验年限
        assert not demands_senior_experience("2026年毕业生优先", max_years=2)

    def test_empty(self):
        assert not demands_senior_experience("", max_years=2)
        assert not demands_senior_experience(None, max_years=2)


# ==================== 过滤链 ====================

class TestFilterCampus:
    def test_matched_kept(self):
        assert filter_jobs([job("产品经理（2026届）")])

    def test_intern_excluded(self):
        assert not filter_jobs([job("产品经理实习生")])

    def test_old_year_excluded(self):
        assert not filter_jobs([job("2024届产品经理专场")])

    def test_tech_excluded(self):
        assert not filter_jobs([job("算法工程师（推荐方向）")])

    def test_wrong_city_excluded(self):
        assert not filter_jobs([job("产品经理", location="成都")])

    def test_empty_location_kept(self):
        # 没写地点/全国岗保留（宁多勿漏）
        assert filter_jobs([job("产品经理", location="")])
        assert filter_jobs([job("产品经理", location="全国")])


class TestFilterSocial:
    def test_social_exempt_from_year_and_intern(self):
        # 社招不受届别限制（"2024"字样不排除社招岗）
        assert filter_jobs([job("产品经理（2024年入职）", recruit_type="社招")])

    def test_senior_title_excluded(self):
        assert not filter_jobs([job("资深产品经理", recruit_type="社招")])
        assert not filter_jobs([job("高级运营专家", recruit_type="社招")])

    def test_entry_level_kept(self):
        assert filter_jobs([job("内容运营", recruit_type="社招")])
