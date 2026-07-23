"""历史数据存储与新增对比（SQLite）

表结构（按 公司 / 招聘类型 / 届别 / 方向类别 分类清晰）：
  jobs          当前在招岗位（主表；已下线的岗位会自动归档，不留垃圾）
    - recruit_type  校招 / 社招
    - recruit_year  届别：如 "2026"、"2026/2027"；未写明届别或社招为 "不限"
    - category      方向类别（产品/运营/电商/策展/增长营销/市场...）
  jobs_archive  已下线岗位归档（结构同 jobs + archived_at；保留历史不污染主表）
  v_job_summary 汇总视图：公司 × 招聘类型 × 届别 的岗位数一览
    用法: sqlite3 data/jobs.db "SELECT * FROM v_job_summary"
"""
import sqlite3
import os
from datetime import datetime, date
from typing import List, Set
from domain.models import JobItem
from filters import parse_recruit_year  # 届别解析属"业务规则"，统一放 filters 层
import config

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jobs.db")

_JOB_COLUMNS = ("company,job_id,title,category,location,url,publish_time,tags,"
                "recruit_type,recruit_year,first_seen,last_seen")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            company TEXT,
            job_id TEXT,
            title TEXT,
            category TEXT,
            location TEXT,
            url TEXT,
            publish_time TEXT,
            tags TEXT,
            recruit_type TEXT DEFAULT '校招',
            recruit_year TEXT DEFAULT '不限',
            first_seen TEXT,
            last_seen TEXT,
            PRIMARY KEY (company, job_id)
        )
    """)
    # 老库升级：补 recruit_type / recruit_year 列（幂等，已有则跳过）
    cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if "recruit_type" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN recruit_type TEXT DEFAULT '校招'")
    if "recruit_year" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN recruit_year TEXT DEFAULT '不限'")
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS jobs_archive (
            company TEXT,
            job_id TEXT,
            title TEXT,
            category TEXT,
            location TEXT,
            url TEXT,
            publish_time TEXT,
            tags TEXT,
            recruit_type TEXT DEFAULT '校招',
            recruit_year TEXT DEFAULT '不限',
            first_seen TEXT,
            last_seen TEXT,
            archived_at TEXT,
            PRIMARY KEY (company, job_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type_year "
                 "ON jobs(recruit_type, recruit_year)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_events (
            event_at TEXT,           -- 事件时间
            company TEXT,
            job_id TEXT,
            event TEXT,              -- CREATED首发 / BOOTSTRAP新源静默入库 / REOPENED重新开放
                                     -- / UPDATED标题或地点变更 / CLOSED下线归档
            title TEXT               -- 事件发生时的岗位名（快照，便于直接读事件流）
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_health (
            run_at TEXT,             -- 运行时间
            source TEXT,             -- 源名
            success INTEGER,         -- 抓取过程是否无异常
            fetched INTEGER,         -- 返回岗位数（本地过滤后）
            raw_fetched INTEGER,     -- 分页原始条数
            reported_total INTEGER,  -- 服务端报告总数（NULL=源不提供）
            complete INTEGER,        -- 1抓全/0疑似不完整/NULL无法判断
            duration_s REAL,
            error TEXT
        )
    """)
    conn.execute("DROP VIEW IF EXISTS v_job_summary")
    conn.execute("""
        CREATE VIEW v_job_summary AS
        SELECT company, recruit_type, recruit_year,
               COUNT(*) AS jobs_count
        FROM jobs
        GROUP BY company, recruit_type, recruit_year
        ORDER BY recruit_type, company, recruit_year
    """)
    return conn


def _job_year(job: JobItem) -> str:
    """社招不分届别；校招从标题+标签解析"""
    if job.recruit_type == "社招":
        return "不限"
    return parse_recruit_year(f"{job.title} {job.tags}")


def save_jobs(jobs: List[JobItem], suspect_companies: Set[str] = None) -> Set[str]:
    """保存岗位，返回本次"新增"的 dedup_key 集合。

    数据可信度守卫（阈值见 config"数据可信度守卫"段）：
      - suspect_companies：main 按 FetchResult 完整性对账判定"疑似没抓全"的源，
        本次跳过归档（岗位照常入库/报新增，但不敢断言别的岗下线了）；
      - 来源级 bootstrap：库里（含归档）从未见过的公司且首抓 >= BOOTSTRAP_MIN_JOBS 岗
        → 静默入库不计新增（防新源存量刷屏日报）；
      - 归档骤降守卫：要归档的岗位占该公司原库存比例过高 → 疑似部分抓取成功，跳过归档并告警；
      - 公司本次抓到 0 岗（官网暂关/接口抖动）不归档；no_archive 源（猎聘系）永不归档。
    正常路径：已下线岗位自动挪入 jobs_archive，主表始终只留当前在招。
    """
    suspect_companies = suspect_companies or set()
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_keys = set()
    current_ids = {}       # company -> set(job_id)
    inserted_count = {}    # company -> 本次新插入行数（骤降守卫要用它还原"原库存"）

    # 来源级 bootstrap 判定：主表+归档表都没见过的公司 = 新接入的源
    known_companies = {r[0] for r in conn.execute(
        "SELECT company FROM jobs UNION SELECT company FROM jobs_archive")}
    batch_by_company = {}
    for job in jobs:
        batch_by_company.setdefault(job.company, []).append(job)
    min_bootstrap = getattr(config, "BOOTSTRAP_MIN_JOBS", 5)
    bootstrap_companies = {
        c for c, batch in batch_by_company.items()
        if c not in known_companies and len(batch) >= min_bootstrap
    }
    for c in sorted(bootstrap_companies):
        print(f"  🧱 [{c}] 新接入源首抓 {len(batch_by_company[c])} 岗："
              f"bootstrap 静默入库，不计入今日新增")

    def log_event(company, job_id, event, title):
        conn.execute("INSERT INTO job_events (event_at, company, job_id, event, title)"
                     " VALUES (?,?,?,?,?)", (now, company, job_id, event, title))

    for job in jobs:
        current_ids.setdefault(job.company, set()).add(job.job_id)
        existing = conn.execute(
            "SELECT first_seen, title, location FROM jobs WHERE company=? AND job_id=?",
            (job.company, job.job_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                f"INSERT INTO jobs ({_JOB_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (job.company, job.job_id, job.title, job.category, job.location,
                 job.url, job.publish_time, job.tags,
                 job.recruit_type, _job_year(job), now, now),
            )
            inserted_count[job.company] = inserted_count.get(job.company, 0) + 1
            if job.company in bootstrap_companies:
                log_event(job.company, job.job_id, "BOOTSTRAP", job.title)
            else:
                new_keys.add(job.dedup_key)
                was_archived = conn.execute(
                    "SELECT 1 FROM jobs_archive WHERE company=? AND job_id=?",
                    (job.company, job.job_id)).fetchone()
                log_event(job.company, job.job_id,
                          "REOPENED" if was_archived else "CREATED", job.title)
        else:
            if (existing[1], existing[2]) != (job.title, job.location):
                log_event(job.company, job.job_id, "UPDATED", job.title)
            conn.execute(
                "UPDATE jobs SET title=?,category=?,location=?,url=?,publish_time=?,"
                "tags=?,recruit_type=?,recruit_year=?,last_seen=? "
                "WHERE company=? AND job_id=?",
                (job.title, job.category, job.location, job.url, job.publish_time,
                 job.tags, job.recruit_type, _job_year(job), now,
                 job.company, job.job_id),
            )

    # 归档已下线岗位（仅处理本次抓到岗位的公司）
    archived = 0
    guard_ratio = getattr(config, "ARCHIVE_GUARD_RATIO", 0.5)
    guard_min = getattr(config, "ARCHIVE_GUARD_MIN_EXISTING", 10)
    for company, ids in current_ids.items():
        if not ids:
            continue
        # no_archive 源（如猎聘，返回数不稳定）不自动归档，避免误判下线→明天又当新增的抖动
        if config.COMPANY_CONFIG.get(company, {}).get("no_archive"):
            continue
        # 完整性对账不合格的源：本次没抓全，看不到 ≠ 下线了
        if company in suspect_companies:
            print(f"  ⚠️ [{company}] 本次抓取疑似不完整，跳过归档")
            continue
        placeholders = ",".join("?" * len(ids))
        stale = conn.execute(
            f"SELECT {_JOB_COLUMNS} FROM jobs "
            f"WHERE company=? AND job_id NOT IN ({placeholders})",
            (company, *ids),
        ).fetchall()
        if not stale:
            continue
        # 骤降守卫：原库存 = 待归档数 + 本次匹配上的旧岗数（= 抓到数 - 新插入数）
        matched = len(ids) - inserted_count.get(company, 0)
        prev_stock = len(stale) + matched
        if prev_stock >= guard_min and len(stale) > prev_stock * guard_ratio:
            print(f"  ⚠️ [{company}] 疑似部分抓取：原库存 {prev_stock} 岗，本次仅匹配到 "
                  f"{matched} 岗（要归档 {len(stale)} 个 > {guard_ratio:.0%}），"
                  f"已跳过归档。若为真实缩招请人工确认（连续出现请排查该源分页/接口）")
            continue
        for row in stale:
            conn.execute(
                f"INSERT OR REPLACE INTO jobs_archive ({_JOB_COLUMNS},archived_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*row, now),
            )
            log_event(row[0], row[1], "CLOSED", row[2])   # company, job_id, title
        conn.execute(
            f"DELETE FROM jobs WHERE company=? AND job_id NOT IN ({placeholders})",
            (company, *ids),
        )
        archived += len(stale)
    if archived:
        print(f"  🗄️ 已归档 {archived} 个下线岗位（主表只留当前在招）")
    conn.commit()
    conn.close()
    return new_keys


def save_source_health(results) -> None:
    """把本轮各源的 FetchResult 写入健康度表（维护者视角的运行记录，
    可用 sqlite3 查询连续失败/持续不完整的源）。"""
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in results:
        complete = r.complete
        conn.execute(
            "INSERT INTO source_health (run_at, source, success, fetched, raw_fetched,"
            " reported_total, complete, duration_s, error) VALUES (?,?,?,?,?,?,?,?,?)",
            (now, r.source, int(r.success), r.fetched, r.raw_fetched,
             r.reported_total, None if complete is None else int(complete),
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
        (f"{today}%",),
    ).fetchall()
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
