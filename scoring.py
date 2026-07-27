"""可投程度评分 —— 在"已通过画像过滤的对口岗"内部再分高下。

定位（外部审查采纳项）：过滤层回答"能不能投"（二值），本层回答"多值得投"（0-100）。
用于推送排序与高匹配标记；权重是经验参数，按实际反馈调。
分值解读：>=⭐阈值 高度匹配 / 70~阈值 值得尝试 / <70 一般。

**权重可自定义**：所有加减分项都从 `config.SCORING_WEIGHTS` 读取（缺项自动用内置默认值），
⭐ 阈值来自 `config.SCORING_STAR_THRESHOLD`。想让"新发布"更重要、或不在乎城市，
改 config 里那一个数字即可，不用动本文件。
"""
from datetime import date, datetime

import config

# 内置默认权重（config 未覆盖时生效）。改这里等于改全局默认，
# 个人偏好请改 config.SCORING_WEIGHTS，不要动这里。
DEFAULT_WEIGHTS = {
    "base": 50,               # 起评分
    "direction_hit": 15,      # 命中一个关注方向
    "direction_extra": 5,     # 每多命中一个方向（最多再算 2 个）
    "city_match": 10,         # 落在目标城市（未设城市偏好时人人有份）
    "campus": 15,             # 校招通道（应届友好）
    "experience_unknown": 5,  # 社招但没写经验要求
    "experience_low": 15,     # 社招且要求 <=1 年经验
    "fresh_grad_friendly": 5, # 标题含 管培/培训生/应届
    "fresh_posting": 10,      # 7 天内新发布
    "stale_posting": -10,     # 挂满 30 天（可能已招满未下架）
}

DEFAULT_STAR_THRESHOLD = 85


def _w(key: str) -> int:
    """取权重：config.SCORING_WEIGHTS 覆盖优先，缺项回落内置默认（坏配置不崩）。"""
    custom = getattr(config, "SCORING_WEIGHTS", None)
    if isinstance(custom, dict):
        v = custom.get(key)
        if isinstance(v, (int, float)):
            return int(v)
    return DEFAULT_WEIGHTS[key]


def star_threshold() -> int:
    v = getattr(config, "SCORING_STAR_THRESHOLD", None)
    return int(v) if isinstance(v, (int, float)) else DEFAULT_STAR_THRESHOLD


# 兼容旧引用（report 里 `from scoring import STAR_THRESHOLD`）：
# 模块级常量取当前配置值；运行期改配置请用 star_threshold()。
STAR_THRESHOLD = star_threshold()


def _days_since(publish_time: str):
    """发布距今天数；解析不了返回 None"""
    if not publish_time:
        return None
    try:
        d = datetime.strptime(publish_time[:10], "%Y-%m-%d").date()
        return (date.today() - d).days
    except ValueError:
        return None


def score_job(job):
    """对已过滤的对口岗打分，返回 (0-100 分值, 加减分原因列表)"""
    score, reasons = _w("base"), []

    # 方向命中强度：命中一个关注方向 +15，多方向岗再 +5/个（封顶再加 2 个）
    hits = [d for d in config.KEYWORDS if d in (job.category or "")]
    if hits:
        score += _w("direction_hit") + min(len(hits) - 1, 2) * _w("direction_extra")
        reasons.append("方向:" + "/".join(hits))

    # 城市：明确落在目标城市 +10（空/全国不加分也不扣——过滤层已保证不在错误城市）。
    # 未配置城市偏好（TARGET_CITIES=[]，开源版默认）时，城市不是区分维度：
    # 一律给这 10 分，否则每个岗都被系统性扣 10 分、⭐ 高匹配几乎永远够不到。
    loc = job.location or ""
    if not config.TARGET_CITIES:
        score += _w("city_match")
    elif loc and any(c in loc for c in config.TARGET_CITIES):
        score += _w("city_match")
        reasons.append("城市匹配")

    # 应届友好度
    if job.recruit_type == "校招":
        score += _w("campus")
        reasons.append("校招通道")
    else:
        y = job.experience_min_years
        if y is None:
            score += _w("experience_unknown")
            reasons.append("未标经验")
        elif y <= 1:
            score += _w("experience_low")
            reasons.append(f"经验{y}年可投")
    if any(k in job.title for k in ("管培", "培训生", "应届")):
        score += _w("fresh_grad_friendly")
        reasons.append("应届友好岗")

    # 新鲜度：7 天内新发布加分；挂超 30 天扣分（可能已招满未下架）
    days = _days_since(job.publish_time)
    if days is not None:
        if days <= 7:
            score += _w("fresh_posting")
            reasons.append("新发布")
        elif days > 30:
            score += _w("stale_posting")
            reasons.append("发布超30天")

    return max(0, min(100, score)), reasons


def tier(score: int) -> str:
    t = star_threshold()
    if score >= t:
        return "高度匹配"
    if score >= 70:
        return "值得尝试"
    return "一般"
