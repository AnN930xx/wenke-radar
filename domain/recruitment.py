"""招聘领域的纯解析逻辑（无画像、无 IO）。

parse_recruit_year 是"从文本认出届别年份"这件纯粹的领域小事，
store（打 recruit_year 标签）和 filters（届别过滤/分桶）都要用——
放在 domain 层，让 store 只依赖 domain、不必依赖 filters（二轮审查采纳的分层精修）。
画像相关的届别规则（目标窗口/分桶顺序，依赖 config.TARGET_GRAD_YEARS）仍留在 filters。
"""
import re


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
