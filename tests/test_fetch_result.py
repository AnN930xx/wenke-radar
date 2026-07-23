"""FetchResult 完整性协议测试 + suspect 源跳过归档"""
import store
from domain.models import JobItem
from domain.results import FetchResult


def fr(**kw):
    base = dict(source="测试源", fetched=100, raw_fetched=100,
                reported_total=100, success=True, duration_s=1.0)
    base.update(kw)
    return FetchResult(**base)


class TestComplete:
    def test_full_fetch_is_complete(self):
        assert fr().complete is True

    def test_partial_fetch_incomplete(self):
        # 服务端说 100，只拿到 20 → 疑似分页断裂
        assert fr(raw_fetched=20).complete is False

    def test_ratio_tolerance(self):
        # 90% 容差内算抓全（翻页期间岗位实时上下线的正常抖动）
        assert fr(raw_fetched=91).complete is True
        assert fr(raw_fetched=89).complete is False

    def test_no_total_is_unknown(self):
        assert fr(reported_total=None).complete is None

    def test_failure_is_incomplete(self):
        assert fr(success=False).complete is False

    def test_raw_vs_returned(self):
        # 本地丢弃源：返回 30 但分页原始 100 → 对账用 raw，判抓全
        assert fr(fetched=30, raw_fetched=100).complete is True

    def test_per_source_ratio_override(self):
        # 北森系总数虚高：按源校准阈值后 80% 实抓算抓全
        assert fr(raw_fetched=80).complete is False
        assert fr(raw_fetched=80, ratio_override=0.75).complete is True


class TestSuspectSkipsArchive:
    def test_suspect_company_not_archived(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))
        jobs12 = [JobItem(company="A", job_id=f"j{i}", title=f"岗{i}") for i in range(12)]
        store.save_jobs(jobs12)
        # 疑似不完整：只抓到 4 个 + 被标 suspect → 不归档（库存不动）
        store.save_jobs(jobs12[:4], suspect_companies={"A"})
        assert store.get_all_jobs_count() == 12
        # 下次抓全了 → 正常归档恢复
        store.save_jobs(jobs12[:8])
        assert store.get_all_jobs_count() == 8
