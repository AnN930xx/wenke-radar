"""岗位过滤层 —— 只负责"哪些岗位符合求职需求"的业务规则判定。

单一职责：纯函数，输入 JobItem，输出布尔/子集/届别分类。
    - 不碰网络抓取（那是 scrapers/ 的事）
    - 不碰 Markdown 渲染（那是 report.py 的事）
    - 不碰数据库存储（那是 store.py / tracker.py 的事）
所有"求职偏好"（方向、城市、届别、排实习、排资深）都在这里统一裁决，
config.py 只提供数据（关键词表/城市表/开关），本层提供逻辑。

对外主要接口：
    filter_jobs(jobs)         -> 过滤后的岗位子集（日报只展示这些）
    campus_year_bucket(job)   -> "2026" / "2027" / "不限·其他"（校招按届别分块用）
    parse_recruit_year(text)  -> 从文本解析届别串（store 写 recruit_year 列也用它）
"""
import re
from typing import List
from domain.models import JobItem
from domain.classify import guess_category
from domain.enrich import enrich, demands_senior_experience
import config


# ==================== 届别 token 推导（画像驱动，任意年份可用）====================
# 从 config.TARGET_GRAD_YEARS 自动生成保留/排除 token——用户改任何年份组合（[2024]、
# [2027,2028]、跨十年都行）系统即刻适配，无需改代码。规则每次按 config 现值计算并缓存，
# 运行期改 config（含测试 monkeypatch）自动生效；非法配置在第一次过滤时给出人话报错。

def _year_tokens(year: int) -> List[str]:
    """一个届别年份的各种常见写法：2026 / 2026届 / 26届 / 26秋 / 26春 / 26校 / 2026春 / 2026秋"""
    full, two = str(year), str(year)[2:]
    return [full, f"{full}届", f"{two}届",
            f"{two}秋", f"{two}春", f"{two}校", f"{full}春", f"{full}秋"]


_year_rule_cache = {}


def year_rules():
    """返回 (保留token, 排除token)。排除窗口=目标届别前后各约6年里的非目标年份
    （更早=往届不再招，更晚=还轮不到），随目标届别移动，不存在写死的年份区间。"""
    targets = tuple(getattr(config, "TARGET_GRAD_YEARS", []) or ())
    for y in targets:
        if not isinstance(y, int) or not 2000 <= y <= 2099:
            raise ValueError(
                f"config.TARGET_GRAD_YEARS 含非法年份 {y!r}——"
                f"请填 2000~2099 的整数列表，如 [2025, 2026, 2027]")
    if _year_rule_cache.get("targets") != targets:
        keep = [t for y in targets for t in _year_tokens(y)]
        lo, hi = (min(targets), max(targets)) if targets else (0, 0)
        reject = [t for y in range(max(lo - 6, 2000), min(hi + 7, 2100))
                  if y not in targets for t in _year_tokens(y)]
        _year_rule_cache.update(targets=targets, keep=keep, reject=reject)
    return _year_rule_cache["keep"], _year_rule_cache["reject"]


def campus_focus_years() -> List[str]:
    """日报分块用的重点届别列表。未显式配置 CAMPUS_FOCUS_YEARS 时，
    自动取全部目标届别（每届一个分块）——改 TARGET_GRAD_YEARS 不用同步改这里。"""
    configured = getattr(config, "CAMPUS_FOCUS_YEARS", None)
    if configured:
        return [str(y) for y in configured]
    return [str(y) for y in getattr(config, "TARGET_GRAD_YEARS", [])]


# ==================== 届别解析 ====================
def parse_recruit_year(text: str) -> str:
    """从标题/标签解析届别，如 "2026"、"2026/2027"；没写年份返回 "不限"。
    识别 "2026届/2026" "26届" "26秋/26春/26校" 等写法，覆盖 20xx 全部年份
    （不锁定某个年代，用户任意配置届别窗口都能识别）；(?<!\\d)(?!\\d) 防薪资等长数字误匹配。
    """
    years = set()
    for m in re.finditer(r"(?<!\d)(20\d{2})(?!\d)", text or ""):
        years.add(m.group(1))
    # 两位数写法限定 1x~4x（"26届/30届"），避开"第5届/第100届"这类序数词
    for m in re.finditer(r"(?<!\d)([1-4]\d)\s*(?:届|秋|春|校)", text or ""):
        years.add("20" + m.group(1))
    return "/".join(sorted(years)) if years else "不限"


def campus_year_bucket(job) -> str:
    """把校招岗分到届别桶（桶顺序来自 campus_focus_years()，第一个为重点届）。
    双届岗（如2026/2027）归入排在前面的重点桶；不含任何关注届别 → 不限·其他（滚动岗等）。"""
    y = parse_recruit_year(f"{job.title} {job.tags} {job.category}")
    for focus in campus_focus_years():
        if focus in y:
            return focus
    return "不限·其他"


# ==================== 单项匹配规则 ====================
def _match_year(job: JobItem) -> bool:
    """届别过滤（仅校招）：保留目标届别窗口内的岗，排除更早/更晚；未提年份=滚动招聘=保留。
    token 由 TARGET_GRAD_YEARS 自动推导（见文件顶部），每年只需改 config 里的年份列表。"""
    if not getattr(config, "ONLY_TARGET_YEAR", False):
        return True
    keep_tokens, reject_tokens = year_rules()
    text = f"{job.title} {job.category} {job.tags}"
    if any(kw in text for kw in keep_tokens):
        return True
    if any(kw in text for kw in reject_tokens):
        return False
    return True  # 未提年份=滚动招聘，可投，保留


def _match_not_intern(job: JobItem) -> bool:
    """排除实习岗（家人已毕业，只留校招正式/社招岗）。"""
    if not getattr(config, "EXCLUDE_INTERN", False):
        return True
    text = f"{job.title} {job.tags} {job.category}".lower()
    kws = [k.lower() for k in getattr(config, "INTERN_KEYWORDS", [])]
    return not any(k in text for k in kws)


def _match_not_senior(job: JobItem) -> bool:
    """社招岗剔除资深岗（求职者刚毕业只投入门级）：
    ① 标题/类别含资深关键词 → 排除；
    ② JD 正文/经验字段（抓取层带回的 description）要求超过阈值年限 → 排除。
    （②原在抓取期执行，已按外部审查搬到本层——同一份抓取数据可复用给不同经验阈值的画像。）"""
    kws = getattr(config, "SOCIAL_EXCLUDE_SENIORITY", [])
    text = f"{job.title} {job.category}".lower()
    if any(k.lower() in text for k in kws):
        return False
    if job.description and demands_senior_experience(job.description):
        return False
    return True


def _match_keywords(job: JobItem) -> bool:
    """判断岗位是否命中关注方向（先排技术岗，再按类别命中，再按标题关键词兜底）。"""
    exclude = getattr(config, "EXCLUDE_TITLE_KEYWORDS", [])
    if any(kw in job.title for kw in exclude):
        return False
    text = f"{job.title} {job.category} {job.tags}"
    for cat_kw in config.CATEGORY_KEYWORDS:
        if cat_kw in job.category:
            return True
    all_kw = []
    for kws in config.KEYWORDS.values():
        all_kw.extend(kws)
    return any(kw in text for kw in all_kw)


def _match_city(job: JobItem) -> bool:
    """判断岗位是否在目标城市（空配置=不限；全国/多地岗保留）。"""
    if not config.TARGET_CITIES:
        return True
    loc = job.location or ""
    if not loc or "全国" in loc:
        return True
    return any(city in loc for city in config.TARGET_CITIES)


def _enrich_category(job: JobItem) -> JobItem:
    """若 category 不含关注方向关键词，用 guess_category 从标题补充（只补关注方向，不加技术等）。"""
    has_focus = any(kw in job.category for kw in config.CATEGORY_KEYWORDS)
    if not has_focus:
        guessed = guess_category(job.title)
        focus_cats = [c for c in guessed.split("、") if c in config.KEYWORDS.keys()]
        if focus_cats:
            existing = [c for c in job.category.split("、") if c] if job.category else []
            merged = list(dict.fromkeys(focus_cats + existing))
            job.category = "、".join(merged)
    return job


# ==================== 总过滤入口 ====================
def filter_jobs(jobs: List[JobItem]) -> List[JobItem]:
    """按 求职偏好 过滤岗位，返回符合需求的子集（日报只展示这些）。
    校招：届别 + 排实习 + 方向 + 城市。
    社招：豁免届别/实习（社招不分届、无实习概念），改为剔除资深岗 + 方向 + 城市。"""
    result = []
    for j in jobs:
        _enrich_category(j)
        enrich(j)   # 补全结构化字段（经验年限等），供过滤与评分使用
        is_social = getattr(j, "recruit_type", "校招") == "社招"
        year_ok = True if is_social else _match_year(j)
        intern_ok = True if is_social else _match_not_intern(j)
        senior_ok = _match_not_senior(j) if is_social else True
        if year_ok and intern_ok and senior_ok and _match_keywords(j) and _match_city(j):
            result.append(j)
    return result
