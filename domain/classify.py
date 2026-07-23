"""标题 → 职位类别 的兜底推断（来源 API 不返回类别时使用）。

属于领域逻辑而非抓取逻辑：抓取层和过滤层都会用到
（抓取期给 category 兜底、过滤期给方向命中补充）。
"""
import config

# config.KEYWORDS 覆盖用户关注方向；这里再补几组通用方向，
# 让"命中方向"之外的岗位也有可读的类别标注。
_EXTRA_CATEGORY_RULES = [
    ("技术", ["算法", "工程师", "开发", "架构", "前端", "后端", "客户端",
              "测试", "运维", "数据", "AI", "大模型", "安全", "Java", "C++",
              "Go", "Python", "研发", "机器学习", "深度学习"]),
    ("设计", ["设计"]),
    ("市场", ["市场", "商务", "销售"]),
    ("职能", ["职能", "财务", "人事", "行政", "法务"]),
]


def guess_category(title: str) -> str:
    """从岗位标题推断职位类别（可多值，顿号相连）"""
    title = title or ""
    hits = []
    for direction, words in config.KEYWORDS.items():
        if direction in title or any(w in title for w in words):
            hits.append(direction)
    for label, words in _EXTRA_CATEGORY_RULES:
        if any(w in title for w in words):
            hits.append(label)
    return "、".join(hits)
