"""B站（哔哩哔哩）校园招聘抓取器
接口: POST https://jobs.bilibili.com/api/campus/position/positionList
需要伪造前端生成的会话头（X-CSRF 为随机 UUID、Lunar-Id 为时间戳串）。
"""
import time
import uuid
from .base import BaseScraper, JobItem
import config


class BilibiliScraper(BaseScraper):
    name = "B站"
    channel = "campus"   # 子类改 "society" 即社招
    job_nature = "校招"  # 子类改 "社招"
    # 社招接口仍走 campus 路径，靠 X-Channel + Referer 区分（/api/society 不存在）

    def fetch(self):
        url = "https://jobs.bilibili.com/api/campus/position/positionList"
        headers = {
            "Content-Type": "application/json",
            "X-UserType": "2",
            "X-AppKey": "ops.ehr-api.auth",
            "Lunar-Id": f"lunar-{int(time.time() * 1000)}-{uuid.uuid4().int % 10**13}",
            "X-CSRF": str(uuid.uuid4()),
            "X-Channel": self.channel,
            "Referer": f"https://jobs.bilibili.com/{self.channel}/positions",
            "Origin": "https://jobs.bilibili.com",
        }
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        all_items = []
        page = 1
        page_size = 50
        while True:
            body = {
                "pageSize": page_size,
                "pageNum": page,
                "positionName": "",
                "postCode": [],
                "postCodeList": [],
                "workLocationList": [],
                "workTypeList": [],
                "positionTypeList": [],
                "deptCodeList": [],
                "recruitType": cfg.get("recruit_type", 1),
                "practiceTypes": [],
                "onlyHotRecruit": 0,
            }
            r = self.session.post(url, json=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if data.get("code") != 0:
                break
            d = data.get("data") or {}
            items = d.get("list") or []
            if not items:
                break
            all_items.extend(items)
            total = d.get("total") or 0
            self.reported_total = total or None
            if total and len(all_items) >= total:
                break
            if len(items) < page_size:
                break
            page += 1
            if page > 30:
                break
        jobs = [self._parse(it) for it in all_items]
        for j in jobs:
            j.recruit_type = self.job_nature
        return jobs

    def _parse(self, it):
        job_id = str(it.get("id") or "")
        pub = (it.get("pushTime") or "")[:10]
        tags = it.get("positionTypeName") or ""
        return JobItem(
            company=self.name,
            job_id=job_id,
            title=(it.get("positionName") or "").strip(),
            category=it.get("postCodeName") or "",
            location=it.get("workLocation") or "",
            url=f"https://jobs.bilibili.com/{self.channel}/positions/{job_id}",
            publish_time=pub,
            tags=tags,
        )


class BilibiliSocialScraper(BilibiliScraper):
    """B站社招（X-Channel=society，接口仍走 campus 路径）"""
    name = "B站(社招)"
    channel = "society"
    job_nature = "社招"
