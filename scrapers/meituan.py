"""美团校园招聘抓取器
接口: POST https://zhaopin.meituan.com/api/official/job/getJobList
官网接口不支持按校招过滤（服务端忽略过滤参数），只能全量翻页后
本地筛选 jobType == "2"（校招）。每页固定 20 条，全量约 130+ 页。
"""
import time
from datetime import datetime
from .base import BaseScraper, JobItem
import config


class MeituanScraper(BaseScraper):
    name = "美团"

    def _fetch_items(self):
        url = "https://zhaopin.meituan.com/api/official/job/getJobList"
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://zhaopin.meituan.com",
            "Referer": "https://zhaopin.meituan.com/web/position?hiringType=2_3",
        }
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        max_pages = cfg.get("max_pages", 200)
        # jobType: 2=校招, 3=社招；job_type_filter 决定抓哪种，默认校招
        want_type = cfg.get("job_type_filter", "2")
        label = cfg.get("job_nature", "校招")
        picked = []
        page = 1
        total_page = None
        while True:
            body = {"page": {"pageNo": page, "pageSize": 20}, "keywords": ""}
            r = self.session.post(url, json=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            d = data.get("data") or {}
            items = d.get("list") or []
            if not items:
                break
            picked.extend(it for it in items if it.get("jobType") == want_type)
            page_info = d.get("page") or {}
            total_page = page_info.get("totalPage") or total_page
            if total_page and page >= total_page:
                break
            page += 1
            if page > max_pages:
                break
            time.sleep(0.15)  # 页数多，控制请求频率
        jobs = [self._parse(it) for it in picked]
        for j in jobs:
            j.recruit_type = label
        return jobs

    def _parse(self, it):
        job_id = str(it.get("jobUnionId") or "")
        cities = it.get("cityList") or []
        location = "、".join(
            c.get("name") or "" for c in cities if isinstance(c, dict))
        pub = ""
        ts = it.get("refreshTime") or it.get("firstPostTime")
        if ts:
            try:
                pub = datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d")
            except Exception:
                pub = ""
        return JobItem(
            company=self.name,
            job_id=job_id,
            title=(it.get("name") or "").strip(),
            category=it.get("jobFamily") or "",
            location=location,
            url=(f"https://zhaopin.meituan.com/web/position/detail"
                 f"?jobUnionId={job_id}&highlightType=campus"),
            publish_time=pub,
            tags=it.get("jobFamilyGroup") or "",
        )


class MeituanSocialScraper(MeituanScraper):
    """美团社招（jobType=3），复用 MeituanScraper 全部逻辑，只改 name"""
    name = "美团(社招)"
