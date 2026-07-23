"""网易校园招聘抓取器
先请求导航接口自动发现所有在招校招项目（互联网/互娱/雷火等），
再逐项目抓取岗位列表。新的校招季开启后无需改代码即可自动覆盖。

接口:
  GET https://campus.163.com/api/campuspc/project/navigation/list
  GET https://{domain}/api/campuspc/position/getJobList?pageSize=&currentPage=&projectId=
"""
import re
from .base import BaseScraper, JobItem
import config

PROJECT_RE = re.compile(
    r"https://(campus(?:\.game)?\.163\.com)/app/job/position\?id=(\d+)")


class NeteaseScraper(BaseScraper):
    name = "网易"

    def fetch(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        exclude = cfg.get("exclude_projects") or []
        projects = self._discover_projects(exclude)
        all_jobs = []
        for domain, project_id, project_name in projects:
            try:
                all_jobs.extend(self._fetch_project(domain, project_id, project_name))
            except Exception as e:
                print(f"  [网易] 项目 {project_name}({project_id}) 抓取失败: {e}")
        return all_jobs

    def _discover_projects(self, exclude):
        url = "https://campus.163.com/api/campuspc/project/navigation/list"
        r = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
        data = r.json()
        projects = []
        seen = set()

        def walk(nodes):
            for node in nodes or []:
                link = node.get("link") or ""
                title = node.get("title") or ""
                m = PROJECT_RE.match(link)
                if m and not any(kw in title for kw in exclude):
                    key = (m.group(1), m.group(2))
                    if key not in seen:
                        seen.add(key)
                        projects.append((m.group(1), m.group(2), title))
                walk(node.get("children"))

        walk(data.get("data"))
        return projects

    def _fetch_project(self, domain, project_id, project_name):
        jobs = []
        page = 1
        while True:
            url = (f"https://{domain}/api/campuspc/position/getJobList"
                   f"?pageSize={config.PAGE_SIZE}&currentPage={page}&projectId={project_id}")
            r = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if data.get("code") != 200:
                break
            d = data.get("data") or {}
            items = d.get("list") or []
            if not items:
                break
            for it in items:
                jobs.append(self._parse(it, domain, project_id, project_name))
            total = d.get("total") or 0
            if total and len(jobs) >= total:
                break
            if len(items) < config.PAGE_SIZE:
                break
            page += 1
            if page > 30:
                break
        return jobs

    def _parse(self, it, domain, project_id, project_name):
        return JobItem(
            company=self.name,
            job_id=f"{project_id}-{it.get('id')}",
            title=(it.get("positionName") or "").strip(),
            category=it.get("positionTypeName") or "",
            location=it.get("workPlaceName") or "",
            # 官网详情页无稳定直链，链接到对应项目的岗位列表页
            url=f"https://{domain}/app/job/position?id={project_id}",
            publish_time="",
            tags=project_name,
        )
