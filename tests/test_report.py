"""渲染层测试：微信精简推送版（docs/推送格式.md 的可执行规范）"""
from domain.models import JobItem
import report


def _jobs():
    return [
        JobItem(company="字节跳动(社招)", job_id="s1", title="内容运营", location="上海",
                url="https://j.com/s1", recruit_type="社招", category="运营"),
        JobItem(company="腾讯", job_id="c1", title="产品策划", location="深圳",
                url="https://j.com/c1", recruit_type="校招", tags="2026届", category="产品"),
        JobItem(company="牛客日程", job_id="c2", title="运营专员", location="杭州",
                url="", recruit_type="校招", tags="2027届", category="运营"),
        JobItem(company="美团(社招)", job_id="old", title="老岗位", location="北京",
                url="https://j.com/o", recruit_type="社招", category="运营"),
    ]


def _new_keys():
    return {j.dedup_key for j in _jobs() if j.job_id != "old"}


class TestPushBrief:
    def test_only_new_jobs_included(self):
        content, n = report.generate_push_brief(_jobs(), _new_keys())
        assert n == 3
        assert "老岗位" not in content

    def test_social_before_campus(self):
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert content.index("💼 社招岗位") < content.index("🎓 校招岗位")

    def test_job_title_is_link(self):
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert "[内容运营 · 上海](https://j.com/s1)" in content

    def test_social_suffix_stripped(self):
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert "**字节跳动**" in content and "字节跳动(社招)" not in content

    def test_campus_year_label(self):
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert "产品策划（2026届） · 深圳" in content
        assert "运营专员（2027届） · 杭州" in content

    def test_no_url_falls_back_to_plain_text(self):
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert "运营专员（2027届） · 杭州" in content
        assert "[运营专员" not in content   # 无链接不渲染成 markdown 链接

    def test_company_job_count(self):
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert "**字节跳动**（1）" in content

    def test_star_for_high_match(self):
        # 腾讯产品策划：校招+方向+城市 = 90 分 → ⭐；字节内容运营（社招无经验信息）80 分无⭐
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert "⭐ 产品策划" in content
        assert "⭐ 内容运营" not in content

    def test_footer_present(self):
        content, _ = report.generate_push_brief(_jobs(), _new_keys())
        assert "📡 秋招雷达" in content

    def test_no_new_returns_one_liner(self):
        content, n = report.generate_push_brief(_jobs(), set())
        assert n == 0
        assert "无新增" in content and len(content) < 100

    def test_empty_section_omitted(self):
        social_only = [j for j in _jobs() if j.recruit_type == "社招"]
        keys = {j.dedup_key for j in social_only}
        content, _ = report.generate_push_brief(social_only, keys)
        assert "🎓 校招岗位" not in content
