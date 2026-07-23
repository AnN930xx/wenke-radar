"""淘宝（淘天集团）校招抓取器
接口: POST https://talent.taotian.com/position/search
三步走：① 访问页面种 XSRF-TOKEN cookie（兜底从 HTML 里正则抠）；
② /searchCondition/listBatch 拿当季应届生批次 batchId；③ 按批次翻页搜岗位。
所有 POST 都要在 query string 带 _csrf。
"""
import re
from .base import BaseScraper, JobItem, guess_category, ms_to_date
import config


class TaotianScraper(BaseScraper):
    name = "淘宝"

    SITE = "https://talent.taotian.com"
    MAX_PAGES = 20

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Referer": f"{self.SITE}/campus/position",
            "Origin": self.SITE,
            "User-Agent": config.USER_AGENT,
        }

    def _fetch_items(self):
        csrf = self._obtain_csrf()
        batch_id = self._pick_batch(csrf)
        if not batch_id:
            return []

        channel = config.COMPANY_CONFIG["淘宝"]["batch_channel"]
        raw = []
        for page in range(1, self.MAX_PAGES + 1):
            r = self.session.post(
                f"{self.SITE}/position/search", params={"_csrf": csrf},
                json={"batchId": batch_id, "pageIndex": page,
                      "pageSize": config.PAGE_SIZE, "regions": "",
                      "channel": channel, "language": "zh"},
                headers=self._headers(), timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if not data.get("success"):
                break
            content = data.get("content") or {}
            batch = content.get("datas") or []
            raw.extend(batch)
            self.reported_total = (content.get("totalSize") or content.get("totalCount")
                                   or self.reported_total)
            if len(batch) < config.PAGE_SIZE:
                break
        return [self._parse(it) for it in raw]

    def _obtain_csrf(self):
        """访问落地页让服务端种 XSRF-TOKEN；cookie 拿不到就在页面源码里找"""
        r = self.session.get(f"{self.SITE}/campus/position",
                             headers={"User-Agent": config.USER_AGENT},
                             timeout=config.REQUEST_TIMEOUT)
        token = self.session.cookies.get("XSRF-TOKEN")
        if token:
            return token
        for pattern in (r'name=["\']_csrf["\']\s+content=["\']([a-f0-9-]+)',
                        r'["\']_csrf["\']:\s*["\']([a-f0-9-]+)'):
            m = re.search(pattern, r.text)
            if m:
                return m.group(1)
        return ""

    def _pick_batch(self, csrf):
        """列出当季批次，应届生(graduate)优先，其次实习/顶尖人才计划"""
        r = self.session.post(f"{self.SITE}/searchCondition/listBatch",
                              params={"_csrf": csrf}, json={},
                              headers=self._headers(), timeout=config.REQUEST_TIMEOUT)
        content = (r.json() or {}).get("content") or {}
        for kind in ("graduate", "internship", "topTalentPlan"):
            batches = content.get(kind) or []
            if batches:
                return batches[0].get("id")
        return None

    def _parse(self, it):
        job_id = it.get("id")
        title = (it.get("name") or "").strip()
        locations = it.get("workLocations") or []
        cats = it.get("categories")
        if isinstance(cats, list) and cats:
            category = "、".join(str(c) for c in cats)
        else:
            category = guess_category(title)
        return JobItem(
            company=self.name,
            job_id=str(job_id),
            title=title,
            category=category,
            location="、".join(locations) if isinstance(locations, list) else str(locations),
            url=f"{self.SITE}/campus/position/detail?id={job_id}",
            publish_time=ms_to_date(it.get("modifyTime") or it.get("publishTime")),
            tags="T-Star" if "T-Star" in title else "",
        )
