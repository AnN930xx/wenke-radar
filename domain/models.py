"""领域模型：JobItem —— 全系统的通用货币。

一条岗位记录的统一形态：抓取层负责产出它（39 个异构源在抓取层内部各自消化差异），
过滤/存储/渲染各层只消费它，对"数据从哪来"零感知。

来源身份（二轮外部审查采纳，v3.1）：
  source_id     稳定的"来源"标识（哪个 feed），健康度/归档/去重的真正主键。
                默认取 company（当前每个源的 company 就是其来源名，二者恒等）；
                未来同一雇主的多来源（校招官网/社招官网/ATS/聚合）可给不同 source_id。
  source_kind   来源可信等级：OFFICIAL_CAREERS / OFFICIAL_ATS / AGGREGATOR_DISCOVERY。
                官方源可为"岗位关闭/更新时间/真实性"背书；聚合发现源只作线索，不 authoritative。
  canonical_job_id  跨源去重预留：同一岗位在多来源出现时指向同一"真实岗位"（暂未启用）。
"""
from dataclasses import dataclass, field
from datetime import datetime

import config


@dataclass
class JobItem:
    """一条岗位记录。

    (source_id, job_id) 构成全局去重键（见 dedup_key），因此数据生产方必须保证
    job_id 在来源内稳定：同一个岗位每次抓取要得到同一个 id，否则新增对比会失真。
    """
    company: str                # 雇主/来源显示名（与 SCRAPERS 注册名一致，日报按它分组）
    job_id: str                 # 来源内稳定的岗位标识
    title: str                  # 岗位名称
    category: str = ""          # 职位类别（产品/运营/…；来源不给时由 classify.guess_category 兜底）
    location: str = ""          # 工作地点（多地点用顿号相连）
    url: str = ""               # 详情/投递页链接
    publish_time: str = ""      # 发布日期 YYYY-MM-DD（拿不到则留空）
    tags: str = ""              # 附加标记（项目名/批次/届别线索等，届别解析也看这里）
    recruit_type: str = "校招"  # 校招 | 社招——社招豁免届别与实习过滤，改走经验/资深过滤
    description: str = ""       # JD 正文/经验要求原文（抓取层带回，enrich 层解析；不落库）
    experience_min_years: int = None  # enrich 解析出的最低经验年限（未提及=None；不落库）
    source_id: str = ""         # 来源身份（空则 __post_init__ 取 company）
    source_kind: str = ""       # 来源可信等级（空则 __post_init__ 按 source_id 推断）
    canonical_job_id: str = ""  # 跨源去重预留（暂未启用）
    fetched_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def __post_init__(self):
        # 来源身份缺省即取 company（当前二者恒等），并推断可信等级——
        # 让所有下游用 source_id 说话，为未来"同雇主多来源"留出分离空间。
        if not self.source_id:
            self.source_id = self.company
        if not self.source_kind:
            self.source_kind = config.source_kind(self.source_id)

    @property
    def dedup_key(self) -> str:
        return f"{self.source_id}::{self.job_id}"
