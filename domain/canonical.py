"""跨源去重（canonical identity）—— 同一真实岗位在多来源出现时的识别与折叠。

实证边界（2026-07 快照分析得出，改规则前先看证据）：
  会重复：同雇主的校招/社招双 feed 暴露同一 requisition（同平台 job_id）。
          实例：B站 updream 3 岗（校招/社招同 id）、腾讯海外 intern 75 组（被过滤器挡住但模式真实）。
  不会合并：
    - 标题相同但 job_id 不同 = 不同 requisition（美团校招/社招各有"招聘助理"，是两个岗）；
      标题级模糊匹配已验证过于危险（同源内同标题不同 id 有 1366 组），不做。
    - 聚合源公司级线索（牛客日程/offerstar）与官方岗位级抓取是互补两级，
      线索自带早鸟通道/网申截止等独立信息，不视为岗位重复、不砍。
      （曾试过按公司名子串匹配聚合线索→"京东方"误配"京东"，此路不通。）

canonical_job_id = f"{雇主}::{平台job_id}"：雇主由 source_id 归一（剥"(社招)"后缀），
job_id 是平台自己的稳定标识——同平台同 id 跨 feed 出现即同岗，置信度足够高。

两处消费：
  store.save_jobs   跨天抑制：新 feed 出现已知 canonical 的孪生行 → 入库但不计新增（防隔日重复推送）
  report 渲染入口   同轮折叠：dedupe_cross_source() 让同一岗在日报/推送只出现一次
"""
import re
from typing import Iterable, List, Set, Tuple

# 社招 feed 的 source_id 命名约定："雇主(社招)"（全角括号也兼容）
_SOCIAL_SUFFIX = re.compile(r"[（(]社招[）)]$")

# 折叠孪生时的保留优先级：官方招聘官网 > 官方ATS > 聚合发现源
_KIND_RANK = {"OFFICIAL_CAREERS": 0, "OFFICIAL_ATS": 1, "AGGREGATOR_DISCOVERY": 2}


def employer_of(source_id: str) -> str:
    """source_id -> 雇主名：同雇主的校招/社招 feed 归一到同一雇主。
    只做确定性归一（剥社招后缀），不做任何模糊/子串匹配（见模块头"不会合并"）。"""
    return _SOCIAL_SUFFIX.sub("", source_id or "")


def canonical_of(source_id: str, job_id: str) -> str:
    """canonical 身份：雇主::平台job_id。同平台同 id 跨 feed = 同一真实岗位。"""
    return f"{employer_of(source_id)}::{job_id}"


def dedupe_cross_source(jobs: List, new_keys: Iterable[str] = ()) -> Tuple[List, Set[str]]:
    """渲染层折叠：同 canonical 的孪生只保留一份，返回 (保留列表, 扩展后的 new_keys)。

    保留优先级：来源可信等级（官方官网>官方ATS>聚合）→ 校招版优先（带届别语义，
    进校招区按届分块）→ 输入顺序稳定兜底。
    new_keys 扩展：任一孪生是今日新增，则保留版也标记为新增——否则"社招 feed 先入库
    占了新增名额、渲染却保留校招版"时，这个岗会从推送里凭空消失。
    """
    new_keys = set(new_keys)
    groups = {}
    for j in jobs:
        groups.setdefault(j.canonical_job_id or j.dedup_key, []).append(j)

    keep_ids = set()
    for canon, twins in groups.items():
        if len(twins) == 1:
            keep_ids.add(id(twins[0]))
            continue
        chosen = min(twins, key=lambda j: (
            _KIND_RANK.get(j.source_kind, 9),
            0 if getattr(j, "recruit_type", "校招") != "社招" else 1))
        keep_ids.add(id(chosen))
        if any(t.dedup_key in new_keys for t in twins):
            new_keys.add(chosen.dedup_key)

    kept = [j for j in jobs if id(j) in keep_ids]   # 保持输入顺序
    return kept, new_keys
