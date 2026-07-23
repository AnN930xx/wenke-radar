"""百度校园招聘抓取器
接口: POST https://talent.baidu.com/httservice/getPostListNew
      form: recruitType=GRADUATE&pageSize=&curPage=&keyWord=
      需要先 GET 页面拿 Cookie，并带 Referer。
"""
from .base import BaseScraper, JobItem, guess_category
import config

HOST = "https://talent.baidu.com"


class BaiduScraper(BaseScraper):
    name = "百度"

    def _fetch_items(self):
        # 先访问列表页拿 Cookie（否则接口返回 no-auth）
        self.session.get(f"{HOST}/jobs/list",
                         headers={"Referer": HOST}, timeout=config.REQUEST_TIMEOUT)
        url = f"{HOST}/httservice/getPostListNew"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{HOST}/jobs/list",
            "Origin": HOST,
        }
        all_items = []
        page = 1
        page_size = 20  # 百度接口 pageSize 上限约 20，超过报 Illegal argument
        while True:
            body = {
                "recruitType": "GRADUATE",  # 应届校招
                "pageSize": page_size,
                "curPage": page,
                "keyWord": "",
            }
            r = self.session.post(url, data=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if data.get("status") != "ok":
                break
            d = data.get("data") or {}
            items = d.get("list") or []
            if not items:
                break
            all_items.extend(items)
            total = int(d.get("total") or 0)
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
        job_id = str(it.get("postId") or it.get("jobId") or "")
        title = (it.get("name") or "").strip()
        cat = it.get("postType") or ""
        if not any(kw in cat for kw in config.CATEGORY_KEYWORDS):
            cat = f"{cat}、{guess_category(title)}".strip("、")
        return JobItem(
            company=self.name,
            job_id=job_id,
            title=title,
            category=cat,
            location="",  # 列表接口不返回地点，详情才有
            url=f"{HOST}/jobs/detail?jobId={it.get('jobId', '')}",
            publish_time=it.get("publishDate") or "",
            tags=it.get("orgName") or "",
        )
