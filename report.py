"""简报渲染层（Markdown）—— 只负责"日报长什么样"。

单一职责：把 已过滤 的岗位渲染成 Markdown 日报。
    - 过滤"哪些岗位符合需求" → filters.py
    - 岗位存储 / 新增对比      → store.py
    - 投递记录查询            → tracker.py（本模块通过 tracker.get_recent_applications 取，不直连 DB）
日报结构：🎓校招（2026/2027/不限 三块，只今日新增）+ 💼社招（每日新增），存量只留计数行。
"""
import os
from datetime import datetime, date
from typing import List
from domain.models import JobItem
from filters import filter_jobs, campus_year_bucket
from scoring import score_job, STAR_THRESHOLD
import config


REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

# 公司排序：官网优先，offerstar 最后，社招源排在最后
COMPANY_ORDER = ["腾讯", "字节跳动", "阿里巴巴", "百度", "小米",
                 "网易", "B站", "米哈游", "美团",
                 "京东", "快手", "小红书", "拼多多", "淘宝",
                 "泡泡玛特", "欧莱雅", "农夫山泉", "滴滴", "名创优品",
                 "蒙牛", "伊利", "元气森林",
                 "UCCA", "牛客日程", "offerstar",
                 "泡泡玛特(社招)", "名创优品(社招)", "蒙牛(社招)", "伊利(社招)",
                 "美团(社招)", "滴滴(社招)", "字节跳动(社招)", "腾讯(社招)",
                 "小红书(社招)", "小米(社招)", "B站(社招)", "京东(社招)",
                 "宽创国际", "凯谛思"]


def _company_sort_key(name):
    if name in COMPANY_ORDER:
        return (0, COMPANY_ORDER.index(name))
    return (1, name)  # 未知公司排在最后


def _render_new_by_company(lines, jobs_list, sort_key, heading_level="###"):
    """把一批新增岗按公司分组，各出一张表"""
    by_company = {}
    for j in jobs_list:
        by_company.setdefault(j.company, []).append(j)
    for company in sorted(by_company.keys(), key=sort_key):
        lines.append(f"{heading_level} {company}（{len(by_company[company])}）")
        lines.append("")
        lines.append("| 岗位名称 | 类别 | 地点 | 发布时间 | 标签 | 链接 |")
        lines.append("|---------|------|------|---------|------|------|")
        for j in by_company[company]:
            link = f"[查看]({j.url})" if j.url else "-"
            lines.append(
                f"| {j.title} | {j.category or '-'} | {j.location or '-'} | "
                f"{j.publish_time or '-'} | {j.tags or '-'} | {link} |")
        lines.append("")


def _render_section(lines, section_title, note, jobs_subset, raw_counts_subset,
                    sort_key, all_daily_only=False, year_split=False):
    """渲染一个招聘大区（校招 或 社招）：总览表 + 今日新增 + 当前在招。
    all_daily_only=True（社招区专用）：整区都不铺存量，只报今日新增 + 一行计数，
    社招存量过大，只关心每日更新。"""
    new_jobs = [j for j in jobs_subset if getattr(j, "_is_new", False)]
    existing_jobs = [j for j in jobs_subset if not getattr(j, "_is_new", False)]
    companies = sorted(raw_counts_subset.keys(), key=sort_key)

    lines.append("")
    lines.append(f"# {section_title}")
    lines.append("")
    if note:
        lines.append(f"> {note}")
        lines.append("")

    # 总览表
    lines.append("## 📊 总览")
    lines.append("")
    lines.append("| 公司 | 抓取岗位总数 | 命中方向 | 今日新增 |")
    lines.append("|------|------------|---------|---------|")
    for company in companies:
        cnt = raw_counts_subset[company]
        hit = len([j for j in jobs_subset if j.company == company])
        new = len([j for j in new_jobs if j.company == company])
        lines.append(f"| {company} | {cnt} | {hit} | {new if new else '-'} |")
    lines.append("")

    # 今日新增
    lines.append("## 🆕 今日新增")
    lines.append("")
    if not new_jobs:
        lines.append("今日暂无新增岗位。有新岗位放出时，次日简报会自动列在这里。")
        lines.append("")
    elif year_split:
        # 校招：按届别拆块（顺序来自 config.CAMPUS_FOCUS_YEARS：重点届/关注届/不限·其他）
        focus_years = getattr(config, "CAMPUS_FOCUS_YEARS", ["2026", "2027"])
        bucket_keys = list(focus_years) + ["不限·其他"]
        buckets = {k: [] for k in bucket_keys}
        for j in new_jobs:
            buckets[campus_year_bucket(j)].append(j)
        block_titles = {"不限·其他": "🔄 不限年份/滚动岗新增"}
        marks = ["🎯", "🔭", "📌", "📌"]
        for i, y in enumerate(focus_years):
            suffix = "（重点）" if i == 0 else ""
            block_titles[y] = f"{marks[min(i, 3)]} {y} 届新增{suffix}"
        for key in bucket_keys:
            jobs_b = buckets[key]
            lines.append(f"### {block_titles[key]}（{len(jobs_b)}）")
            lines.append("")
            if jobs_b:
                _render_new_by_company(lines, jobs_b, sort_key, heading_level="####")
            else:
                lines.append("今日无。")
                lines.append("")
    else:
        _render_new_by_company(lines, new_jobs, sort_key)

    # 当前在招（可折叠存量）
    # 社招整区(all_daily_only)或个别 daily_only 大体量源，都不全量铺存量，只给一行计数
    def _daily_only(company):
        return all_daily_only or config.COMPANY_CONFIG.get(company, {}).get("daily_only", False)
    daily_only_jobs = [j for j in existing_jobs if _daily_only(j.company)]
    existing_jobs = [j for j in existing_jobs if not _daily_only(j.company)]

    if existing_jobs:
        lines.append(f"## 📌 当前在招（共 {len(existing_jobs)} 个）")
        lines.append("")
        lines.append("<details><summary>点击展开全部在招岗位</summary>")
        lines.append("")
        by_company = {}
        for j in existing_jobs:
            by_company.setdefault(j.company, []).append(j)
        for company in sorted(by_company.keys(), key=sort_key):
            lines.append(f"**{company}（{len(by_company[company])}）**")
            lines.append("")
            for j in by_company[company]:
                link = f"[查看]({j.url})" if j.url else ""
                tag_str = f"`{j.tags}`" if j.tags else ""
                lines.append(f"- {j.title} ｜ {j.category or ''} ｜ {j.location or ''} ｜ {j.publish_time or ''} {tag_str} {link}")
            lines.append("")
        lines.append("</details>")
        lines.append("")

    if daily_only_jobs:
        by_company = {}
        for j in daily_only_jobs:
            by_company.setdefault(j.company, []).append(j)
        parts = "、".join(f"{c} {len(v)} 个"
                          for c, v in sorted(by_company.items(),
                                             key=lambda kv: sort_key(kv[0])))
        label = "各源在招存量" if all_daily_only else "大体量源另有在招"
        lines.append(f"> 📦 {label}：{parts}（只报每日新增，不铺存量；"
                     f"要看全部存量请直接去对应官网按方向搜索）")
        lines.append("")


def generate_brief(jobs: List[JobItem], new_keys: set, all_raw_count: dict,
                   health_notes: list = None) -> str:
    """生成当日 Markdown 简报。health_notes = 数据完整性告警（维护者视角，
    只进留档版不进微信推送）。"""
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 过滤出目标岗位
    target_jobs = filter_jobs(jobs)
    # 标记新增（校招/社招各自的新增在 _render_section 里按子集计算）
    for j in target_jobs:
        j._is_new = j.dedup_key in new_keys

    lines = []
    lines.append(f"# 📋 秋招雷达日报 · {today}")
    lines.append("")
    focus_str = " / ".join(config.KEYWORDS.keys())
    year_str = getattr(config, "TARGET_YEAR_LABEL", "全部届别") if getattr(config, "ONLY_TARGET_YEAR", False) else "全部届别"
    intern_str = " ｜ 已排除实习岗" if getattr(config, "EXCLUDE_INTERN", False) else ""
    lines.append(f"> 自动抓取于 {now} ｜ {year_str}{intern_str} ｜ 关注方向：{focus_str} ｜ 目标城市：{('、'.join(config.TARGET_CITIES)) or '全国'}")
    lines.append("")

    if health_notes:
        lines.append("> ⚠️ **数据完整性告警**（这些源本次数据可能不全，已跳过归档）：")
        for note in health_notes:
            lines.append(f"> - {note}")
        lines.append("")

    _sort_key = _company_sort_key

    # 按招聘类型拆分：校招正式岗 / 社招入门岗
    campus_jobs = [j for j in target_jobs if getattr(j, "recruit_type", "校招") != "社招"]
    social_jobs = [j for j in target_jobs if getattr(j, "recruit_type", "校招") == "社招"]
    campus_counts = {k: v for k, v in all_raw_count.items() if "(社招)" not in k}
    social_counts = {k: v for k, v in all_raw_count.items() if "(社招)" in k}

    # 顶部：两区岗位数速览
    lines.append(f"**校招正式岗** 命中 {len(campus_jobs)} 个（今日新增 "
                 f"{len([j for j in campus_jobs if getattr(j, '_is_new', False)])}）"
                 f" ｜ **社招入门岗** 命中 {len(social_jobs)} 个（今日新增 "
                 f"{len([j for j in social_jobs if getattr(j, '_is_new', False)])}）")
    lines.append("")

    # 投递进度概览
    app_section = _build_application_section()
    if app_section:
        lines.extend(app_section)

    # ========== 校招大区 ==========
    _render_section(
        lines, "🎓 校招正式岗",
        f"面向应届的校招正式岗（已排除实习）｜方向：{focus_str}｜{year_str}｜"
        f"**只报今日新增**，按 2026/2027/不限 分块；存量不铺",
        campus_jobs, campus_counts, _sort_key,
        all_daily_only=True, year_split=True)

    # ========== 社招大区 ==========
    if social_counts:
        _render_section(
            lines, "💼 社招入门岗",
            f"社招入门级岗位（已排除资深/多年经验岗）｜方向：{focus_str}｜"
            f"**只报今日新增**（只报每日新增，存量不铺）",
            social_jobs, social_counts, _sort_key, all_daily_only=True)

    lines.append("---")
    lines.append("*本简报由 Campus Radar 自动生成。如某公司持续显示 0 岗位，可能是其招聘尚未开启，开启后会自动出现。*")

    content = "\n".join(lines)

    # 写文件
    os.makedirs(REPORT_DIR, exist_ok=True)
    filepath = os.path.join(REPORT_DIR, f"{today}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return content


def generate_push_brief(jobs: List[JobItem], new_keys: set):
    """生成微信推送用的精简简报（格式规范见 docs/推送格式.md）。

    只列当天有新增对口岗位的公司：社招在前、校招在后，每岗一行，
    岗位名称本身是投递链接。完整日报仍由 generate_brief 写入 reports/ 留档。
    返回 (正文, 新增对口岗位数) —— 数量供 main.py 定推送标题。
    """
    target_jobs = filter_jobs(jobs)
    new_jobs = [j for j in target_jobs if j.dedup_key in new_keys]
    if not new_jobs:
        return ("今日各源均无新增对口岗位。系统运行正常，有新岗放出会在次日推送。", 0)

    social = [j for j in new_jobs if getattr(j, "recruit_type", "校招") == "社招"]
    campus = [j for j in new_jobs if getattr(j, "recruit_type", "校招") != "社招"]

    lines = []

    focus_years = getattr(config, "CAMPUS_FOCUS_YEARS", ["2026", "2027"])

    def _render_block(header, jobs_list, with_year=False):
        if not jobs_list:
            return
        lines.append(f"**{header}**")
        lines.append("")
        by_company = {}
        for j in jobs_list:
            by_company.setdefault(j.company, []).append(j)
        for company in sorted(by_company, key=_company_sort_key):
            # 高分在前；区标题已注明社招/校招，公司名不带内部源名的"(社招)"后缀
            scored = sorted(((score_job(j)[0], j) for j in by_company[company]),
                            key=lambda p: -p[0])
            lines.append(f"**{company.replace('(社招)', '')}**（{len(scored)}）")
            for s, j in scored:
                year = ""
                if with_year:
                    bucket = campus_year_bucket(j)
                    year = f"（{bucket}届）" if bucket in focus_years else "（不限届别）"
                loc = f" · {j.location}" if j.location else ""
                star = "⭐ " if s >= STAR_THRESHOLD else ""
                text = f"{star}{j.title}{year}{loc}"
                lines.append(f"- [{text}]({j.url})" if j.url else f"- {text}")
            lines.append("")

    _render_block("💼 社招岗位", social)
    _render_block("🎓 校招岗位", campus, with_year=True)
    lines.append("———")
    lines.append("📡 秋招雷达 ｜ ⭐=高度匹配 ｜ 每日 09:00 自动巡航")
    return ("\n".join(lines).strip(), len(new_jobs))


def _build_application_section():
    """构建投递进度概览（插入每日简报里）。
    投递数据由 tracker 层提供（applications.db 归 tracker 管，本模块不直连 DB）。"""
    try:
        import tracker
        rows = tracker.get_recent_applications()
    except Exception:
        return None
    if not rows:
        return None

    total = len(rows)
    # 按状态分组
    by_status = {}
    for r in rows:
        by_status.setdefault(r[2] or "未知", []).append(r)
    # 进展中的（非终态）
    in_progress = [r for r in rows if r[2] in ("笔试", "一面", "二面", "三面", "HR面")]
    offers = [r for r in rows if r[2] == "Offer"]
    rejected = [r for r in rows if r[2] in ("已拒", "已放弃")]

    lines = []
    lines.append("## 📬 我的投递进度")
    lines.append("")
    lines.append(f"> 共投递 **{total}** 个岗位 ｜ 进行中 **{len(in_progress)}** ｜ Offer **{len(offers)}** ｜ 已结束 **{len(rejected)}**")
    lines.append("")

    # 状态分布条
    status_order = ["待投递", "已投递", "笔试", "一面", "二面", "三面", "HR面", "Offer", "已拒", "已放弃"]
    parts = []
    for s in status_order:
        if s in by_status:
            parts.append(f"`{s}: {len(by_status[s])}`")
    if parts:
        lines.append("  ".join(parts))
        lines.append("")

    # 近期需要关注的（有下一步动作 或 进行中）
    focus = [r for r in rows if r[2] in ("笔试", "一面", "二面", "三面", "HR面") or r[5]]
    if focus:
        lines.append("<details><summary>📍 需关注（进行中 / 有待办）</summary>")
        lines.append("")
        lines.append("| 公司 | 岗位 | 状态 | 投递日期 | 反馈 | 下一步 |")
        lines.append("|------|------|------|---------|------|--------|")
        for r in focus[:15]:
            lines.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3] or '-'} | {r[4] or '-'} | {r[5] or '-'} |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Offer 列表（如果有）
    if offers:
        lines.append("### 🎉 已获 Offer")
        lines.append("")
        for r in offers:
            lines.append(f"- **{r[0]}** - {r[1]} （{r[3]}）")
        lines.append("")

    return lines
