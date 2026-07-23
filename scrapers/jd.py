"""京东校招抓取器
接口: POST https://campus.jd.com/api/wx/position/page?type=present（微信小程序同款接口）
type=present 即"应届生"批次；翻页从 pageIndex=0 起，按 totalNumber 判停。
"""
from .base import BaseScraper, JobItem, ms_to_date
import config


class JdScraper(BaseScraper):
    name = "京东"

    API = "https://campus.jd.com/api/wx/position/page"
    HEADERS = {
        "Content-Type": "application/json",
        "Referer": "https://campus.jd.com/",
        "Origin": "https://campus.jd.com",
    }
    MAX_PAGES = 21

    def _fetch_items(self):
        recruit_batch = config.COMPANY_CONFIG["京东"]["type"]
        raw = []
        for page in range(self.MAX_PAGES):
            payload = {
                "pageSize": config.PAGE_SIZE,
                "pageIndex": page,
                "parameter": {
                    "positionName": "",
                    "planIdList": [],
                    "jobDirectionCodeList": [],
                    "workCityCodeList": [],
                    "positionDeptList": [],
                },
            }
            r = self.session.post(self.API, params={"type": recruit_batch},
                                  json=payload, headers=self.HEADERS,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if not data.get("success"):
                break
            body = data.get("body") or {}
            batch = body.get("items") or []
            if not batch:
                break
            raw.extend(batch)
            self.reported_total = body.get("totalNumber") or None
            if len(raw) >= (body.get("totalNumber") or 0):
                break
        return [self._parse(it) for it in raw]

    def _parse(self, it):
        req_id = str(it.get("reqId", ""))
        direction = it.get("jobDirection") or ""
        return JobItem(
            company=self.name,
            job_id=req_id,
            title=(it.get("positionName") or "").strip(),
            category=self._category(it, direction),
            location=it.get("workCity") or "",
            url=f"https://campus.jd.com/#/jobs?reqId={req_id}",
            publish_time=ms_to_date(it.get("publishTime")),
            tags=direction,
        )

    def _category(self, it, direction):
        # jobDirection 粒度太粗（如"综合类"），优先从部门名/岗位名里找方向词
        haystack = f"{it.get('positionDept') or ''} {it.get('positionName') or ''}"
        for kw in config.CATEGORY_KEYWORDS:
            if kw in haystack:
                return kw
        return direction
