"""跨源去重测试（canonical_job_id 启用）。

锁定实证边界（详见 domain/canonical.py 模块头）：
  合并：同雇主校招/社招双 feed 的同平台 job_id 孪生（B站 updream 实例）；
  不合并：同标题不同 job_id（美团"招聘助理"实为两个 requisition）、聚合源公司级线索。
三个消费点各自验证：store 跨天新增抑制 / 渲染同轮折叠 / 推送单条呈现。
"""
import sqlite3

import pytest

import store
from domain.models import JobItem
from domain.canonical import employer_of, canonical_of, dedupe_cross_source


class TestEmployerNormalization:
    @pytest.mark.parametrize("source_id,employer", [
        ("B站", "B站"),
        ("B站(社招)", "B站"),
        ("腾讯（社招）", "腾讯"),          # 全角括号也兼容
        ("字节跳动(社招)", "字节跳动"),
        ("牛客日程", "牛客日程"),          # 聚合源不动
        ("offerstar·某公司", "offerstar·某公司"),
        ("宽创国际", "宽创国际"),
    ])
    def test_employer_of(self, source_id, employer):
        assert employer_of(source_id) == employer

    def test_canonical_of(self):
        assert canonical_of("B站(社招)", "29267") == "B站::29267"
        assert canonical_of("B站", "29267") == "B站::29267"


class TestJobItemCanonical:
    def test_twin_feeds_share_canonical(self):
        """校招/社招双 feed 暴露同一 requisition → canonical 相同（B站 updream 实例）"""
        campus = JobItem(company="B站", job_id="29267", title="UP主运营【2026届】")
        social = JobItem(company="B站(社招)", job_id="29267", title="UP主运营【2026届】",
                         recruit_type="社招")
        assert campus.canonical_job_id == social.canonical_job_id == "B站::29267"

    def test_different_job_id_not_twin(self):
        """同标题不同 job_id = 不同 requisition，canonical 必须不同（美团招聘助理实例）"""
        a = JobItem(company="美团", job_id="2963188562", title="招聘助理")
        b = JobItem(company="美团(社招)", job_id="4630805604", title="招聘助理",
                    recruit_type="社招")
        assert a.canonical_job_id != b.canonical_job_id

    def test_explicit_canonical_kept(self):
        j = JobItem(company="A", job_id="1", title="x", canonical_job_id="X::9")
        assert j.canonical_job_id == "X::9"


class TestDedupeCrossSource:
    def _twins(self):
        campus = JobItem(company="B站", job_id="29267", title="UP主运营【2026届】",
                         location="上海")
        social = JobItem(company="B站(社招)", job_id="29267", title="UP主运营【2026届】",
                         location="上海", recruit_type="社招")
        return campus, social

    def test_collapse_keeps_campus_copy(self):
        """孪生折叠保留校招版（带届别语义，进校招区分块）"""
        campus, social = self._twins()
        kept, _ = dedupe_cross_source([social, campus])
        assert kept == [campus]

    def test_official_beats_aggregator(self):
        """来源可信等级优先于校招/社招之分"""
        official = JobItem(company="X", job_id="1", title="策展助理", recruit_type="社招",
                           source_kind="OFFICIAL_CAREERS", canonical_job_id="X::1")
        agg = JobItem(company="X聚合", job_id="1", title="策展助理",
                      source_kind="AGGREGATOR_DISCOVERY", canonical_job_id="X::1")
        kept, _ = dedupe_cross_source([agg, official])
        assert kept == [official]

    def test_new_keys_extended_to_kept_twin(self):
        """社招版占了新增名额、渲染保留校招版 → 校招版必须继承新增标记（否则推送里凭空消失）"""
        campus, social = self._twins()
        kept, new_keys = dedupe_cross_source([campus, social], {social.dedup_key})
        assert kept == [campus]
        assert campus.dedup_key in new_keys

    def test_non_twins_untouched(self):
        a = JobItem(company="美团", job_id="1", title="招聘助理")
        b = JobItem(company="美团(社招)", job_id="2", title="招聘助理", recruit_type="社招")
        kept, new_keys = dedupe_cross_source([a, b], {a.dedup_key})
        assert kept == [a, b]
        assert new_keys == {a.dedup_key}

    def test_order_stable(self):
        jobs = [JobItem(company=f"C{i}", job_id="1", title="产品经理") for i in range(5)]
        kept, _ = dedupe_cross_source(jobs)
        assert kept == jobs


class TestStoreCrossSourceSuppression:
    @pytest.fixture(autouse=True)
    def temp_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))

    def _campus(self):
        return JobItem(company="B站", job_id="29267", title="UP主运营【2026届】",
                       location="上海")

    def _social(self):
        return JobItem(company="B站(社招)", job_id="29267", title="UP主运营【2026届】",
                       location="上海", recruit_type="社招")

    def test_next_day_twin_suppressed(self):
        """跨天场景：昨天校招 feed 已收录，今天社招 feed 出现孪生 → 不计新增，防隔日重复推送"""
        assert store.save_jobs([self._campus()]) == {"B站::29267"}
        new = store.save_jobs([self._campus(), self._social()])
        assert new == set()   # 孪生被抑制，也没有别的新增

        conn = sqlite3.connect(store.DB_PATH)
        rows = conn.execute("SELECT source_id FROM jobs ORDER BY source_id").fetchall()
        events = {r[0] for r in conn.execute(
            "SELECT event FROM job_events WHERE source_id='B站(社招)'")}
        conn.close()
        assert rows == [("B站",), ("B站(社招)",)]   # 两行都入库（各 feed 独立归档）
        assert events == {"DUPLICATE"}

    def test_same_run_twins_count_once(self):
        """同轮场景：两个 feed 同轮抓到同岗 → 只计一次新增"""
        new = store.save_jobs([self._campus(), self._social()])
        assert len(new) == 1

    def test_unrelated_jobs_still_new(self):
        """非孪生照常计新增（不同 job_id 不受影响）"""
        store.save_jobs([self._campus()])
        new = store.save_jobs([
            self._campus(),
            JobItem(company="B站(社招)", job_id="99999", title="活动运营",
                    location="上海", recruit_type="社招")])
        assert new == {"B站(社招)::99999"}

    def test_legacy_db_backfills_canonical(self):
        """老库（canonical 为空串）迁移回填 = 雇主::job_id，社招后缀正确归一"""
        conn = store._get_conn()
        conn.execute(
            f"INSERT INTO jobs ({store._JOB_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("腾讯(社招)", "j1", "产品", "", "深圳", "u", "", "", "社招", "不限",
             "腾讯(社招)", "OFFICIAL_CAREERS", "", None, None, "2026-01-01", "2026-01-01"))
        conn.commit()
        conn.close()
        conn = store._get_conn()   # 再开触发回填
        canon = conn.execute("SELECT canonical_job_id FROM jobs WHERE job_id='j1'").fetchone()[0]
        conn.close()
        assert canon == "腾讯::j1"


class TestPushRendersOnce:
    def test_twin_appears_once_in_push(self):
        """推送里孪生只出现一行，且计数不重复"""
        import report
        campus = JobItem(company="B站", job_id="29267", title="UP主产品运营【2026届】",
                         location="上海", url="https://x/29267")
        social = JobItem(company="B站(社招)", job_id="29267", title="UP主产品运营【2026届】",
                         location="上海", url="https://x/29267", recruit_type="社招")
        content, n_new = report.generate_push_brief(
            [campus, social], {campus.dedup_key, social.dedup_key})
        assert n_new == 1
        assert content.count("UP主产品运营") == 1

    def test_suppressed_twin_new_key_still_pushes(self):
        """新增名额挂在社招版、渲染保留校招版 → 推送仍要出现这条岗"""
        import report
        campus = JobItem(company="B站", job_id="29267", title="UP主产品运营【2026届】",
                         location="上海", url="https://x/29267")
        social = JobItem(company="B站(社招)", job_id="29267", title="UP主产品运营【2026届】",
                         location="上海", url="https://x/29267", recruit_type="社招")
        content, n_new = report.generate_push_brief(
            [campus, social], {social.dedup_key})
        assert n_new == 1
        assert "UP主产品运营" in content
