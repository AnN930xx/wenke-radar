"""北森(zhiye.com)招聘平台通用抓取器
很多消费/文化类公司（泡泡玛特、名创优品等）的校招官网都由北森搭建，
域名形如 https://{company}.zhiye.com，接口统一：
  POST {host}/api/Jobad/GetJobAdPageList
  body: {"pageIndex": N, "pageSize": M, "keyWord": "", "category": 2, "langType": "zh_CN"}
  category: 2=校园招聘, 1=社会招聘
详情页: {host}/job/detail?jobAdId={Id}

要接入新的北森公司，在 config.ENABLED_COMPANIES 加开关、COMPANY_CONFIG 里
配 host 即可（参照"泡泡玛特"），然后在 scrapers/__init__.py 注册一个子类。
"""
from .base import BaseScraper, JobItem, guess_category
import config


class BeisenScraper(BaseScraper):
    """按 config.COMPANY_CONFIG[name] 里的 host/category 抓取北森站点"""
    name = ""  # 子类指定

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        host = cfg["host"].rstrip("/")
        category = cfg.get("category", 2)
        url = f"{host}/api/Jobad/GetJobAdPageList"
        headers = {
            "Content-Type": "application/json",
            "Origin": host,
            "Referer": f"{host}/campus/jobs",
        }
        # 部分北森租户会拒绝较大的 pageSize（返回空 Data），且每页实际返回条数
        # 不稳定，因此用较小的 pageSize，并只按 Count 判断是否抓完（不能用
        # len(items)<pageSize 判断结束，否则会提前退出漏抓）
        page_size = cfg.get("page_size", 10)
        all_items = []
        page = 1
        while True:
            body = {
                "pageIndex": page,
                "pageSize": page_size,
                "keyWord": "",
                "category": category,
                "langType": "zh_CN",
            }
            r = self.session.post(url, json=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if data.get("Code") != 200:
                break
            items = data.get("Data") or []
            if not items:
                break
            all_items.extend(items)
            total = data.get("Count") or data.get("Total") or 0
            self.reported_total = total or None
            if total and len(all_items) >= total:
                break
            page += 1
            if page > 100:
                break
        label = cfg.get("job_nature", "校招")
        jobs = [self._parse(it, host) for it in all_items]
        for j in jobs:
            j.recruit_type = label
        return jobs

    def _parse(self, it, host):
        title = (it.get("JobAdName") or "").strip()
        guid = it.get("Id") or ""
        # 地点字段在不同租户配置下命名不一，逐个尝试
        location = ""
        for key in ("LocationName", "LocName", "WorkPlace", "WorkCity", "Location"):
            v = it.get(key)
            if v and isinstance(v, str):
                location = v
                break
        pub = ""
        pd = it.get("PostDate") or ""
        if pd and not pd.startswith("0001"):
            pub = pd[:10]
        return JobItem(
            company=self.name,
            job_id=str(it.get("JobAdId") or guid),
            title=title,
            category=guess_category(title),
            location=location,
            url=f"{host}/job/detail?jobAdId={guid}" if guid else f"{host}/campus/jobs",
            publish_time=pub,
            tags="",
        )


class PopmartScraper(BeisenScraper):
    name = "泡泡玛特"


class MinisoScraper(BeisenScraper):
    name = "名创优品"


class PopmartSocialScraper(BeisenScraper):
    name = "泡泡玛特(社招)"


class MinisoSocialScraper(BeisenScraper):
    name = "名创优品(社招)"


class MengniuScraper(BeisenScraper):
    name = "蒙牛"


class MengniuSocialScraper(BeisenScraper):
    name = "蒙牛(社招)"


# ---------- 批次26 扩源：快消/零售第三批（北森租户，host 见 config）----------
class PolyDevScraper(BeisenScraper):
    name = "保利发展"          # 校招：策划管培/运营管理/企业管理（对口运营/增长营销）


class TsingtaoScraper(BeisenScraper):
    name = "青岛啤酒"          # 校招：菁英计划（销售/国贸/职能）


class TsingtaoSocialScraper(BeisenScraper):
    name = "青岛啤酒(社招)"     # 社招：数字化/推广/业务代表


class HeyteaSocialScraper(BeisenScraper):
    name = "喜茶(社招)"        # 社招大户（4千+，含产品策划/品牌/设计）


class VindaSocialScraper(BeisenScraper):
    name = "维达(社招)"        # 社招：数字营销/数据分析


class UniPresidentSocialScraper(BeisenScraper):
    name = "统一(社招)"        # 社招大户（8百+，含推广/经销/市场）
