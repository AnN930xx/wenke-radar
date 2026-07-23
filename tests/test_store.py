"""存储层测试：新增对比、自动归档、数据可信度守卫（bootstrap / 骤降 / no_archive）。
全部跑在临时库上，不碰真实 data/jobs.db。
"""
import pytest

import store
import config
from domain.models import JobItem


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test_jobs.db"))


def mk(company, n, prefix="j"):
    return [JobItem(company=company, job_id=f"{prefix}{i}", title=f"岗位{i}",
                    location="上海", url=f"https://x.com/{i}") for i in range(n)]


class TestNewJobDetection:
    def test_first_seen_marks_new(self):
        # 已知公司（先小批量入库使其"已知"）的后续新岗计新增
        store.save_jobs(mk("A", 2))
        new = store.save_jobs(mk("A", 2) + mk("A", 1, prefix="x"))
        assert new == {"A::x0"}

    def test_rerun_is_idempotent(self):
        store.save_jobs(mk("A", 3))
        assert store.save_jobs(mk("A", 3)) == set()


class TestBootstrapGuard:
    def test_large_new_source_silenced(self):
        new = store.save_jobs(mk("新大厂", 12))
        assert new == set()
        assert store.get_all_jobs_count() == 12   # 入库了，只是不计新增

    def test_small_new_company_reported(self):
        # 聚合源新公司只有 1-2 条公告，属真实新增
        new = store.save_jobs(mk("offerstar·某司", 2))
        assert len(new) == 2

    def test_known_company_not_affected(self):
        store.save_jobs(mk("A", 2))
        new = store.save_jobs(mk("A", 2) + mk("A", 6, prefix="n"))
        assert len(new) == 6   # 已知公司一次上 6 个新岗照常全报


class TestArchiveAndGuards:
    def _seed(self, company, n):
        """建一个已知公司的库存（第一次 save 会走 bootstrap，属正常路径）"""
        store.save_jobs(mk(company, n))

    def test_normal_archive(self):
        self._seed("A", 12)
        store.save_jobs(mk("A", 8))            # 归档 4/12 = 33% < 50%
        assert store.get_all_jobs_count() == 8

    def test_plunge_skips_archive(self):
        self._seed("A", 12)
        new = store.save_jobs(mk("A", 3))      # 只匹配到 3/12 → 要归档 75% → 拦截
        assert store.get_all_jobs_count() == 12
        assert new == set()

    def test_small_stock_exempt_from_guard(self):
        # 库存 < ARCHIVE_GUARD_MIN_EXISTING 的小源不受骤降守卫限制（2→1 属正常）
        self._seed("小司", 2)
        store.save_jobs(mk("小司", 1))
        assert store.get_all_jobs_count() == 1

    def test_zero_fetch_no_archive(self):
        self._seed("A", 12)
        store.save_jobs([])                    # 全体 0 岗（源失败）→ 不归档
        assert store.get_all_jobs_count() == 12

    def test_no_archive_flag(self, monkeypatch):
        monkeypatch.setitem(config.COMPANY_CONFIG, "抖动源", {"no_archive": True})
        self._seed("抖动源", 6)
        store.save_jobs(mk("抖动源", 2))       # 反爬只返回子集 → 不归档
        assert store.get_all_jobs_count() == 6

    def test_reopened_job_after_archive_is_new(self):
        self._seed("A", 12)
        store.save_jobs(mk("A", 8))                       # j8~j11 被归档
        new = store.save_jobs(mk("A", 12))                # 归档的 4 个重新出现
        assert new == {f"A::j{i}" for i in (8, 9, 10, 11)}
