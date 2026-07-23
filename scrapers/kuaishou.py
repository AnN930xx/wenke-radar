"""快手校招抓取器
接口: POST https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple
按 recruitSubProjectCodes（校招项目代码，config 里配）拉岗位；
职位类别是编码，需先调 dictionary/batch 接口拿 code→中文名 映射。
"""
from .base import BaseScraper, JobItem, guess_category, ms_to_date
import config

_DICT_API = ("https://campus.kuaishou.cn/recruit/campus/e/api/v1/dictionary/batch"
             "?types=workLocation,positionCategory,positionCategoryFlatten,positionNature")
_LIST_API = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"


class KuaishouScraper(BaseScraper):
    name = "快手"

    HEADERS = {
        "Content-Type": "application/json",
        "Referer": "https://campus.kuaishou.cn/recruit/campus/e/",
    }
    MAX_PAGES = 20

    def fetch(self):
        categories = self._load_category_dict()
        project_codes = config.COMPANY_CONFIG["快手"]["recruit_sub_project_codes"]
        raw = []
        page = 1
        while page <= self.MAX_PAGES:
            r = self.session.post(
                _LIST_API,
                json={"recruitSubProjectCodes": project_codes,
                      "pageSize": config.PAGE_SIZE, "pageNum": page},
                headers=self.HEADERS, timeout=config.REQUEST_TIMEOUT)
            data = r.json()
            if data.get("code") != 0:
                break
            result = data.get("result") or {}
            batch = result.get("list") or []
            if not batch:
                break
            raw.extend(batch)
            self.reported_total = result.get("total") or None
            if len(raw) >= (result.get("total") or 0):
                break
            page += 1
        return [self._parse(it, categories) for it in raw]

    def _load_category_dict(self):
        """positionCategory(Flatten) 两张字典合并成 code→中文名"""
        mapping = {}
        try:
            result = self.session.get(_DICT_API, timeout=config.REQUEST_TIMEOUT).json().get("result") or {}
            for dict_name in ("positionCategory", "positionCategoryFlatten"):
                for entry in result.get(dict_name) or []:
                    mapping[entry.get("code")] = entry.get("name")
        except Exception:
            pass
        return mapping

    def _parse(self, it, categories):
        title = (it.get("name") or "").strip()
        # simple 接口经常不带地点，能取到什么算什么
        cities = it.get("workLocationNameList") or it.get("workLocationNames") or []
        if not cities and it.get("workLocationCode"):
            cities = [it["workLocationCode"]]
        # 类别编码查字典，查不到从标题猜
        code = it.get("positionClassCode") or it.get("positionCategoryCode")
        category = categories.get(code) or guess_category(title)

        marks = []
        if "快Star" in title:
            marks.append("快Star")
        nature = it.get("positionNatureCode")
        if nature == "fulltime":
            marks.append("全职")
        elif nature in ("intern", "internship"):
            marks.append("实习")

        return JobItem(
            company=self.name,
            job_id=str(it.get("id") or it.get("code")),
            title=title,
            category=category,
            location="、".join(cities) if isinstance(cities, list) else str(cities),
            url="https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs?recruitSubProjectCodes=20271779425607",
            publish_time=ms_to_date(it.get("publishTime")),
            tags="/".join(marks),
        )
