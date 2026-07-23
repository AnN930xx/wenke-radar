"""百库(hotjob.cn)招聘平台通用抓取器
很多消费/国企的校招官网由百库搭建，域名形如 https://{company}.hotjob.cn，
每个租户有一个 SU 站点ID。接口平台通用：
  POST {host}/wecruit/positionInfo/listPosition/{SU}?iSaJAx=isAjax&request_locale=zh_CN
  form: isFrompb=true&recruitType=1&pageSize=&currentPage=   (recruitType=1 校招)
详情页: {host}/{SU}/pb/position.html?id={postId}

注意：租户在两季招聘之间会「关闭官网」，此时 config 接口返回"该官网已关闭"，
本抓取器会优雅返回空列表（不报错），官网重开后自动恢复抓取。

接入新的百库公司：在 config 配 host+su，然后在 __init__.py 注册子类（参照 LorealScraper）。
"""
from datetime import datetime
from .base import BaseScraper, JobItem, guess_category
import config


class BaikuScraper(BaseScraper):
    """百库通用抓取器，子类通过 config.COMPANY_CONFIG[name] 的 host/su 指定站点"""
    name = ""

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        host = cfg["host"].rstrip("/")
        su = cfg["su"]
        recruit_type = cfg.get("recruit_type", 1)  # 1=校招
        url = (f"{host}/wecruit/positionInfo/listPosition/{su}"
               f"?iSaJAx=isAjax&request_locale=zh_CN")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{host}/{su}/pb/school.html",
            "Origin": host,
        }
        all_items = []
        page = 1
        # 注意：百库服务端把每页硬限制在 12 条左右（忽略较大的 pageSize），
        # 所以翻页只依据 totalPage / dataCount，不能用 len(items)<pageSize 判断结束
        while True:
            body = (f"isFrompb=true&recruitType={recruit_type}"
                    f"&pageSize=50&currentPage={page}")
            r = self.session.post(url, data=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            try:
                data = r.json()
            except Exception:
                break  # 官网关闭时返回非 JSON
            if data.get("state") != "200":
                break  # 官网已关闭或异常
            pf = (data.get("data") or {}).get("pageForm") or {}
            items = pf.get("pageData") or []
            if not items:
                break
            all_items.extend(items)
            total = pf.get("dataCount") or 0
            self.reported_total = total or None
            total_page = pf.get("totalPage") or 0
            if total and len(all_items) >= total:
                break
            if total_page and page >= total_page:
                break
            page += 1
            if page > 100:  # 每页约12条，100页≈1200岗封顶
                break
        label = cfg.get("job_nature", "校招")
        jobs = [self._parse(it, host, su) for it in all_items]
        for j in jobs:
            j.recruit_type = label
        return jobs

    def _parse(self, it, host, su):
        post_id = str(it.get("postId") or "")
        title = (it.get("postName") or "").strip()
        cat = it.get("postTypeName") or ""
        if not any(kw in cat for kw in config.CATEGORY_KEYWORDS):
            guessed = guess_category(title)
            cat = f"{cat}、{guessed}".strip("、") if guessed else cat
        pub = (it.get("publishDate") or "")[:10]
        tags = it.get("projectName") or ""
        return JobItem(
            company=self.name,
            job_id=post_id or it.get("postCode") or title,
            title=title,
            category=cat,
            location=it.get("workPlaceStr") or "",
            url=f"{host}/{su}/pb/position.html?id={post_id}",
            publish_time=pub,
            tags=tags,
        )


class LorealScraper(BaikuScraper):
    name = "欧莱雅"
