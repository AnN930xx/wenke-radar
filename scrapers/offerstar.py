"""OfferStar 聚合平台抓取器（SSR 页面，bs4 解析表格）
官网源的补充：一张大表列出各公司校招公告（公司级信息，非具体岗位）。
按"产品/运营"两个方向词各查一次，结果去重合并。
"""
from urllib.parse import quote
from bs4 import BeautifulSoup
from .base import BaseScraper, JobItem
import config

# 表格列序（改版时对照官网更新）：
# 0=公司 1=标题 2=批次 3=更新时间 4=招聘岗位 5=工作地点 6=行业 7=招聘类型 8=截止时间 9=操作(投递链接)
_COL_COMPANY, _COL_TITLE, _COL_UPDATED, _COL_POSITIONS, _COL_CITY, _COL_ACTION = 0, 1, 3, 4, 5, 9


class OfferstarScraper(BaseScraper):
    name = "offerstar"

    SEARCH_URL = "https://www.offerstar.cn/recruitment"
    DIRECTIONS = ["产品", "运营"]

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG["offerstar"]
        collected, seen = [], set()
        for direction in self.DIRECTIONS:
            url = (f"{self.SEARCH_URL}?title={quote(cfg['title'])}"
                   f"&positions={quote(direction)}&channel={quote(cfg['channel'])}")
            try:
                html = self.session.get(url, timeout=config.REQUEST_TIMEOUT).text
            except Exception as e:
                print(f"  [offerstar] {direction} 方向请求失败: {e}")
                continue
            for job in self._parse_table(html):
                if job.job_id not in seen:
                    seen.add(job.job_id)
                    collected.append(job)
        return collected

    def _parse_table(self, html):
        table = BeautifulSoup(html, "html.parser").find("table")
        if not table:
            return []
        jobs = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) <= _COL_ACTION:
                continue
            text = lambda i: cells[i].get_text(strip=True)
            company, title = text(_COL_COMPANY), text(_COL_TITLE)
            anchor = cells[_COL_ACTION].find("a")
            jobs.append(JobItem(
                company=f"offerstar·{company}",
                job_id=f"{company}_{title}",   # 聚合页无稳定 id，用 公司_标题 合成
                title=title,
                category=self._hit_directions(text(_COL_POSITIONS) + title),
                location=text(_COL_CITY),
                url=anchor["href"] if anchor and anchor.get("href") else "",
                publish_time=text(_COL_UPDATED),
                tags="聚合",
            ))
        return jobs

    @staticmethod
    def _hit_directions(text):
        return "、".join(kw for kw in config.CATEGORY_KEYWORDS if kw in text)
