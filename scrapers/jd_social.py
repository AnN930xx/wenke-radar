"""京东社招抓取器（zhaopin.jd.com 老 JSP 站）
校招是 campus.jd.com（另一套），社招是 zhaopin.jd.com：
  POST https://zhaopin.jd.com/web/job/job_list
  **form 编码**（不是 JSON！传 JSON 会被忽略、永远返回默认10条）：
    pageIndex=N&pageSize=20&workCityJson=[]&jobTypeJson=[]&jobSearch=&depTypeJson=[]
  返回 JSON 数组，含 positionNameOpen(展示名)/jobType(运营类等)/workCity/qualification(JD正文)
  翻页 pageIndex 递增到空为止。详情页需登录，无公开直链 → 用列表页兜底。
"""
from datetime import datetime
from .base import BaseScraper, JobItem, guess_category
import config


class JdSocialScraper(BaseScraper):
    name = "京东(社招)"
    LIST_PAGE = "https://zhaopin.jd.com/web/job/job_info_list/3"
    API = "https://zhaopin.jd.com/web/job/job_list"

    def _fetch_items(self):
        # 先访问列表页拿 jsessionid
        self.session.get(self.LIST_PAGE, timeout=config.REQUEST_TIMEOUT)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.LIST_PAGE,
            "Origin": "https://zhaopin.jd.com",
        }
        seen = {}
        page = 1
        page_size = 20
        empty_streak = 0
        while True:
            body = (f"pageIndex={page}&pageSize={page_size}"
                    f"&workCityJson=%5B%5D&jobTypeJson=%5B%5D&jobSearch=&depTypeJson=%5B%5D")
            r = self.session.post(self.API, data=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            try:
                items = r.json()
            except ValueError:
                break
            if not isinstance(items, list) or not items:
                break
            fresh = 0
            for it in items:
                pid = str(it.get("positionId") or it.get("id") or "")
                if not pid or pid in seen:
                    continue
                j = self._parse(it, pid)
                # 抓取层只带回 JD 正文；经验年限判断在 enrich/filters 层做
                j.description = f"{it.get('qualification') or ''}\n{it.get('workContent') or ''}"
                seen[pid] = j
                fresh += 1
            empty_streak = empty_streak + 1 if fresh == 0 else 0
            if empty_streak >= 2:
                break
            page += 1
            if page > 100:  # 每页20，2000岗封顶
                break
        jobs = list(seen.values())
        for j in jobs:
            j.recruit_type = "社招"
        return jobs

    def _parse(self, it, pid):
        title = (it.get("positionNameOpen") or it.get("positionName") or "").strip()
        cat = it.get("jobType") or guess_category(title)
        pub = it.get("formatPublishTime") or ""
        if not pub and it.get("publishTime"):
            try:
                pub = datetime.fromtimestamp(it["publishTime"] / 1000).strftime("%Y-%m-%d")
            except Exception:
                pub = ""
        return JobItem(
            company=self.name,
            job_id=pid,
            title=title,
            category=cat,
            location=it.get("workCity") or "",
            url=self.LIST_PAGE,   # 详情页需登录，用列表页兜底
            publish_time=pub,
            tags=it.get("positionDeptName") or "",
        )
