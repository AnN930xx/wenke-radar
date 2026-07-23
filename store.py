"""历史数据存储与新增对比（SQLite）

以 **来源身份 source_id** 为主键做新增对比与归档（二轮审查采纳；当前每个源的
source_id 恒等于其 company 名，故行为与旧版逐字节一致，但语义正名为"来源"）。

表结构：
  jobs          当前在招岗位（主表；下线岗自动归档，不留垃圾）
    - source_id / source_kind  来源身份与可信等级（OFFICIAL_* / AGGREGATOR_DISCOVERY）
    - recruit_type / recruit_year / category  分类列
    - canonical_job_id  跨源去重预留（暂空）
  jobs_archive  已下线岗位归档（结构同 jobs + archived_at）
  job_events    岗位生命周期事件流（CREATED/BOOTSTRAP/REOPENED/UPDATED/CLOSED）
  source_health 每轮每源的抓取健康度（成功/完整性/耗时/可信等级）
  v_job_summary 汇总视图：公司 × 招聘类型 × 届别
"""
import sqlite3
import os
from datetime import datetime, date
from typing import List, Set
from domain.models import JobItem
from domain.enrich import enrich        # 落库前抽取结构化字段（经验年限），供指纹与展示
from filters import parse_recruit_year  # 届别解析属"业务规则"，统一放 filters 层
import config

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jobs.db")

# 落库列（含来源身份 + 内容指纹）。顺序与 INSERT 值元组严格对应。
_JOB_COLUMNS = ("company,job_id,title,category,location,url,publish_time,tags,"
                "recruit_type,recruit_year,source_id,source_kind,canonical_job_id,"
                "content_fingerprint,experience_min_years,first_seen,last_seen")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            company TEXT, job_id TEXT, title TEXT, category TEXT, location TEXT,
            url TEXT, publish_time TEXT, tags TEXT,
            recruit_type TEXT DEFAULT '校招', recruit_year TEXT DEFAULT '不限',
            source_id TEXT, source_kind TEXT, canonical_job_id TEXT DEFAULT '',
            content_fingerprint TEXT, experience_min_years INTEGER,
            first_seen TEXT, last_seen TEXT,
            PRIMARY KEY (company, job_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs_archive (
            company TEXT, job_id TEXT, title TEXT, category TEXT, location TEXT,
            url TEXT, publish_time TEXT, tags TEXT,
            recruit_type TEXT DEFAULT '校招', recruit_year TEXT DEFAULT '不限',
            source_id TEXT, source_kind TEXT, canonical_job_id TEXT DEFAULT '',
            content_fingerprint TEXT, experience_min_years INTEGER,
            first_seen TEXT, last_seen TEXT, archived_at TEXT,
            PRIMARY KEY (company, job_id)
        )
    """)
    _migrate_columns(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_events (
            event_at TEXT, source_id TEXT, company TEXT, job_id TEXT,
            event TEXT,   -- CREATED / BOOTSTRAP / REOPENED / UPDATED / CLOSED
            title TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_health (
            run_at TEXT, source TEXT, source_kind TEXT, success INTEGER,
            fetched INTEGER, raw_fetched INTEGER, reported_total INTEGER,
            complete INTEGER, duration_s REAL, error TEXT
        )
    """)
    conn.execute("DROP VIEW IF EXISTS v_job_summary")
    conn.execute("""
        CREATE VIEW v_job_summary AS
        SELECT company, recruit_type, recruit_year, COUNT(*) AS jobs_count
        FROM jobs GROUP BY company, recruit_type, recruit_year
        ORDER BY recruit_type, company, recruit_year
    """)
    conn.commit()
    return conn


def _migrate_columns(conn):
    """老库平滑升级：补齐来源身份等新列并回填（幂等，只在缺列时跑一次回填）。"""
    for table in ("jobs", "jobs_archive"):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        need_source = "source_id" not in cols
        for col, ddl in (("recruit_type", "TEXT DEFAULT '校招'"),
                         ("recruit_year", "TEXT DEFAULT '不限'"),
                         ("source_id", "TEXT"), ("source_kind", "TEXT"),
                         ("canonical_job_id", "TEXT DEFAULT ''"),
                         ("content_fingerprint", "TEXT"),
                         ("experience_min_years", "INTEGER")):
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        if need_source:
            # 回填：source_id 取旧 company（二者恒等），source_kind 按来源分级推断
            conn.execute(f"UPDATE {table} SET source_id=company "
                         f"WHERE source_id IS NULL OR source_id=''")
            for (sid,) in conn.execute(
                    f"SELECT DISTINCT source_id FROM {table}").fetchall():
                conn.execute(f"UPDATE {table} SET source_kind=? WHERE source_id=?",
                             (config.source_kind(sid), sid))
    # job_events / source_health 补列（旧库缺则加）
    ev_cols = {r[1] for r in conn.execute("PRAGMA table_info(job_events)").fetchall()}
    if ev_cols and "source_id" not in ev_cols:
        conn.execute("ALTER TABLE job_events ADD COLUMN source_id TEXT")
        conn.execute("UPDATE job_events SET source_id=company")
    sh_cols = {r[1] for r in conn.execute("PRAGMA table_info(source_health)").fetchall()}
    if sh_cols and "source_kind" not in sh_cols:
        conn.execute("ALTER TABLE source_health ADD COLUMN source_kind TEXT")


def _job_year(job: JobItem) -> str:
    """社招不分届别；校招从标题+标签解析"""
    if job.recruit_type == "社招":
        return "不限"
    return parse_recruit_year(f"{job.title} {job.tags}")


def save_jobs(jobs: List[JobItem], suspect_sources: Set[str] = None) -> Set[str]:
    """保存岗位，返回本次"新增"的 dedup_key 集合。所有新增对比/归档/守卫均按 source_id 分组。

    数据可信度守卫（阈值见 config"数据可信度守卫"段）：
      - suspect_sources：main 按 FetchResult 完整性对账判定"疑似没抓全"的来源，本次跳过归档；
      - 来源级 bootstrap：库里（含归档）从未见过的来源且首抓 >= BOOTSTRAP_MIN_JOBS 岗 → 静默入库不计新增；
      - 归档骤降守卫：要归档的岗位占该来源原库存比例过高 → 疑似部分抓取，跳过归档并告警；
      - 本次抓到 0 岗不归档；no_archive 源（猎聘系）永不归档。
    """
    suspect_sources = suspect_sources or set()
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_keys = set()
    current_ids = {}       # source_id -> set(job_id)
    inserted_count = {}    # source_id -> 本次新插入行数（骤降守卫还原"原库存"用）

    # 来源级 bootstrap：主表+归档都没见过的 source_id = 新接入的来源
    known = {r[0] for r in conn.execute(
        "SELECT source_id FROM jobs UNION SELECT source_id FROM jobs_archive")}
    batch_by_source = {}
    for job in jobs:
        batch_by_source.setdefault(job.source_id, []).append(job)
    min_bootstrap = getattr(config, "BOOTSTRAP_MIN_JOBS", 5)
    bootstrap_sources = {s for s, batch in batch_by_source.items()
                         if s not in known and len(batch) >= min_bootstrap}
    for s in sorted(bootstrap_sources):
        print(f"  🧱 [{s}] 新接入来源首抓 {len(batch_by_source[s])} 岗："
              f"bootstrap 静默入库，不计入今日新增")

    def log_event(source_id, company, job_id, event, title):
        conn.execute("INSERT INTO job_events (event_at, source_id, company, job_id, event, title)"
                     " VALUES (?,?,?,?,?,?)", (now, source_id, company, job_id, event, title))

    for job in jobs:
        enrich(job)                      # 落库前抽取经验年限（供指纹与展示；幂等）
        fp = job.content_fingerprint     # 标题/地点/类别/JD 任一变化即变
        current_ids.setdefault(job.source_id, set()).add(job.job_id)
        existing = conn.execute(
            "SELECT first_seen, content_fingerprint FROM jobs WHERE source_id=? AND job_id=?",
            (job.source_id, job.job_id)).fetchone()
        if existing is None:
            conn.execute(
                f"INSERT INTO jobs ({_JOB_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (job.company, job.job_id, job.title, job.category, job.location,
                 job.url, job.publish_time, job.tags, job.recruit_type, _job_year(job),
                 job.source_id, job.source_kind, job.canonical_job_id,
                 fp, job.experience_min_years, now, now))
            inserted_count[job.source_id] = inserted_count.get(job.source_id, 0) + 1
            if job.source_id in bootstrap_sources:
                log_event(job.source_id, job.company, job.job_id, "BOOTSTRAP", job.title)
            else:
                new_keys.add(job.dedup_key)
                was_archived = conn.execute(
                    "SELECT 1 FROM jobs_archive WHERE source_id=? AND job_id=?",
                    (job.source_id, job.job_id)).fetchone()
                log_event(job.source_id, job.company, job.job_id,
                          "REOPENED" if was_archived else "CREATED", job.title)
        else:
            # 内容指纹变化=真 UPDATED（含 JD/要求变化）。老库迁移后指纹为 NULL：
            # 首见时静默采纳、不报 UPDATED，只有后续真变化才记事件（避免迁移 UPDATED 洪水）。
            stored_fp = existing[1]
            if stored_fp is not None and stored_fp != fp:
                log_event(job.source_id, job.company, job.job_id, "UPDATED", job.title)
            conn.execute(
                "UPDATE jobs SET title=?,category=?,location=?,url=?,publish_time=?,"
                "tags=?,recruit_type=?,recruit_year=?,source_kind=?,"
                "content_fingerprint=?,experience_min_years=?,last_seen=? "
                "WHERE source_id=? AND job_id=?",
                (job.title, job.category, job.location, job.url, job.publish_time,
                 job.tags, job.recruit_type, _job_year(job), job.source_kind,
                 fp, job.experience_min_years, now, job.source_id, job.job_id))

    # 归档已下线岗位（仅处理本次抓到岗位的来源）
    archived = 0
    guard_ratio = getattr(config, "ARCHIVE_GUARD_RATIO", 0.5)
    guard_min = getattr(config, "ARCHIVE_GUARD_MIN_EXISTING", 10)
    for source_id, ids in current_ids.items():
        if not ids:
            continue
        # no_archive 源（如猎聘，返回数不稳定）不自动归档，避免误判下线→次日又当新增
        if config.COMPANY_CONFIG.get(source_id, {}).get("no_archive"):
            continue
        # 完整性对账不合格的来源：本次没抓全，看不到 ≠ 下线了
        if source_id in suspect_sources:
            print(f"  ⚠️ [{source_id}] 本次抓取疑似不完整，跳过归档")
            continue
        placeholders = ",".join("?" * len(ids))
        stale = conn.execute(
            f"SELECT {_JOB_COLUMNS} FROM jobs "
            f"WHERE source_id=? AND job_id NOT IN ({placeholders})",
            (source_id, *ids)).fetchall()
        if not stale:
            continue
        matched = len(ids) - inserted_count.get(source_id, 0)   # 本次匹配上的旧岗
        prev_stock = len(stale) + matched
        if prev_stock >= guard_min and len(stale) > prev_stock * guard_ratio:
            print(f"  ⚠️ [{source_id}] 疑似部分抓取：原库存 {prev_stock} 岗，本次仅匹配到 "
                  f"{matched} 岗（要归档 {len(stale)} 个 > {guard_ratio:.0%}），已跳过归档。"
                  f"若为真实缩招请人工确认（连续出现请排查该源分页/接口）")
            continue
        for row in stale:
            conn.execute(
                f"INSERT OR REPLACE INTO jobs_archive ({_JOB_COLUMNS},archived_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*row, now))
            log_event(row[10], row[0], row[1], "CLOSED", row[2])  # source_id,company,job_id,title
        conn.execute(
            f"DELETE FROM jobs WHERE source_id=? AND job_id NOT IN ({placeholders})",
            (source_id, *ids))
        archived += len(stale)
    if archived:
        print(f"  🗄️ 已归档 {archived} 个下线岗位（主表只留当前在招）")
    conn.commit()
    conn.close()
    return new_keys


def save_source_health(results) -> None:
    """把本轮各源的 FetchResult 写入健康度表（维护者视角运行记录，含来源可信等级）。"""
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in results:
        complete = r.complete
        conn.execute(
            "INSERT INTO source_health (run_at, source, source_kind, success, fetched,"
            " raw_fetched, reported_total, complete, duration_s, error)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (now, r.source, config.source_kind(r.source), int(r.success), r.fetched,
             r.raw_fetched, r.reported_total, None if complete is None else int(complete),
             r.duration_s, r.error))
    conn.commit()
    conn.close()


def get_today_new_jobs() -> List[dict]:
    """获取今天首次发现的岗位"""
    conn = _get_conn()
    today = date.today().isoformat()
    rows = conn.execute(
        "SELECT company,job_id,title,category,location,url,publish_time,tags,first_seen "
        "FROM jobs WHERE first_seen LIKE ? ORDER BY company, first_seen DESC",
        (f"{today}%",)).fetchall()
    conn.close()
    return [dict(zip(
        ["company", "job_id", "title", "category", "location", "url",
         "publish_time", "tags", "first_seen"], row)) for row in rows]


def get_all_jobs_count():
    conn = _get_conn()
    n = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    return n


def clear_all():
    """清空所有历史数据（全量初始化用）"""
    conn = _get_conn()
    conn.execute("DELETE FROM jobs")
    conn.execute("DELETE FROM jobs_archive")
    conn.commit()
    conn.close()
