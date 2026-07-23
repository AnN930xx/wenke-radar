"""腾讯校园招聘 + 社招抓取器
校招接口: POST https://join.qq.com/api/v1/position/searchPosition
社招接口: GET https://careers.tencent.com/tencentcareer/api/post/Query
  公开 API，parentCategoryId 过滤方向：40003=产品 40004=营销与公关 40006=内容
说明: 校招官网详情页为 SPA 且不暴露稳定的岗位详情链接，日报里统一链接到岗位列表页；
     社招详情页 careers.tencent.com/jobdesc.html?postId= 是稳定直链。
"""
import time
from .base import BaseScraper, JobItem, guess_category
import config


class TencentScraper(BaseScraper):
    name = "腾讯"

    def _fetch_items(self):
        url = "https://join.qq.com/api/v1/position/searchPosition"
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://join.qq.com/post.html",
            "Origin": "https://join.qq.com",
        }
        all_items = []
        page = 1
        while True:
            body = {
                "pageIndex": page,
                "pageSize": config.PAGE_SIZE,
                "keyword": "",
                "workCountryType": 0,
            }
            r = self.session.post(url, json=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if data.get("status") != 0:
                break
            items = (data.get("data") or {}).get("positionList") or []
            if not items:
                break
            all_items.extend(items)
            total = (data.get("data") or {}).get("total") or 0
            self.reported_total = total or None
            if total and len(all_items) >= total:
                break
            if len(items) < body["pageSize"]:
                break
            page += 1
            if page > 30:
                break
        return [self._parse(it) for it in all_items]

    def _parse(self, it):
        title = (it.get("positionTitle") or "").strip()
        return JobItem(
            company=self.name,
            job_id=str(it.get("postId") or it.get("id") or title),
            title=title,
            category=guess_category(title),
            location=(it.get("workCities") or "").strip(),
            url="https://join.qq.com/post.html",
            publish_time="",
            tags=it.get("recruitLabelName") or it.get("projectName") or "",
        )


class TencentSocialScraper(BaseScraper):
    """腾讯社招（careers.tencent.com 公开接口，按父类目过滤方向）"""
    name = "腾讯(社招)"

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        # 40003=产品 40004=营销与公关 40006=内容（40001技术等不抓）
        parent_ids = cfg.get("parent_category_ids", [40003, 40004, 40006])
        base = "https://careers.tencent.com/tencentcareer/api/post/Query"
        headers = {"Referer": "https://careers.tencent.com/search.html"}
        seen = {}
        raw_count = 0        # 分页原始条数（含被资深过滤丢弃的），完整性对账用
        total_sum = 0        # 各父类目服务端总数之和
        for pid in parent_ids:
            page = 1
            while True:
                params = {
                    "timestamp": int(time.time() * 1000),
                    "parentCategoryId": pid,
                    "pageIndex": page,
                    "pageSize": 50,
                    "language": "zh-cn",
                    "area": "cn",
                }
                r = self.session.get(base, params=params, headers=headers,
                                     timeout=config.REQUEST_TIMEOUT)
                data = r.json()
                if data.get("Code") != 200:
                    break
                d = data.get("Data") or {}
                items = d.get("Posts") or []
                if not items:
                    break
                raw_count += len(items)
                if page == 1:
                    total_sum += d.get("Count") or 0
                for it in items:
                    jid = str(it.get("PostId") or it.get("RecruitPostId") or "")
                    if not jid or jid in seen:
                        continue
                    j = self._parse(it, jid)
                    # 结构化经验字段带回 description；判断在 enrich/filters 层做
                    if it.get("RequireWorkYearsName"):
                        j.description = f"{it['RequireWorkYearsName']}工作经验"
                    seen[jid] = j
                total = d.get("Count") or 0
                if page * 50 >= total:
                    break
                page += 1
                if page > 40:
                    break
        self.raw_fetched = raw_count
        self.reported_total = total_sum or None
        jobs = list(seen.values())
        for j in jobs:
            j.recruit_type = "社招"
        return jobs

    def _parse(self, it, jid):
        title = (it.get("RecruitPostName") or "").strip()
        cat = it.get("CategoryName") or guess_category(title)
        pub = (it.get("LastUpdateTime") or "")[:10]
        return JobItem(
            company=self.name,
            job_id=jid,
            title=title,
            category=cat,
            location=it.get("LocationName") or "",
            url=f"https://careers.tencent.com/jobdesc.html?postId={jid}",
            publish_time=pub,
            tags=it.get("BGName") or "",
        )
