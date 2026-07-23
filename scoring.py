"""可投程度评分 —— 在"已通过画像过滤的对口岗"内部再分高下。

定位（外部审查采纳项）：过滤层回答"能不能投"（二值），本层回答"多值得投"（0-100）。
用于推送排序与高匹配标记；权重是经验参数，按实际反馈调。
分值解读：>=85 高度匹配(⭐) / 70-84 值得尝试 / <70 一般。
"""
from datetime import date, datetime

import config

STAR_THRESHOLD = 85


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
    score, reasons = 50, []

    # 方向命中强度：命中一个关注方向 +15，多方向岗再 +5/个（封顶 +25）
    hits = [d for d in config.KEYWORDS if d in (job.category or "")]
    if hits:
        score += 15 + min(len(hits) - 1, 2) * 5
        reasons.append("方向:" + "/".join(hits))

    # 城市：明确落在目标城市 +10（空/全国不加分也不扣——过滤层已保证不在错误城市）
    loc = job.location or ""
    if loc and any(c in loc for c in config.TARGET_CITIES):
        score += 10
        reasons.append("城市匹配")

    # 应届友好度
    if job.recruit_type == "校招":
        score += 15
        reasons.append("校招通道")
    else:
        y = job.experience_min_years
        if y is None:
            score += 5
            reasons.append("未标经验")
        elif y <= 1:
            score += 15
            reasons.append(f"经验{y}年可投")
    if any(k in job.title for k in ("管培", "培训生", "应届")):
        score += 5
        reasons.append("应届友好岗")

    # 新鲜度：7 天内新发布 +10；挂超 30 天 -10（可能已招满未下架）
    days = _days_since(job.publish_time)
    if days is not None:
        if days <= 7:
            score += 10
            reasons.append("新发布")
        elif days > 30:
            score -= 10
            reasons.append("发布超30天")

    return max(0, min(100, score)), reasons


def tier(score: int) -> str:
    if score >= STAR_THRESHOLD:
        return "高度匹配"
    if score >= 70:
        return "值得尝试"
    return "一般"
