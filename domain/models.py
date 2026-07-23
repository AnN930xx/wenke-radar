"""领域模型：JobItem —— 全系统的通用货币。

一条岗位记录的统一形态：抓取层负责产出它（39 个异构源在抓取层内部各自消化差异），
过滤/存储/渲染各层只消费它，对"数据从哪来"零感知。
之所以放在独立的 domain 层而不是 scrapers 里：岗位是领域概念不是爬虫概念——
未来的人工录入、RSS、合作方 API 等来源同样产出 JobItem，不该被迫"看起来来自爬虫"。
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobItem:
    """一条岗位记录。

    company + job_id 构成全局去重键（见 dedup_key），因此数据生产方必须保证
    job_id 在公司内稳定：同一个岗位每次抓取要得到同一个 id，否则新增对比会失真。
    """
    company: str                # 来源公司/源名（与 SCRAPERS 注册名一致）
    job_id: str                 # 公司内稳定的岗位标识
    title: str                  # 岗位名称
    category: str = ""          # 职位类别（产品/运营/…；来源不给时由 classify.guess_category 兜底）
    location: str = ""          # 工作地点（多地点用顿号相连）
    url: str = ""               # 详情/投递页链接
    publish_time: str = ""      # 发布日期 YYYY-MM-DD（拿不到则留空）
    tags: str = ""              # 附加标记（项目名/批次/届别线索等，届别解析也看这里）
    recruit_type: str = "校招"  # 校招 | 社招——社招豁免届别与实习过滤，改走经验/资深过滤
    description: str = ""       # JD 正文/经验要求原文（抓取层带回，enrich 层解析；不落库）
    experience_min_years: int = None  # enrich 解析出的最低经验年限（未提及=None；不落库）
    fetched_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def dedup_key(self) -> str:
        return f"{self.company}::{self.job_id}"
