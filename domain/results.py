"""抓取结果元数据：把"这次抓取可不可信"变成一等公民。

背景（外部审查 P0-2）：抓取器只返回 List[JobItem] 时，
"真没岗位 / 解析失效变空 / 分页断了只抓到一部分"三种情况长得一模一样。
FetchResult 记录抓取过程的元数据，让下游能区分：
  - success   : 抓取过程没有抛异常
  - complete  : 与服务端报告总数对账的结论（True 抓全 / False 疑似缺页 / None 无法判断）
对账基准是 raw_fetched（分页拿到的原始条数，本地过滤前）——
字节/腾讯社招等源会在分页后本地丢弃资深岗，返回数天然小于服务端总数，不能拿来对。
"""
from dataclasses import dataclass

import config


@dataclass
class FetchResult:
    source: str                 # 源名（与 SCRAPERS 注册名一致）
    fetched: int                # 最终返回的岗位数（本地过滤后）
    raw_fetched: int            # 分页拿到的原始条数（无本地过滤的源 = fetched）
    reported_total: int | None  # 服务端报告的总数（源未提供则 None）
    success: bool               # 抓取过程未抛异常
    duration_s: float
    error: str = ""
    ratio_override: float = None  # 按源校准的对账比例（北森系总数虚高，见 config complete_ratio）

    @property
    def complete(self):
        """True=抓全 / False=疑似不完整 / None=无从判断（源不提供总数）"""
        if not self.success:
            return False
        if not self.reported_total:
            return None
        ratio = self.ratio_override or getattr(config, "FETCH_COMPLETE_RATIO", 0.9)
        return self.raw_fetched >= self.reported_total * ratio

    def describe(self) -> str:
        if self.complete is False and self.success:
            return (f"{self.source}: 服务端报告 {self.reported_total} 岗，"
                    f"实际只拿到 {self.raw_fetched}（疑似分页断裂/接口改版）")
        if not self.success:
            return f"{self.source}: 抓取失败 {self.error[:80]}"
        return f"{self.source}: 正常（{self.fetched} 岗）"
