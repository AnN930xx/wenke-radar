"""小红书 校招+社招 抓取器
接口: POST https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition
recruitType=campus 校招 / social 社招，一套接口两个入口；
校招额外带 campusRecruitTypes（term_regular=应届）过滤，社招无此字段。
"""
from .base import BaseScraper, JobItem, guess_category
import config

_SITE = "https://job.xiaohongshu.com"

# jobType 编码 → 中文类别（接口返回英文短码）
_JOB_TYPE_NAMES = {"tech": "技术类", "pro": "产品类", "om": "运营类",
                   "design": "设计类", "market": "销售类", "function": "职能类"}


class XiaohongshuScraper(BaseScraper):
    name = "小红书"
    recruit_channel = "campus"   # 社招子类改 "social"
    job_nature = "校招"          # 社招子类改 "社招"（触发届别豁免+经验过滤+每日新增）
    MAX_PAGES = 20

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        raw = []
        page = 1
        while page <= self.MAX_PAGES:
            payload = {
                "recruitType": self.recruit_channel,
                "positionName": "",
                "pageNum": page,
                "pageSize": config.PAGE_SIZE,
                "workplaces": cfg.get("workplaces", []),
            }
            if self.recruit_channel == "campus":
                payload["campusRecruitTypes"] = cfg.get("campus_recruit_types", [])
            r = self.session.post(
                f"{_SITE}/websiterecruit/position/pageQueryPosition",
                json=payload,
                headers={"Content-Type": "application/json",
                         "Referer": f"{_SITE}/{self.recruit_channel}/position"},
                timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if not data.get("success"):
                break
            page_data = data.get("data") or {}
            batch = page_data.get("list") or []
            if not batch:
                break
            raw.extend(batch)
            self.reported_total = page_data.get("total") or None
            if len(raw) >= (page_data.get("total") or 0):
                break
            page += 1

        jobs = [self._parse(it) for it in raw]
        for j in jobs:
            j.recruit_type = self.job_nature
        return jobs

    def _parse(self, it):
        title = (it.get("positionName") or "").strip()
        category = _JOB_TYPE_NAMES.get(it.get("jobType") or "") or guess_category(title)
        return JobItem(
            company=self.name,
            job_id=str(it.get("positionId") or it.get("id") or it.get("code")),
            title=title,
            category=category,
            location=it.get("workplace") or "",     # 接口直接给中文地点
            url=f"{_SITE}/{self.recruit_channel}/position",  # 详情无独立页，落到列表页
            publish_time=(it.get("publishTime") or "")[:10],
            tags=it.get("jobProjectName") or "",
        )


class XiaohongshuSocialScraper(XiaohongshuScraper):
    """小红书社招（recruitType=social）"""
    name = "小红书(社招)"
    recruit_channel = "social"
    job_nature = "社招"
