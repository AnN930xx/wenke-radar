"""Moka(mokahr.com)招聘平台通用抓取器
大量快消/互联网公司用 Moka 搭校招官网（农夫山泉、滴滴、名创优品等），
域名可能是 app.mokahr.com 或公司自有域名（如 campus.didiglobal.com）。

接口: POST {host}/api/outer/ats-apply/website/jobs/module
  body: {"orgId": "..", "siteId": N, "pagination": {"pageIndex": N, "pageSize": M}, "locale": "zh-cn"}

响应是 AES-CBC 加密的 {"data": <base64密文>, "necromancer": <16字节密钥>}：
  key = necromancer（每次响应下发）
  iv  = 固定常量 de7c21ed8d6f50fe（全平台通用，从前端 window.TurboApply.data.aesIv 得到）
  解密后是标准 JSON。

接入新的 Moka 公司：在 config 配 host/orgId/siteId，然后注册子类（参照 NongfuScraper）。
如何拿 orgId/siteId：打开公司 Moka 校招页，控制台执行
  window.TurboApply.data.org.id  和  window.TurboApply.data.org.siteId
"""
import base64
import json
from .base import BaseScraper, JobItem, guess_category
import config

# Moka 全平台固定 AES-CBC IV（来自前端 window.TurboApply.data.aesIv）
MOKA_AES_IV = b"de7c21ed8d6f50fe"


def _decrypt(data_b64: str, necromancer: str) -> dict:
    """解密 Moka 响应。依赖 pycryptodome。"""
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    ct = base64.b64decode(data_b64)
    key = necromancer.encode("utf-8")
    pt = unpad(AES.new(key, AES.MODE_CBC, MOKA_AES_IV).decrypt(ct), 16)
    return json.loads(pt.decode("utf-8"))


class MokaScraper(BaseScraper):
    """Moka 通用抓取器，子类通过 config.COMPANY_CONFIG[name] 的 host/org_id/site_id 指定"""
    name = ""

    def _fetch_items(self):
        cfg = config.COMPANY_CONFIG.get(self.name, {})
        host = cfg["host"].rstrip("/")
        org_id = cfg["org_id"]
        site_id = cfg["site_id"]
        url = f"{host}/api/outer/ats-apply/website/jobs/module"
        headers = {
            "Content-Type": "application/json",
            "Referer": f"{host}/",
            "Origin": host,
        }
        all_jobs = []
        page = 1
        page_size = 100
        while True:
            body = {
                "orgId": org_id,
                "siteId": site_id,
                "pagination": {"pageIndex": page, "pageSize": page_size},
                "locale": "zh-cn",
            }
            r = self.session.post(url, json=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
            resp = r.json()
            if not resp.get("necromancer"):
                break  # 官网关闭或异常时可能无加密体
            obj = _decrypt(resp["data"], resp["necromancer"])
            d = obj.get("data") or {}
            jobs = d.get("jobs") or []
            if not jobs:
                break
            all_jobs.extend(jobs)
            total = (d.get("jobStats") or {}).get("total") or 0
            self.reported_total = total or None
            if total and len(all_jobs) >= total:
                break
            if len(jobs) < page_size:
                break
            page += 1
            if page > 40:
                break
        label = cfg.get("job_nature", "校招")
        jobs = [self._parse(it, host, org_id, site_id) for it in all_jobs]
        for j in jobs:
            j.recruit_type = label
        return jobs

    def _parse(self, it, host, org_id, site_id):
        title = (it.get("title") or "").strip()
        job_id = str(it.get("id") or "")
        return JobItem(
            company=self.name,
            job_id=job_id,
            title=title,
            category=guess_category(title),
            location="",  # Moka 岗位对象不含城市（城市在分组接口里），留空由标题兜底
            url=f"{host}/campus-recruitment/{org_id}/{site_id}/job/{job_id}",
            publish_time="",
            tags="",
        )


class NongfuScraper(MokaScraper):
    name = "农夫山泉"


class DidiScraper(MokaScraper):
    name = "滴滴"
