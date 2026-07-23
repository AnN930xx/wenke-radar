"""UCCA当代艺术中心 招聘抓取器（含策展/展览类岗位与实习）
页面: https://ucca.org.cn/careers/ —— 静态 HTML 表格，直接解析。
表格列: 岗位名称 | 部门 | 工作地点 | 招聘人数 | 岗位编号 | 发布时间
"""
import re
from html import unescape
from .base import BaseScraper, JobItem
import config

ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
LINK_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


class UccaScraper(BaseScraper):
    name = "UCCA"

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        url = cfg.get("url", "https://ucca.org.cn/careers/")
        r = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
        r.encoding = "utf-8"
        html = r.text
        jobs = []
        for row_html in ROW_RE.findall(html):
            cells = CELL_RE.findall(row_html)
            if len(cells) < 6:
                continue  # 表头或其他行
            title_cell = cells[0]
            m = LINK_RE.search(title_cell)
            if m:
                href, title = m.group(1), m.group(2)
            else:
                href, title = "", title_cell
            title = unescape(TAG_RE.sub("", title)).strip()
            dept = unescape(TAG_RE.sub("", cells[1])).strip()
            location = unescape(TAG_RE.sub("", cells[2])).strip()
            job_no = unescape(TAG_RE.sub("", cells[4])).strip()
            pub = unescape(TAG_RE.sub("", cells[5])).strip().replace(".", "-")
            if not title:
                continue
            full_url = href if href.startswith("http") else f"https://ucca.org.cn{href}"
            jobs.append(JobItem(
                company=self.name,
                job_id=job_no or f"{title}-{location}",
                title=title,
                category=self._category(title, dept),
                location=location,
                url=full_url,
                publish_time=pub,
                tags=dept,
            ))
        return jobs

    def _category(self, title, dept):
        text = f"{title} {dept}"
        if any(kw in text for kw in ("策展", "展览", "布展", "展陈")):
            return "策展"
        if "实习" in title:
            return "策展、实习"  # 美术馆实习统一归入策展方向便于命中
        return "策展"  # UCCA 全部岗位默认归入策展方向
