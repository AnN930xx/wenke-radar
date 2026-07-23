"""伊利集团校招抓取器（百库 hotjob.cn 旧版接口）
伊利用的是百库旧版（/wt/ 路径的 Struts 站），与欧莱雅的新版 wecruit 接口不同：
  1. GET 岗位列表页，从页面 JS 里提取动态 operational 令牌
  2. GET {host}/wt/yili/web/json/position/list?operational=...&brandCode=1
         &recruitType=1&keyWord=&page=N   （recruitType=1 校招）
  3. 按 pageCount 翻页，postList 里是岗位数组
令牌每次页面生成都会变，必须先拉页面再调接口，不能写死。
详情页无稳定直链（postIdToken 也是动态的），日报统一链接到校招列表页。
"""
import re
from .base import BaseScraper, JobItem, guess_category
import config


class YiliScraper(BaseScraper):
    name = "伊利"

    # {rt} 处填 recruitType：1=校招 2=社招
    LIST_PAGE_TPL = ("/wt/yili/web/templet1000/index/"
                     "corpwebPosition1000yili!gotoPostListForAjax"
                     "?positionType=&brandCode=1&recruitType={rt}&showComp=true&comPart=")

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        host = cfg.get("host", "https://yili.hotjob.cn").rstrip("/")
        brand_code = cfg.get("brand_code", 1)
        recruit_type = cfg.get("recruit_type", 1)  # 1=校招 2=社招
        list_page = self.LIST_PAGE_TPL.format(rt=recruit_type)

        # 第一步：拉列表页提取 operational 动态令牌
        page_r = self.session.get(host + list_page,
                                  timeout=config.REQUEST_TIMEOUT)
        m = re.search(r"json/position/list\?operational=([0-9a-f]+)", page_r.text)
        if not m:
            raise RuntimeError("伊利页面未找到 operational 令牌（页面结构可能变了）")
        operational = m.group(1)

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": host + list_page,
        }
        all_items = []
        page = 1
        while True:
            url = (f"{host}/wt/yili/web/json/position/list"
                   f"?operational={operational}&brandCode={brand_code}"
                   f"&recruitType={recruit_type}&keyWord=&page={page}")
            r = self.session.get(url, headers=headers,
                                 timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            items = data.get("postList") or []
            if not items:
                break
            all_items.extend(items)
            page_count = data.get("pageCount") or 0
            if page_count and page >= page_count:
                break
            page += 1
            if page > 100:  # 社招约91页；按 pageCount 正常提前结束，这是防死循环兜底
                break
        label = cfg.get("job_nature", "校招")
        jobs = [self._parse(it, host) for it in all_items]
        for j in jobs:
            j.recruit_type = label
        return jobs

    def _parse(self, it, host):
        title = (it.get("postName") or "").strip()
        cat = it.get("postType") or ""
        if not isinstance(cat, str):
            cat = ""
        if not any(kw in cat for kw in config.CATEGORY_KEYWORDS):
            guessed = guess_category(title)
            cat = f"{cat}、{guessed}".strip("、") if guessed else cat
        tags = it.get("orgName") or it.get("deptOrgName") or ""
        salary = it.get("workingTreatment") or ""
        if salary:
            tags = f"{tags}、{salary}".strip("、")
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        landing = "social" if cfg.get("recruit_type", 1) == 2 else "campus"
        return JobItem(
            company=self.name,
            job_id=str(it.get("postId") or title),
            title=title,
            category=cat,
            location=it.get("workPlace") or "",
            url=f"{host}/wt/yili/web/index/{landing}",
            publish_time=(it.get("publishDate") or "")[:10],
            tags=tags,
        )


class YiliSocialScraper(YiliScraper):
    """伊利社招（百库旧版 recruitType=2）"""
    name = "伊利(社招)"
