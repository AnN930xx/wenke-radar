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

    def test_archive_needs_two_consecutive_misses(self):
        # 状态机：缺失第一次只挂起(留在主表)，连续第二次才归档
        self._seed("A", 12)
        store.save_jobs(mk("A", 8))            # j8~j11 首次缺失 → PENDING，主表仍 12
        assert store.get_all_jobs_count() == 12
        store.save_jobs(mk("A", 8))            # 连续第二次缺失 → CLOSED，主表 8
        assert store.get_all_jobs_count() == 8

    def test_reappear_clears_pending(self):
        # 挂起的岗位下次抓到即恢复，不会被误归档（这正是替代 50% 阈值的意义）
        self._seed("A", 12)
        store.save_jobs(mk("A", 8))            # j8~j11 挂起
        store.save_jobs(mk("A", 12))          # 全部又抓到 → 清除挂起
        assert store.get_all_jobs_count() == 12
        store.save_jobs(mk("A", 8))           # 再次缺失 → 只是重新挂起(streak 归零后=1)，未归档
        assert store.get_all_jobs_count() == 12

    def test_large_dropout_not_stuck(self):
        # 真实大规模缩招：旧 50% 阈值会永久卡住；状态机两次确认后正常归档
        self._seed("A", 12)
        store.save_jobs(mk("A", 2))           # 掉到 2（>50% 缺失）→ 10 个挂起
        assert store.get_all_jobs_count() == 12
        store.save_jobs(mk("A", 2))           # 连续第二次 → 10 个归档
        assert store.get_all_jobs_count() == 2

    def test_zero_fetch_no_state_change(self):
        self._seed("A", 12)
        store.save_jobs([])                    # 全体 0 岗（源失败）→ 不推进状态
        assert store.get_all_jobs_count() == 12

    def test_no_archive_flag(self, monkeypatch):
        monkeypatch.setitem(config.COMPANY_CONFIG, "抖动源", {"no_archive": True})
        self._seed("抖动源", 6)
        store.save_jobs(mk("抖动源", 2))       # 反爬只返回子集 → 永不归档
        store.save_jobs(mk("抖动源", 2))       # 连续缺失也不归档
        assert store.get_all_jobs_count() == 6

    def test_reopened_job_after_archive_is_new(self):
        self._seed("A", 12)
        store.save_jobs(mk("A", 8))                       # 挂起
        store.save_jobs(mk("A", 8))                       # j8~j11 归档
        new = store.save_jobs(mk("A", 12))                # 归档的 4 个重新出现
        assert new == {f"A::j{i}" for i in (8, 9, 10, 11)}
