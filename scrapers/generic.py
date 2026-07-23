"""配置驱动的通用抓取器 —— 零代码接新源

在 config.py 的 GENERIC_SOURCES 里加一段声明即可接入一个新源，无需写代码。
支持两类源：
  - "api"  : JSON 接口（GET/POST），声明分页方式 + 字段映射
  - "html" : 服务端渲染页面，解析首个 <table>

完整配置示例见 config.py 的 GENERIC_SOURCES 注释。要点：
  - body_template 里的 "{page}" 占位符（或 pagination.page_key 指定的键）每页替换成页码
  - response.list_path / total_path 用点号路径定位（如 "data.list"）
  - fields 把接口字段名映射到 JobItem 字段；缺类别时自动从标题猜
  - detail_url_template 里的 {job_id} 替换成岗位 id，生成详情链接
"""
import json
from bs4 import BeautifulSoup
from .base import BaseScraper, JobItem, guess_category, ms_to_date
import config

_MAX_PAGES = 30


def dig(obj, path):
    """点号路径取嵌套值："data.list" / "result.0.jobs"。任何一步取不到返回 None"""
    if not path:
        return None
    node = obj
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
        if node is None:
            return None
    return node


class GenericScraper(BaseScraper):
    """由 GENERIC_SOURCES 配置项驱动，一个实例对应一个源"""

    def __init__(self, http_session, source_config):
        self.name = source_config["name"]
        self.cfg = source_config
        super().__init__(http_session)

    def _fetch_items(self):
        if self.cfg.get("type", "api") == "html":
            return self._fetch_html()
        return self._fetch_api()

    # ---------- JSON 接口 ----------

    def _fetch_api(self):
        paging = self.cfg.get("pagination", {})
        first_page = paging.get("page_start", 1)
        stop_rule = paging.get("stop_when", "less_than_size")
        page_size = self.cfg.get("page_size", config.PAGE_SIZE)
        resp_cfg = self.cfg.get("response", {})

        raw = []
        for page in range(first_page, first_page + _MAX_PAGES):
            data = self._request_page(page, paging.get("page_key", "page"))
            if data is None:
                break
            batch = dig(data, resp_cfg.get("list_path", "list"))
            if not isinstance(batch, list):
                batch = []
            raw.extend(batch)

            if not batch:
                break
            if stop_rule == "less_than_size" and len(batch) < page_size:
                break
            total = dig(data, resp_cfg.get("total_path")) if resp_cfg.get("total_path") else None
            if isinstance(total, (int, float)):
                self.reported_total = int(total) or None
                if len(raw) >= total:
                    break
        return [self._to_job(it) for it in raw]

    def _request_page(self, page, page_key):
        headers = dict(self.cfg.get("headers", {}))
        headers.setdefault("User-Agent", config.USER_AGENT)
        body = self._render_body(page, page_key)
        try:
            if self.cfg.get("method", "GET").upper() == "POST":
                r = self.session.post(self.cfg["url"], json=body, headers=headers,
                                      timeout=config.REQUEST_TIMEOUT)
            else:
                r = self.session.get(self.cfg["url"], params=body or {}, headers=headers,
                                     timeout=config.REQUEST_TIMEOUT)
            return r.json()
        except Exception as e:
            print(f"  [{self.name}] 第 {page} 页请求失败: {e}")
            return None

    def _render_body(self, page, page_key):
        """实例化请求体模板：先做 "{page}" 字符串替换，再把 page_key 键直接赋成整数页码"""
        template = self.cfg.get("body_template")
        if not template:
            return None
        body = json.loads(json.dumps(template).replace('"{page}"', str(page))
                          .replace("{page}", str(page)))
        if isinstance(body, dict) and page_key in body and not isinstance(body[page_key], int):
            body[page_key] = page
        return body

    def _to_job(self, it):
        fmap = self.cfg.get("fields", {})
        take = lambda field, default="": str(dig(it, fmap.get(field, default)) or "").strip()

        job_id = take("job_id", "id")
        title = take("title", "name")
        publish_time = take("publish_time")

        # 毫秒时间戳字段声明了就转日期
        ts_field = self.cfg.get("timestamp_field")
        if ts_field:
            ts = dig(it, ts_field)
            if isinstance(ts, (int, float)):
                publish_time = ms_to_date(ts)

        url = take("url")
        if not url and job_id:
            url = self.cfg.get("detail_url_template", "").replace("{job_id}", job_id)

        return JobItem(
            company=self.name,
            job_id=job_id,
            title=title,
            category=take("category") or guess_category(title),
            location=take("location"),
            url=url,
            publish_time=publish_time,
            tags=take("tags"),
        )

    # ---------- HTML 表格 ----------

    def _fetch_html(self):
        try:
            html = self.session.get(self.cfg["url"],
                                    headers={"User-Agent": config.USER_AGENT},
                                    timeout=config.REQUEST_TIMEOUT).text
        except Exception as e:
            print(f"  [{self.name}] 页面请求失败: {e}")
            return []
        table = BeautifulSoup(html, "html.parser").find("table")
        if not table:
            return []
        jobs = []
        for row in table.find_all("tr")[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            jobs.append(JobItem(
                company=self.name,
                job_id=cells[0],
                title=cells[1],
                category=guess_category(cells[1]),
                location=cells[2] if len(cells) > 2 else "",
                url="",
                tags="聚合",
            ))
        return jobs
