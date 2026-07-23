"""牛客网校招日程聚合抓取器
页面: https://www.nowcoder.com/school/schedule （公开，无需登录）
接口: POST https://www.nowcoder.com/np-api/u/school-schedule/list-card
      form: query=&propertyId=&page=N&pageSize=M&tab=T
      tab=1 全量档案(2万+含已结束) / tab=2、3 近期更新与即将截止的活跃子集

聚合的是"公司级"校招项目（某公司27届秋招/实习开始网申了），
和各官网的"岗位级"抓取互补。每天只抓活跃子集，新收录项目靠数据库对比识别。
"""
from datetime import datetime
from .base import BaseScraper, JobItem
import config


class NowcoderScraper(BaseScraper):
    name = "牛客日程"

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        tabs = cfg.get("tabs", [2, 3])
        url = "https://www.nowcoder.com/np-api/u/school-schedule/list-card"
        # 牛客有阿里云 WAF：需要浏览器指纹头 + 先访问页面拿 acw_tc Cookie，
        # 且不能声明 br 压缩（requests 无 brotli 解码器时会拿到乱码）
        waf_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": "https://www.nowcoder.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        self.session.get("https://www.nowcoder.com/school/schedule",
                         headers=waf_headers, timeout=config.REQUEST_TIMEOUT)
        headers = dict(waf_headers)
        headers["Referer"] = "https://www.nowcoder.com/school/schedule"
        seen = {}
        for tab in tabs:
            page = 1
            while True:
                body = {"query": "", "propertyId": "", "page": page,
                        "pageSize": 50, "tab": tab}
                r = self.session.post(url, data=body, headers=headers,
                                      timeout=config.REQUEST_TIMEOUT)
                data = r.json()
                if data.get("code") != 0:
                    break
                d = data.get("data") or {}
                items = d.get("datas") or []
                if not items:
                    break
                for it in items:
                    job = self._parse(it)
                    if job:
                        seen.setdefault(job.job_id, job)
                total_page = d.get("totalPage") or 1
                if page >= total_page:
                    break
                page += 1
                if page > 30:
                    break
        return list(seen.values())

    def _parse(self, it):
        name = (it.get("name") or "").strip()
        if not name:
            return None
        batch = it.get("batchName") or ""
        careers = it.get("careerNameList") or []
        # 申请链接优先级：自定义网申链接 > 信息来源 > 牛客日程页
        link = (it.get("customWangshenLink") or it.get("sourceInformation")
                or "https://www.nowcoder.com/school/schedule")
        deadline = ""
        ts = it.get("wangshenEndDate")
        if ts:
            try:
                deadline = datetime.fromtimestamp(int(ts) / 1000).strftime("%m-%d")
            except Exception:
                deadline = ""
        pub = ""
        uts = it.get("wangshenUpdateTime") or it.get("updateTime")
        if uts:
            try:
                pub = datetime.fromtimestamp(int(uts) / 1000).strftime("%Y-%m-%d")
            except Exception:
                pub = ""
        tags = batch
        if deadline:
            tags = f"{tags}、网申截止{deadline}" if tags else f"网申截止{deadline}"
        return JobItem(
            company=self.name,
            job_id=f"{it.get('companyId')}-{it.get('batch')}",
            title=f"{name} · {batch}" if batch else name,
            category="、".join(careers),
            location="、".join(it.get("cityList") or []),
            url=link,
            publish_time=pub,
            tags=tags,
        )
