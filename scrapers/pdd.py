"""拼多多校招抓取器
接口: POST https://careers.pddglobalhr.com/api/careers/api/recruit/position/list
明文 JSON，无需 token；t 参数为类别过滤（null=全部）。按"返回不足一页"判停。
"""
from .base import BaseScraper, JobItem, ms_to_date
import config


class PddScraper(BaseScraper):
    name = "拼多多"

    API = "https://careers.pddglobalhr.com/api/careers/api/recruit/position/list"
    HEADERS = {
        "Content-Type": "application/json",
        "Referer": "https://careers.pddglobalhr.com/campus/grad",
    }
    MAX_PAGES = 20

    def fetch(self):
        category_filter = config.COMPANY_CONFIG["拼多多"]["t"]
        raw = []
        for page in range(1, self.MAX_PAGES + 1):
            r = self.session.post(
                self.API,
                json={"page": page, "pageSize": config.PAGE_SIZE, "t": category_filter},
                headers=self.HEADERS, timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if not data.get("success"):
                break
            batch = (data.get("result") or {}).get("list") or []
            raw.extend(batch)
            if len(batch) < config.PAGE_SIZE:
                break
        return [self._parse(it) for it in raw]

    def _parse(self, it):
        job_id = it.get("id") or it.get("code")
        title = (it.get("name") or "").strip()
        return JobItem(
            company=self.name,
            job_id=str(job_id),
            title=title,
            category=it.get("jobName") or "",   # API 直接给中文类别
            location=it.get("workLocationName") or it.get("workLocation") or "",
            url=f"https://careers.pddglobalhr.com/campus/grad/position/detail?id={job_id}",
            publish_time=ms_to_date(it.get("releaseTime")),
            tags="云弧计划" if "云弧" in title else "",
        )
