"""抓取层公共设施：BaseScraper 基类 + 抓取期 helper。

数据模型 JobItem 与类别推断 guess_category 已上收到 domain 层
（岗位是领域概念不是爬虫概念）；本模块 re-export 二者，
所有抓取器照旧 `from .base import JobItem, guess_category` 即可。
"""
import time
import traceback
from datetime import datetime
from typing import List
import config

from domain.models import JobItem            # noqa: F401  re-export
from domain.classify import guess_category   # noqa: F401  re-export
from domain.results import FetchResult


class BaseScraper:
    """抓取器基类。

    对外唯一契约（二轮审查采纳）：`fetch() -> FetchResult`——岗位与完整性同一通道返回，
    main 不再靠读实例属性"猜"是否抓全。子类只实现 `_fetch_items()` 返回 List[JobItem]，
    并在分页循环里按需设 self.reported_total / self.raw_fetched；计时、异常兜底、
    完整性元数据组装全部由本基类的 fetch() 统一完成。
    不过滤、不碰数据库、不管渲染——那些是上层的事（见 CLAUDE.md 分层规矩）。
    """
    name: str = ""

    def __init__(self, http_session):
        self.session = http_session
        # 完整性对账埋点：_fetch_items 过程中由子类按需填写。
        # reported_total = 服务端报告的岗位总数；raw_fetched = 分页原始条数（本地过滤前，
        # 只有做本地丢弃的源需要显式设置，其余由 fetch() 按返回数兜底）。
        self.reported_total = None
        self.raw_fetched = None

    def _fetch_items(self) -> List[JobItem]:
        """子类实现：从来源拿到 JobItem 列表。不要在这里 catch 全局异常。"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 _fetch_items()")

    def fetch(self) -> FetchResult:
        """唯一对外入口：跑抓取，无论成败都返回一个自洽的 FetchResult（含 items + 完整性）。"""
        started = time.time()
        self.reported_total = None
        self.raw_fetched = None
        ratio = config.COMPANY_CONFIG.get(self.name, {}).get("complete_ratio")
        try:
            items = self._fetch_items()
            return FetchResult(
                source=self.name, items=items, fetched=len(items),
                raw_fetched=self.raw_fetched if self.raw_fetched is not None else len(items),
                reported_total=self.reported_total, success=True,
                duration_s=round(time.time() - started, 1), ratio_override=ratio)
        except Exception as e:
            traceback.print_exc()
            return FetchResult(
                source=self.name, items=[], fetched=0, raw_fetched=0,
                reported_total=None, success=False,
                duration_s=round(time.time() - started, 1), error=str(e),
                ratio_override=ratio)

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
