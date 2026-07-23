"""批次22 新增能力测试：enrichment 解析 / 可投程度评分 / 岗位事件流"""
import pytest

import store
import scoring
from domain.models import JobItem
from domain.enrich import parse_min_experience_years, enrich
from filters import filter_jobs


# ==================== enrichment ====================

class TestEnrich:
    def test_min_years_from_range(self):
        assert parse_min_experience_years("1-3年经验") == 1
        assert parse_min_experience_years("3-5年产品经验") == 3

    def test_none_when_absent(self):
        assert parse_min_experience_years("负责社区内容运营") is None
        assert parse_min_experience_years("") is None

    def test_enrich_fills_field(self):
        j = JobItem(company="A", job_id="1", title="运营", description="3年以上运营经验")
        enrich(j)
        assert j.experience_min_years == 3

    def test_social_senior_dropped_via_description(self):
        # 经验判断已从抓取期搬到过滤层：description 带"3年以上"的社招岗被过滤
        senior = JobItem(company="A", job_id="1", title="内容运营", location="上海",
                         recruit_type="社招", description="3年以上内容运营经验")
        junior = JobItem(company="A", job_id="2", title="内容运营", location="上海",
                         recruit_type="社招", description="1-3年经验或应届优秀者")
        kept = filter_jobs([senior, junior])
        assert [j.job_id for j in kept] == ["2"]


# ==================== 评分 ====================

def job(**kw):
    base = dict(company="A", job_id="1", title="内容运营", category="运营",
                location="上海", recruit_type="社招")
    base.update(kw)
    return JobItem(**base)


class TestScoring:
    def test_campus_direction_city_is_high_match(self):
        s, reasons = scoring.score_job(job(recruit_type="校招"))
        assert s >= scoring.STAR_THRESHOLD
        assert any("校招" in r for r in reasons)

    def test_social_unknown_experience_moderate(self):
        s, _ = scoring.score_job(job())
        assert 70 <= s < scoring.STAR_THRESHOLD

    def test_low_experience_boost(self):
        j = job(description="1-3年经验")
        enrich(j)
        s, reasons = scoring.score_job(j)
        assert s >= scoring.STAR_THRESHOLD
        assert any("可投" in r for r in reasons)

    def test_stale_posting_penalty(self):
        fresh, _ = scoring.score_job(job(publish_time="2026-07-20"))
        stale, _ = scoring.score_job(job(publish_time="2026-01-01"))
        assert fresh > stale

    def test_tier_labels(self):
        assert scoring.tier(90) == "高度匹配"
        assert scoring.tier(75) == "值得尝试"
        assert scoring.tier(60) == "一般"


# ==================== 岗位事件流 ====================

@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))


def mk(company, n, prefix="j"):
    return [JobItem(company=company, job_id=f"{prefix}{i}", title=f"岗位{i}",
                    location="上海") for i in range(n)]


def events():
    import sqlite3
    conn = sqlite3.connect(store.DB_PATH)
    rows = conn.execute("SELECT company, job_id, event FROM job_events"
                        " ORDER BY rowid").fetchall()
    conn.close()
    return rows


class TestJobEvents:
    def test_lifecycle_events(self):
        store.save_jobs(mk("A", 2))                       # 小批量 → CREATED×2
        assert [e[2] for e in events()] == ["CREATED", "CREATED"]

        store.save_jobs(mk("A", 1))                       # j1 下线 → CLOSED
        assert events()[-1] == ("A", "j1", "CLOSED")

        store.save_jobs(mk("A", 2))                       # j1 重新出现 → REOPENED
        assert events()[-1] == ("A", "j1", "REOPENED")

    def test_update_event_on_title_change(self):
        store.save_jobs(mk("A", 1))
        changed = [JobItem(company="A", job_id="j0", title="岗位0-改名", location="上海")]
        store.save_jobs(changed)
        assert events()[-1] == ("A", "j0", "UPDATED")

    def test_bootstrap_event(self):
        store.save_jobs(mk("新大厂", 6))
        assert {e[2] for e in events()} == {"BOOTSTRAP"}
