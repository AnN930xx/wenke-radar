"""滴滴社招抓取器（talent.didiglobal.com 自研 recruit-portal-service）
与滴滴校招（campus.didiglobal.com，Moka加密）不同，社招站是滴滴自研前端：
  GET /recruit-portal-service/api/job/front/list?page=N&pageSize=16
  明文 JSON，无需加密解密。注意：
  - 分页参数是 page（传 pageNum/pageIndex 等都被静默忽略、永远返回第一页！）
  - pageSize 服务端硬限 16（传 50/100 也只回 16 条）
  - 有 WAF 限流：短时间高频请求会被 openresty 拦成 501，翻页必须限速；
    命中限流时重试一次后明确报错（报错安全：异常源不参与下线归档）
  - 列表顺序会随岗位刷新变动，翻页用 jdId 去重，凑够 total 或连续空页即停
详情页: https://talent.didiglobal.com/social/p/{jdId}
"""
import re
import time
from .base import BaseScraper, JobItem, guess_category
import config

# 标题尾部的内部岗位编号，如 "用户产品经理 (JR2026071400F)"，展示时去掉
_JOB_CODE_RE = re.compile(r"\s*\(J[A-Z0-9]+\)\s*$")


class DidiSocialScraper(BaseScraper):
    name = "滴滴(社招)"
    host = "https://talent.didiglobal.com"

    def fetch(self):
        url = f"{self.host}/recruit-portal-service/api/job/front/list"
        headers = {"Referer": f"{self.host}/social/list"}
        seen = {}
        page = 1
        empty_streak = 0
        total = None
        while True:
            r = self.session.get(url, params={"page": page, "pageSize": 16},
                                 headers=headers, timeout=config.REQUEST_TIMEOUT)
            try:
                data = r.json()
            except ValueError:
                time.sleep(5)  # 疑似触发 WAF 限流，缓一下重试一次
                r = self.session.get(url, params={"page": page, "pageSize": 16},
                                     headers=headers, timeout=config.REQUEST_TIMEOUT)
                try:
                    data = r.json()
                except ValueError:
                    raise RuntimeError(
                        f"滴滴社招接口返回非JSON(HTTP {r.status_code})，疑似WAF限流，"
                        f"已抓 {len(seen)} 岗后中断")
            if (data.get("meta") or {}).get("code") != 0:
                break
            d = data.get("data") or {}
            total = d.get("total") or total
            self.reported_total = total or None
            items = d.get("items") or []
            fresh = 0
            for it in items:
                jid = str(it.get("jdId") or "")
                if jid and jid not in seen:
                    seen[jid] = self._parse(it, jid)
                    fresh += 1
            empty_streak = empty_streak + 1 if fresh == 0 else 0
            if not items or empty_streak >= 3:
                break
            if total and len(seen) >= total:
                break
            page += 1
            if page > 120:  # 1086岗/16条 ≈ 68页，留余量封顶
                break
            time.sleep(0.4)  # 翻页限速，避免触发 WAF（一天一跑，慢点没关系）
        jobs = list(seen.values())
        for j in jobs:
            j.recruit_type = "社招"
        return jobs

    def _parse(self, it, jid):
        raw_title = (it.get("jobName") or "").strip()
        title = _JOB_CODE_RE.sub("", raw_title)
        return JobItem(
            company=self.name,
            job_id=jid,
            title=title,
            category=guess_category(title),
            location=it.get("workArea") or "",
            url=f"{self.host}/social/p/{jid}",
            publish_time=(it.get("refreshTime") or "")[:10],
            tags=it.get("deptName") or "",
        )
