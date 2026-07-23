"""来源身份 source_id / 可信等级 source_kind 测试（二轮审查 P0）。

锁定：① source_id 缺省取 company、dedup_key 按 source_id；② 来源分级正确；
③ 官方源与聚合发现源的可信度区分；④ 老库（无 source_id 列）平滑迁移不丢数据、行为不变。
"""
import sqlite3

import pytest

import config
import store
from domain.models import JobItem


class TestSourceIdentityDefaults:
    def test_source_id_defaults_to_company(self):
        j = JobItem(company="腾讯", job_id="1", title="产品经理")
        assert j.source_id == "腾讯"
        assert j.dedup_key == "腾讯::1"

    def test_explicit_source_id_kept(self):
        j = JobItem(company="腾讯", job_id="1", title="x", source_id="tencent_campus")
        assert j.dedup_key == "tencent_campus::1"

    def test_canonical_auto_derived(self):
        """canonical_job_id 自动派生为 雇主::job_id（跨源去重身份，详见 test_canonical.py）"""
        assert JobItem(company="A", job_id="1", title="x").canonical_job_id == "A::1"


class TestSourceKind:
    @pytest.mark.parametrize("name,kind", [
        ("腾讯", "OFFICIAL_CAREERS"),
        ("腾讯(社招)", "OFFICIAL_CAREERS"),
        ("字节跳动", "OFFICIAL_ATS"),        # 飞书 ATS
        ("泡泡玛特(社招)", "OFFICIAL_ATS"),   # 北森
        ("农夫山泉", "OFFICIAL_ATS"),        # Moka
        ("牛客日程", "AGGREGATOR_DISCOVERY"),
        ("宽创国际", "AGGREGATOR_DISCOVERY"),  # 猎聘
        ("凯谛思", "AGGREGATOR_DISCOVERY"),
        ("offerstar·某公司", "AGGREGATOR_DISCOVERY"),  # 前缀匹配
    ])
    def test_classification(self, name, kind):
        assert config.source_kind(name) == kind

    def test_authoritative(self):
        assert config.is_authoritative("腾讯")
        assert config.is_authoritative("字节跳动")
        assert not config.is_authoritative("宽创国际")
        assert not config.is_authoritative("offerstar·某司")

    def test_jobitem_gets_kind(self):
        assert JobItem(company="牛客日程", job_id="1", title="x").source_kind == "AGGREGATOR_DISCOVERY"
        assert JobItem(company="腾讯", job_id="1", title="x").source_kind == "OFFICIAL_CAREERS"


class TestStoreKeysBySource:
    @pytest.fixture(autouse=True)
    def temp_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))

    def test_source_id_written_to_db(self):
        store.save_jobs([JobItem(company="腾讯", job_id="1", title="产品")])
        conn = sqlite3.connect(store.DB_PATH)
        row = conn.execute("SELECT source_id, source_kind FROM jobs").fetchone()
        conn.close()
        assert row == ("腾讯", "OFFICIAL_CAREERS")

    def test_health_records_kind(self):
        from domain.results import FetchResult
        store.save_source_health([FetchResult(
            source="宽创国际", fetched=2, raw_fetched=2, reported_total=None,
            success=True, duration_s=1.0)])
        conn = sqlite3.connect(store.DB_PATH)
        kind = conn.execute("SELECT source_kind FROM source_health").fetchone()[0]
        conn.close()
        assert kind == "AGGREGATOR_DISCOVERY"


class TestLegacyMigration:
    def test_old_schema_migrates(self, tmp_path, monkeypatch):
        """模拟旧库（jobs 表无 source_id 列），确认迁移后回填 source_id/source_kind、数据不丢。"""
        db = str(tmp_path / "old.db")
        conn = sqlite3.connect(db)
        conn.execute("""CREATE TABLE jobs (company TEXT, job_id TEXT, title TEXT,
            category TEXT, location TEXT, url TEXT, publish_time TEXT, tags TEXT,
            recruit_type TEXT, recruit_year TEXT, first_seen TEXT, last_seen TEXT,
            PRIMARY KEY (company, job_id))""")
        conn.execute("INSERT INTO jobs VALUES ('字节跳动','j1','产品','产品','上海','u','','',"
                     "'校招','2026','2026-01-01','2026-01-01')")
        conn.commit(); conn.close()

        monkeypatch.setattr(store, "DB_PATH", db)
        conn = store._get_conn()   # 触发迁移
        row = conn.execute("SELECT company, source_id, source_kind FROM jobs").fetchone()
        conn.close()
        # 旧行仍在，source_id 回填=company，source_kind 按分级推断（字节=飞书ATS）
        assert row == ("字节跳动", "字节跳动", "OFFICIAL_ATS")

    def test_migration_preserves_new_detection(self, tmp_path, monkeypatch):
        """迁移后接着 save_jobs：老岗不重报新增，真新岗照常报——增量语义不被迁移破坏。"""
        db = str(tmp_path / "old2.db")
        conn = sqlite3.connect(db)
        conn.execute("""CREATE TABLE jobs (company TEXT, job_id TEXT, title TEXT,
            category TEXT, location TEXT, url TEXT, publish_time TEXT, tags TEXT,
            recruit_type TEXT, recruit_year TEXT, first_seen TEXT, last_seen TEXT,
            PRIMARY KEY (company, job_id))""")
        conn.execute("INSERT INTO jobs VALUES ('腾讯','old','老岗','','上海','u','','',"
                     "'社招','不限','2026-01-01','2026-01-01')")
        conn.commit(); conn.close()

        monkeypatch.setattr(store, "DB_PATH", db)
        new = store.save_jobs([
            JobItem(company="腾讯", job_id="old", title="老岗", location="上海", recruit_type="社招"),
            JobItem(company="腾讯", job_id="fresh", title="新岗", location="上海", recruit_type="社招"),
        ])
        assert new == {"腾讯::fresh"}   # 老岗不重报，只有真新岗
