"""每源 fixture 契约测试：录制的真实响应样本离线回放 _parse。

作用（外部审查采纳项）：接口改版或解析代码被重构破坏时，CI 直接红，
并能区分"网站数据变了"和"解析写坏了"——不碰网络，确定性执行。
样本由 tests/record_fixtures.py 录制，接口改版后重录对应源即可。
"""
import glob
import json
import os

import pytest

from domain.models import JobItem
from scrapers import SCRAPERS

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
_files = sorted(glob.glob(os.path.join(FIXTURE_DIR, "*.json")))


@pytest.mark.parametrize(
    "path", _files,
    ids=[os.path.splitext(os.path.basename(p))[0] for p in _files])
def test_parse_contract(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cls = SCRAPERS[data["source"]]
    scraper = cls(None)   # _parse 不碰网络，session 传 None 即可
    for args in data["samples"]:
        job = scraper._parse(*args)
        assert isinstance(job, JobItem), "解析产物必须是 JobItem"
        assert job.company, "company 不能为空"
        assert job.job_id and job.job_id not in ("None", ""), "job_id 必须稳定非空"
        assert job.title, "title 不能为空"
        assert job.recruit_type in ("校招", "社招")


def test_fixture_coverage_documented():
    """fixture 覆盖数只能涨不能掉（防止有人误删样本）"""
    assert len(_files) >= 15, f"当前仅 {len(_files)} 个源有 fixture（应 >= 15）"
