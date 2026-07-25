"""秋招雷达 —— 入口与编排
串起完整流水线：抓取(scrapers) → 入库+新增对比(store) → 渲染(report) → 推送(push)。

用法:
    python main.py            # 日常运行：对比历史，报告今日新增
    python main.py --full     # 全量初始化：清库重建，不标记新增（首次部署用）

Windows 本地务必带 PYTHONUTF8=1（GBK 控制台打印 emoji/中文会崩）。
"""
import sys
import traceback
from datetime import date

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
import store
import report
import push
from domain.results import FetchResult
from domain.delivery import summarize_push
from scrapers import SCRAPERS
from scrapers.generic import GenericScraper


def build_http_session():
    """带重试的共享 HTTP 会话（5xx 自动重试，GET/POST 都算）"""
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT})
    retry = Retry(total=config.MAX_RETRIES, backoff_factor=1,
                  status_forcelist=[500, 502, 503, 504],
                  allowed_methods=["GET", "POST"])
    for scheme in ("https://", "http://"):
        s.mount(scheme, HTTPAdapter(max_retries=retry))
    return s


def run_all_scrapers(session):
    """跑完所有启用的源。单源失败只记 0 条，绝不拖垮整轮抓取。
    返回 (全部岗位列表, {源名: 原始抓取数}, [FetchResult 完整性元数据])。"""
    jobs, counts, results = [], {}, []

    def run_one(name, make_scraper):
        print(f"\n[{name}] 抓取中...")
        try:
            scraper = make_scraper()
        except Exception as e:                    # 抓取器构造失败（配置错等）
            print(f"  ❌ 构造失败: {e}")
            traceback.print_exc()
            counts[name] = 0
            results.append(FetchResult(source=name, success=False, error=str(e)))
            return
        result = scraper.fetch()                  # 唯一契约：FetchResult（含 items + 完整性）
        jobs.extend(result.items)
        counts[name] = result.fetched
        if result.success:
            state = "" if result.complete is not False else "（⚠️ 疑似不完整）"
            print(f"  ✅ 获取 {result.fetched} 个岗位{state}")
        else:
            print(f"  ❌ 抓取失败: {result.error}")
        results.append(result)

    for name, cls in SCRAPERS.items():
        if not config.ENABLED_COMPANIES.get(name, True):
            print(f"[{name}] 已跳过（配置关闭）")
            continue
        run_one(name, lambda c=cls: c(session))

    # 配置声明的通用源（GENERIC_SOURCES，零代码接入）
    for src in getattr(config, "GENERIC_SOURCES", []):
        run_one(src.get("name", "未知"), lambda s=src: GenericScraper(session, s))

    return jobs, counts, results


def main():
    full_mode = "--full" in sys.argv
    print("=" * 50)
    print(f"秋招雷达启动 ｜ 模式: {'全量初始化' if full_mode else '日常抓取'}")
    print("=" * 50)

    all_jobs, raw_counts, fetch_results = run_all_scrapers(build_http_session())

    # 完整性判定（分级）：只有官方源的"疑似不完整"才跳过归档 + 告警——
    # 聚合发现源（猎聘/牛客/offerstar）本就不 authoritative，其不完整是常态、不误报警。
    suspects = {r.source for r in fetch_results
                if r.complete is False and r.success and config.is_authoritative(r.source)}
    health_notes = [r.describe() for r in fetch_results
                    if not r.success or (r.complete is False and config.is_authoritative(r.source))]
    if health_notes:
        print("\n⚠️ 数据完整性告警：")
        for note in health_notes:
            print(f"  - {note}")

    if full_mode:
        store.clear_all()
        store.save_jobs(all_jobs, suspect_sources=suspects)
        new_keys = set()   # 初始化建库，不报新增
    else:
        new_keys = store.save_jobs(all_jobs, suspect_sources=suspects)
    store.save_source_health(fetch_results)

    print(f"\n{'=' * 50}")
    print(f"抓取完成：共 {len(all_jobs)} 个岗位，本次新增 {len(new_keys)} 个")
    print(f"数据库累计：{store.get_all_jobs_count()} 个岗位")

    # 投递数据由编排层从 tracker 取好、传给纯渲染的 report（report 不直连 DB）
    try:
        import tracker
        applications = tracker.get_recent_applications()
    except Exception:
        applications = None

    # 完整日报写 reports/ 留档（含维护者视角的完整性告警）
    content = report.generate_brief(all_jobs, new_keys, raw_counts,
                                    health_notes=health_notes, applications=applications)
    today = date.today()
    print(f"\n📄 简报已生成：reports/{today.isoformat()}.md")
    print("=" * 50)

    # 微信等渠道推精简版（格式见 docs/推送格式.md），完整日报只留档不推送
    print("\n📤 推送简报...")
    push_content, push_new = report.generate_push_brief(all_jobs, new_keys)
    date_label = f"{today.month}月{today.day}日"
    if full_mode:
        title = f"秋招雷达初始化完成 · {date_label}"
    elif push_new > 0:
        title = f"今日新发布岗位 · {date_label}"
    else:
        title = f"今日无新增岗位 · {date_label}"
    # 送达检测：逐渠道结果落库（可观测）+ 汇总。全渠道失败=用户没收到 → 退出码非零，
    # 让 GitHub 运行标红并邮件告警（唯一能"出圈"通知到人的兜底，因为推送渠道本身正是失败的那个）。
    # 报告已存 reports/ 并进运行摘要，即便微信没推到，也能在告警邮件点进去看当天岗位。
    push_results = push.send_brief(push_content, title=title)
    store.save_push_health(push_results)
    summary = summarize_push(push_results)
    if summary.all_failed:
        print(f"\n❌ 推送全部失败（{summary.failed}/{summary.total} 渠道），本次未送达用户。"
              f"\n   → 运行将标红，请查收 GitHub 告警邮件；当天日报见运行摘要 / reports/。")
        sys.exit(1)
    return content


if __name__ == "__main__":
    main()
