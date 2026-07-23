"""米哈游校园招聘抓取器
接口: POST https://ats.openout.mihoyo.com/ats-portal/v1/job/list
body: {"channelDetailIds": [1], "pageNo": N, "pageSize": M}  (1=校招渠道)
"""
from .base import BaseScraper, JobItem
import config


class MihoyoScraper(BaseScraper):
    name = "米哈游"

    def fetch(self):
        url = "https://ats.openout.mihoyo.com/ats-portal/v1/job/list"
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://jobs.mihoyo.com",
            "Referer": "https://jobs.mihoyo.com/",
        }
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        channel_ids = cfg.get("channel_detail_ids", [1])
        all_items = []
        page = 1
        page_size = 50
        while True:
            body = {
                "channelDetailIds": channel_ids,
                "pageNo": page,
                "pageSize": page_size,
            }
            r = self.session.post(url, json=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if not data.get("success"):
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
        return [self._parse(it) for it in all_items]

    def _parse(self, it):
        job_id = str(it.get("id") or "")
        addr_list = it.get("addressDetailList") or []
        location = "、".join(
            a.get("addressDetail") or "" for a in addr_list if isinstance(a, dict))
        tags_parts = [p for p in [it.get("projectName"), it.get("jobNature")] if p]
        return JobItem(
            company=self.name,
            job_id=job_id,
            title=(it.get("title") or "").strip(),
            category=it.get("competencyType") or "",
            location=location,
            url=f"https://jobs.mihoyo.com/#/campus/position/{job_id}",
            publish_time="",
            tags="、".join(tags_parts),
        )
