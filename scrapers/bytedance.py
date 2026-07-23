"""字节跳动 / 小米 / 元气森林 等 校招+社招抓取器（飞书 ATS 招聘系统）
接口: POST {host}/api/v1/search/job/posts
需要先 POST {host}/api/v1/csrf/token 拿 atsx-csrf-token Cookie，再带 x-csrf-token 头请求。
站点区分靠 website-path 头 + portal_type：
  - 字节/小米校招: website-path=campus, portal_type=3
  - 字节社招:      不带 website-path, portal_type=2（带 campus 返回校招!）
  - jobs.feishu.cn 多租户(元气森林): website-path=站点路径(如 352020)，否则报 site not exist

小米/元气森林用同一套飞书 ATS（host 不同），复用本抓取器，见下方子类。
"""
from urllib.parse import unquote, urlparse
from .base import BaseScraper, JobItem
import config


class FeishuAtsScraper(BaseScraper):
    """飞书 ATS 通用抓取器，子类通过 host/website_path 等类属性指定站点"""
    name = ""
    host = ""
    website_path = "campus"          # website-path 头；None=不带（字节社招）
    portal_channel = "campus"        # portal-channel 头；None=不带
    referer_path = "campus/position"
    detail_path = "campus/position/{job_id}/detail"

    def fetch(self):
        host = self.host.rstrip("/")
        domain = urlparse(host).netloc
        # 第一步：获取 CSRF token
        self.session.post(f"{host}/api/v1/csrf/token", timeout=config.REQUEST_TIMEOUT)
        raw = self.session.cookies.get("atsx-csrf-token", domain=f".{domain}") \
            or self.session.cookies.get("atsx-csrf-token")
        if not raw:
            raise RuntimeError(f"未拿到 atsx-csrf-token（{domain}）")
        token = unquote(raw)

        url = f"{host}/api/v1/search/job/posts"
        headers = {
            "Content-Type": "application/json",
            "x-csrf-token": token,
            "portal-platform": "pc",
            "Referer": f"{host}/{self.referer_path}",
            "Origin": host,
        }
        if self.website_path:
            headers["website-path"] = self.website_path
        if self.portal_channel:
            headers["portal-channel"] = self.portal_channel
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        all_items = []
        offset = 0
        limit = 100
        while True:
            body = {
                "keyword": "",
                "limit": limit,
                "offset": offset,
                # 社招源按职类过滤（产品/运营/市场），否则全量上万条抓不动
                "job_category_id_list": cfg.get("job_category_ids", []),
                "tag_id_list": [],
                "location_code_list": [],
                "subject_id_list": [],
                "recruitment_id_list": [],
                "portal_type": cfg.get("portal_type", 3),
                "job_function_id_list": [],
                "portal_entrance": 1,
            }
            r = self.session.post(url, json=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if data.get("code") != 0:
                break
            d = data.get("data") or {}
            items = d.get("job_post_list") or []
            if not items:
                break
            all_items.extend(items)
            total = d.get("count") or 0
            self.reported_total = total or None
            if total and len(all_items) >= total:
                break
            if len(items) < limit:
                break
            offset += limit
            if offset > 8000:
                break
        self.raw_fetched = len(all_items)
        label = cfg.get("job_nature", "校招")
        jobs = []
        for it in all_items:
            j = self._parse(it)
            j.recruit_type = label
            if label == "社招":
                # 抓取层只负责带回 JD 正文；经验年限判断在 enrich/filters 层做
                j.description = f"{it.get('requirement') or ''}\n{it.get('description') or ''}"
            jobs.append(j)
        return jobs

    def _parse(self, it):
        job_id = str(it.get("id") or "")
        cities = it.get("city_list") or []
        city = "、".join(c.get("name") or "" for c in cities if isinstance(c, dict))
        if not city:
            city_info = it.get("city_info") or {}
            if isinstance(city_info, dict):
                city = city_info.get("name") or ""
        cat = ""
        cat_info = it.get("job_category") or {}
        if isinstance(cat_info, dict):
            cat = cat_info.get("name") or ""
            parent = cat_info.get("parent")
            if isinstance(parent, dict) and parent.get("name"):
                cat = f"{parent['name']}、{cat}"
        pub = ""
        ts = it.get("publish_time")
        if ts:
            from datetime import datetime
            try:
                pub = datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d")
            except Exception:
                pub = ""
        tags = ""
        subject = it.get("job_subject") or {}
        if isinstance(subject, dict):
            name = subject.get("name")
            if isinstance(name, dict):
                tags = name.get("zh_cn") or name.get("i18n") or ""
            elif isinstance(name, str):
                tags = name
        # recruit_type 子级（应届/实习）也放进标签
        rt = it.get("recruit_type") or {}
        if isinstance(rt, dict) and rt.get("name"):
            tags = f"{tags}、{rt['name']}" if tags else rt["name"]
        return JobItem(
            company=self.name,
            job_id=job_id,
            title=(it.get("title") or "").strip(),
            category=cat,
            location=city,
            url=f"{self.host.rstrip('/')}/{self.detail_path.format(job_id=job_id)}",
            publish_time=pub,
            tags=tags,
        )


class BytedanceScraper(FeishuAtsScraper):
    name = "字节跳动"
    host = "https://jobs.bytedance.com"


class XiaomiScraper(FeishuAtsScraper):
    name = "小米"
    host = "https://xiaomi.jobs.f.mioffice.cn"


class GenkiForestScraper(FeishuAtsScraper):
    """元气森林（jobs.feishu.cn 多租户站，站点路径 352020）"""
    name = "元气森林"
    host = "https://k11pnjpvz1.jobs.feishu.cn"
    website_path = "352020"
    portal_channel = None
    referer_path = "352020/position"
    detail_path = "352020/position/{job_id}/detail"


class BytedanceSocialScraper(FeishuAtsScraper):
    """字节跳动社招（不带 website-path 头 + portal_type=2；按职类过滤）"""
    name = "字节跳动(社招)"
    host = "https://jobs.bytedance.com"
    website_path = None
    portal_channel = None
    referer_path = "experienced/position"
    detail_path = "experienced/position/{job_id}/detail"


class XiaomiSocialScraper(FeishuAtsScraper):
    """小米社招（飞书 ATS，同字节社招套路：不带 website-path + portal_type=2）"""
    name = "小米(社招)"
    host = "https://xiaomi.jobs.f.mioffice.cn"
    website_path = None
    portal_channel = None
    referer_path = "experienced/position"
    detail_path = "experienced/position/{job_id}/detail"
