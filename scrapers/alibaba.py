"""阿里巴巴集团校园招聘抓取器
站点: https://campus-talent.alibaba.com （淘天等业务单独站点，这里抓集团主站）
接口:
  GET  /campus/position                       —— 页面里含 _csrf token
  POST /searchCondition/listBatch?_csrf=TOKEN —— 列出所有在招批次(应届/实习/研究型/日常)
  POST /position/search?_csrf=TOKEN           —— 按 batchId 分页查岗位
"""
import re
from .base import BaseScraper, JobItem
import config

CSRF_RE = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
HOST = "https://campus-talent.alibaba.com"


class AlibabaScraper(BaseScraper):
    name = "阿里巴巴"

    def fetch(self):
        # 1. 抓页面拿 _csrf token
        r = self.session.get(f"{HOST}/campus/position",
                             headers={"Referer": HOST}, timeout=config.REQUEST_TIMEOUT)
        m = CSRF_RE.search(r.text)
        if not m:
            raise RuntimeError("未从页面提取到 _csrf token")
        token = m.group(0)
        headers = {
            "Content-Type": "application/json",
            "Referer": f"{HOST}/campus/position",
            "Origin": HOST,
        }

        # 2. 列批次
        rb = self.session.post(f"{HOST}/searchCondition/listBatch?_csrf={token}",
                              json={"language": "zh"}, headers=headers,
                              timeout=config.REQUEST_TIMEOUT)
        content = (rb.json() or {}).get("content") or {}
        batches = []
        seen_batch = set()
        for group in content.values():
            if not isinstance(group, list):
                continue  # content 里还有 sequence 等非批次字段
            for b in group:
                if not isinstance(b, dict):
                    continue
                bid = b.get("id")
                if bid and bid not in seen_batch:
                    seen_batch.add(bid)
                    batches.append((bid, b.get("name") or ""))

        # 3. 逐批次翻页
        all_jobs = []
        for bid, bname in batches:
            all_jobs.extend(self._fetch_batch(token, headers, bid, bname))
        return all_jobs

    def _fetch_batch(self, token, headers, bid, bname):
        jobs = []
        page = 1
        while True:
            body = {
                "batchId": bid,
                "pageIndex": page,
                "pageSize": 20,
                "customDeptCode": "",
                "channel": "campus_group_official_site",
                "language": "zh",
            }
            r = self.session.post(f"{HOST}/position/search?_csrf={token}",
                                 json=body, headers=headers,
                                 timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if not data.get("success"):
                break
            content = data.get("content") or {}
            items = content.get("datas") or []
            if not items:
                break
            for it in items:
                jobs.append(self._parse(it, bid, bname))
            total = content.get("totalCount") or content.get("total") or 0
            if total and len(jobs) >= total:
                break
            if len(items) < 20:
                break
            page += 1
            if page > 40:
                break
        return jobs

    def _parse(self, it, bid, bname):
        job_id = str(it.get("id") or "")
        locs = it.get("workLocations") or []
        return JobItem(
            company=self.name,
            job_id=job_id,
            title=(it.get("name") or "").strip(),
            category=it.get("categories") or "",
            location="、".join(locs) if isinstance(locs, list) else str(locs),
            url=f"{HOST}/campus/position/detail?positionId={job_id}",
            publish_time="",
            tags=bname,
        )
