"""信息抽取（enrichment）层：从 JD 正文/结构化字段提取可过滤、可评分的结构化信息。

职责边界（外部审查"经验判断不该在抓取期"的修复）：
    抓取层只负责把正文带回来（JobItem.description）——
    本层负责理解它。数据流：抓取 → description 原文 → enrich 解析 → filters 过滤 / scoring 评分。
"""
import re

import config

_ZH_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def extract_experience_years(text: str) -> list:
    """解析文本里出现的全部经验年限要求（区间取下限）。

    覆盖写法："3年以上产品经验" / "3-5年经验" / "三年以上工作经验" / "5年+"。
    (?<!\\d) 防止把 "2026年" 里的 "26年" 误判成经验年限；
    (?<![\\d\\-–~到至]) 防止 "1-3年经验" 里的 "3年经验" 被单独匹配（区间已按下限计）。
    """
    if not text:
        return []
    years = []
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*[-–~到至]\s*\d{1,2}\s*年", text):
        years.append(int(m.group(1)))
    for m in re.finditer(
            r"(?<![\d\-–~到至])(\d{1,2})\s*年(?:以上|及以上|\+)?[^\n，。;；]{0,12}?(?:经验|经历)",
            text):
        years.append(int(m.group(1)))
    for m in re.finditer(
            r"([一两二三四五六七八九十])\s*年(?:以上|及以上)?[^\n，。;；]{0,12}?(?:经验|经历)",
            text):
        years.append(_ZH_NUM[m.group(1)])
    return years


def parse_min_experience_years(text: str):
    """最低经验年限（给评分/展示用）；文本未提经验返回 None"""
    years = extract_experience_years(text)
    return min(years) if years else None


def demands_senior_experience(text: str, max_years: int = None) -> bool:
    """社招入门过滤判据：文本里任一处经验要求超过 max_years 年 → True。
    （用 any 而非 min：JD 同时写"1-3年或5年专家"时按更严的一档拦，宁缺勿滥。）"""
    if max_years is None:
        max_years = getattr(config, "SOCIAL_MAX_EXPERIENCE_YEARS", 2)
    return any(y > max_years for y in extract_experience_years(text))


def enrich(job):
    """就地补全 JobItem 的结构化字段（幂等）。目前：最低经验年限。"""
    if job.experience_min_years is None and job.description:
        job.experience_min_years = parse_min_experience_years(job.description)
    return job
