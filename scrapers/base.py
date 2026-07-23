"""抓取层公共设施：BaseScraper 基类 + 抓取期 helper。

数据模型 JobItem 与类别推断 guess_category 已上收到 domain 层
（岗位是领域概念不是爬虫概念）；本模块 re-export 二者，
所有抓取器照旧 `from .base import JobItem, guess_category` 即可。
"""
from datetime import datetime
from typing import List
import config

from domain.models import JobItem            # noqa: F401  re-export
from domain.classify import guess_category   # noqa: F401  re-export


class BaseScraper:
    """抓取器基类。子类只做一件事：fetch() 返回 List[JobItem]。

    不过滤、不碰数据库、不管渲染——那些是上层的事（见 CLAUDE.md 分层规矩）。
    """
    name: str = ""

    def __init__(self, http_session):
        self.session = http_session
        # 完整性对账埋点（FetchResult 用）：fetch 过程中由子类填写。
        # reported_total = 服务端报告的岗位总数；raw_fetched = 分页拿到的原始条数
        # （本地过滤前——只有做本地丢弃的源需要显式设置，其余由 main 按返回数兜底）。
        self.reported_total = None
        self.raw_fetched = None

    def fetch(self) -> List[JobItem]:
        raise NotImplementedError(f"{type(self).__name__} 未实现 fetch()")

    def safe(self, fn, *args, **kwargs):
        """吞掉异常的调用包装：拿不到就算了，别让一个字段毁掉整条岗位"""
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None


# ==================== 抓取期 helper ====================

def ms_to_date(ts) -> str:
    """毫秒时间戳 → YYYY-MM-DD。各大厂 API 普遍用毫秒时间戳发布时间，统一在这转。
    非数字/异常输入按字符串截前 10 位兜底，实在不行返回空串。"""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
    except Exception:
        return str(ts)[:10]


# 经验年限解析已上收到 enrichment 层（职责债还清：抓取层只带回正文，不做判断）。
# re-export 供仍在抓取期用它的旧路径与测试兼容。
from domain.enrich import demands_senior_experience   # noqa: F401, E402  re-export
