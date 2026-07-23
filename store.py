"""历史数据存储与新增对比（SQLite）

以 **来源身份 source_id** 为主键做新增对比与归档（二轮审查采纳；当前每个源的
source_id 恒等于其 company 名，故行为与旧版逐字节一致，但语义正名为"来源"）。

表结构：
  jobs          当前在招岗位（主表；下线岗自动归档，不留垃圾）
    - source_id / source_kind  来源身份与可信等级（OFFICIAL_* / AGGREGATOR_DISCOVERY）
    - recruit_type / recruit_year / category  分类列
    - canonical_job_id  跨源去重身份（雇主::平台job_id，见 domain/canonical.py）：
      新来源出现"其它来源已收录的同岗孪生"时照常入库、但不计新增（防隔日重复推送），
      事件流记 DUPLICATE
  jobs_archive  已下线岗位归档（结构同 jobs + archived_at）
  job_events    岗位生命周期事件流（CREATED/BOOTSTRAP/REOPENED/UPDATED/CLOSED/DUPLICATE）
  source_health 每轮每源的抓取健康度（成功/完整性/耗时/可信等级）
  v_job_summary 汇总视图：公司 × 招聘类型 × 届别
"""
import sqlite3
import os
from datetime import datetime, date
from typing import List, Set
from domain.models import JobItem
from domain.enrich import enrich              # 落库前抽取结构化字段（经验年限），供指纹与展示
from domain.recruitment import parse_recruit_year  # 届别解析（纯领域逻辑，store 不再依赖 filters）
from domain.canonical import canonical_of     # 跨源去重身份（老库回填迁移用）
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
            missing_streak INTEGER DEFAULT 0,
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_canonical ON jobs(canonical_job_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_events (
            event_at TEXT, source_id TEXT, company TEXT, job_id TEXT,
            event TEXT,   -- CREATED / BOOTSTRAP / REOPENED / UPDATED / CLOSED / DUPLICATE
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
                         ("experience_min_years", "INTEGER"),
                         ("missing_streak", "INTEGER DEFAULT 0")):
            if col not in cols and not (table == "jobs_archive" and col == "missing_streak"):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        if need_source:
            # 回填：source_id 取旧 company（二者恒等），source_kind 按来源分级推断
            conn.execute(f"UPDATE {table} SET source_id=company "
                         f"WHERE source_id IS NULL OR source_id=''")
            for (sid,) in conn.execute(
                    f"SELECT DISTINCT source_id FROM {table}").fetchall():
                conn.execute(f"UPDATE {table} SET source_kind=? WHERE source_id=?",
                             (config.source_kind(sid), sid))
        # canonical_job_id 回填（老库为空串；幂等，回填过一次后命中 0 行）
        for sid, jid in conn.execute(
                f"SELECT source_id, job_id FROM {table} "
                f"WHERE canonical_job_id IS NULL OR canonical_job_id=''").fetchall():
            conn.execute(
                f"UPDATE {table} SET canonical_job_id=? WHERE source_id=? AND job_id=?",
                (canonical_of(sid, jid), sid, jid))
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
      - suspect_sources：main 按 FetchResult 完整性对账判定"疑似没抓全"的来源，本次跳过下线判定；
      - 来源级 bootstrap：库里（含归档）从未见过的来源且首抓 >= BOOTSTRAP_MIN_JOBS 岗 → 静默入库不计新增；
      - 归档状态机：缺失岗位先 PENDING_CLOSED，连续缺失 CLOSE_AFTER_MISSES 次才 CLOSED（替代旧的骤降阈值）；
      - 本次抓到 0 岗不推进状态；no_archive 源（猎聘系）永不归档；
      - 跨源去重：新行的 canonical_job_id 已被其它来源收录（校招/社招双 feed 孪生）→
        入库但不计新增、事件记 DUPLICATE（同轮的另一份由渲染层 dedupe_cross_source 折叠）。
    """
    suspect_sources = suspect_sources or set()
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_keys = set()
    current_ids = {}       # source_id -> set(job_id)
    dup_by_source = {}     # source_id -> 跨源孪生抑制数（打日志用）

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
            if job.source_id in bootstrap_sources:
                log_event(job.source_id, job.company, job.job_id, "BOOTSTRAP", job.title)
            else:
                # 跨源去重：其它来源已收录同一 canonical（同雇主同平台 job_id 的孪生，
                # 如校招/社招双 feed 同岗）→ 照常入库但不计新增，防重复推送
                twin = conn.execute(
                    "SELECT 1 FROM jobs WHERE canonical_job_id=? AND source_id<>? LIMIT 1",
                    (job.canonical_job_id, job.source_id)).fetchone()
                if twin:
                    log_event(job.source_id, job.company, job.job_id, "DUPLICATE", job.title)
                    dup_by_source[job.source_id] = dup_by_source.get(job.source_id, 0) + 1
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
                "content_fingerprint=?,experience_min_years=?,missing_streak=0,last_seen=? "
                "WHERE source_id=? AND job_id=?",   # 抓到=确认存活，缺失计数清零
                (job.title, job.category, job.location, job.url, job.publish_time,
                 job.tags, job.recruit_type, _job_year(job), job.source_kind,
                 fp, job.experience_min_years, now, job.source_id, job.job_id))

    for s in sorted(dup_by_source):
        print(f"  🔗 [{s}] {dup_by_source[s]} 个岗位是其它来源已收录岗位的孪生"
              f"（跨源去重：入库不计新增）")

    # 归档状态机（仅处理本次抓到岗位的来源）：完整运行里缺失的岗位先挂起(PENDING_CLOSED)，
    # 连续缺失达 CLOSE_AFTER_MISSES 次才归档(CLOSED)。抓到的岗位上面已把 missing_streak 清零。
    n_cols = len(_JOB_COLUMNS.split(","))   # 归档列数（stale 行尾部多一个 missing_streak）
    close_after = getattr(config, "CLOSE_AFTER_MISSES", 2)
    archived = 0
    for source_id, ids in current_ids.items():
        if not ids:
            continue   # 本次没抓到该源任何岗 → 不推进状态（源可能整体失败/官网暂关）
        # no_archive 源（如猎聘）不 authoritative，永不自动归档
        if config.COMPANY_CONFIG.get(source_id, {}).get("no_archive"):
            continue
        # 不完整运行：缺失不可信，整源跳过下线判定（抓到的岗位仍已重置计数=确认存活）
        if source_id in suspect_sources:
            print(f"  ⚠️ [{source_id}] 本次抓取疑似不完整，跳过下线判定（缺失不可信）")
            continue
        placeholders = ",".join("?" * len(ids))
        stale = conn.execute(
            f"SELECT {_JOB_COLUMNS}, missing_streak FROM jobs "
            f"WHERE source_id=? AND job_id NOT IN ({placeholders})",
            (source_id, *ids)).fetchall()
        pending = 0
        for row in stale:
            cols = row[:n_cols]                 # 去掉尾部 missing_streak
            streak = (row[n_cols] or 0) + 1
            sid, comp, jid, title = cols[10], cols[0], cols[1], cols[2]
            if streak >= close_after:           # 连续缺失达标 → 确认下线，归档
                conn.execute(
                    f"INSERT OR REPLACE INTO jobs_archive ({_JOB_COLUMNS},archived_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*cols, now))
                conn.execute("DELETE FROM jobs WHERE source_id=? AND job_id=?", (sid, jid))
                log_event(sid, comp, jid, "CLOSED", title)
                archived += 1
            else:                               # 首次缺失 → 挂起待确认，留在主表
                conn.execute("UPDATE jobs SET missing_streak=? WHERE source_id=? AND job_id=?",
                             (streak, sid, jid))
                log_event(sid, comp, jid, "PENDING_CLOSED", title)
                pending += 1
        if pending:
            print(f"  ⏳ [{source_id}] {pending} 个岗位本次缺失，挂起待确认"
                  f"（连续缺失 {close_after} 次才归档）")
    if archived:
        print(f"  🗄️ 已归档 {archived} 个确认下线的岗位")
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
