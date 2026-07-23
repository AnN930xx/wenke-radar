"""猎聘公司页抓取器（服务端渲染 HTML，用 bs4 解析）

有些家人特别想去的公司（宽创国际、凯谛思）没有官方招聘 API，只在猎聘招人。
猎聘 PC 站反爬重，但**手机版公司职位页**是服务端渲染的，job-card 直接在 HTML 里：
  GET https://m.liepin.com/company-jobs/{company_id}/   （带 iPhone UA）
  每个 <a class="job-card" data-jobid=..> 里含 标题/薪资/城市/经验/学历/日期/详情链接。

猎聘岗位基本都是社招 → 统一 recruit_type=社招（走每日新增），按经验标签剔资深岗。

接新的猎聘公司：加子类设 company_id（公司页 URL 里的数字），注册 + config 即可。
注意：猎聘对数据中心 IP 可能反爬，云端（GitHub Actions）若抓到 0/被拦属已知风险。
"""
import time
from bs4 import BeautifulSoup
from .base import BaseScraper, JobItem, guess_category
import config

_IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1")


class LiepinCompanyScraper(BaseScraper):
    """猎聘公司页通用抓取器，子类设 company_id。"""
    name = ""
    company_id = ""

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        cid = cfg.get("company_id", self.company_id)
        url = f"https://m.liepin.com/company-jobs/{cid}/"
        headers = {
            "User-Agent": _IPHONE_UA,
            "Referer": f"https://m.liepin.com/company/{cid}/",
            "Accept": "text/html,application/xhtml+xml",
        }
        # 猎聘反爬不稳定：短时高频会只返回少量"热招"卡。重试几次取最多的一次。
        best = []
        for attempt in range(3):
            r = self.session.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            cards = BeautifulSoup(r.text, "html.parser").select("a.job-card")
            if len(cards) > len(best):
                best = cards
            # 拿到较全（>5）就够了；否则缓一下重试
            if len(best) > 5:
                break
            time.sleep(2)
        cards = best
        jobs = []
        for c in cards:
            j = self._parse(c)
            if j is None:
                continue
            jobs.append(j)
        for j in jobs:
            j.recruit_type = "社招"
        return jobs

    def _parse(self, card):
        job_id = card.get("data-jobid") or ""
        title_el = card.select_one(".job-title .ellipsis") or card.select_one(".job-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        salary_el = card.select_one("h3 small") or card.select_one("small")
        salary = salary_el.get_text(strip=True) if salary_el else ""
        labels = [l.get_text(strip=True) for l in card.select(".job-card-labels label")]
        location = labels[0] if labels else ""
        experience = labels[1] if len(labels) > 1 else ""  # 如 "1年以上" / "3年以上" / "经验不限"
        date_el = card.select_one(".job-card-date")
        pub = date_el.get_text(strip=True) if date_el else ""
        href = card.get("href") or ""
        tags = "、".join([t for t in [salary, experience] if t and t != "经验不限"])
        return JobItem(
            company=self.name,
            job_id=str(job_id or title),
            title=title,
            category=guess_category(title),
            location=location,
            url=href,
            # 经验标签带回正文（"3年以上"→"3年以上经验"），判断在 enrich/filters 层
            description=f"{experience}经验" if experience and experience != "经验不限" else "",
            publish_time=pub,
            tags=tags,
        )


class KuanChuangScraper(LiepinCompanyScraper):
    """宽创国际（博物馆展陈/文物IP/策展——家人策展方向靶心）"""
    name = "宽创国际"
    company_id = "9584536"


class ArcadisScraper(LiepinCompanyScraper):
    """凯谛思 Arcadis（文化遗产/考古外企）"""
    name = "凯谛思"
    company_id = "10054189"
