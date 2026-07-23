"""用户自定义方向（隔离区）测试：证明三件事——
  1. 用户加的方向能端到端生效（检索→过滤→推送）；
  2. 用户配置写坏了，引擎照常运行、抓取器不受影响（隔离性）；
  3. 同名方向合并不覆盖内置。
"""
import ast
import copy
import glob
import os

import pytest

import config
import report
from domain.models import JobItem
from filters import filter_jobs, _match_keywords


@pytest.fixture(autouse=True)
def restore_keywords():
    """每个用例后还原全局 KEYWORDS/CATEGORY_KEYWORDS，避免相互污染"""
    kw = copy.deepcopy(config.KEYWORDS)
    ck = list(config.CATEGORY_KEYWORDS)
    yield
    config.KEYWORDS.clear()
    config.KEYWORDS.update(kw)
    config.CATEGORY_KEYWORDS[:] = ck


def job(title, recruit_type="社招"):
    return JobItem(company="测试", job_id=title, title=title, location="上海",
                   url=f"https://x.com/{title}", recruit_type=recruit_type)


class TestCustomDirectionWorks:
    def test_added_direction_end_to_end(self):
        added = config.apply_user_directions({"游戏发行": ["游戏发行", "发行经理"]})
        assert added == ["游戏发行"]
        j = job("游戏发行运营专员")
        assert _match_keywords(j)                       # 检索命中
        assert filter_jobs([j])                          # 过滤保留
        content, n = report.generate_push_brief([j], {j.dedup_key})
        assert n == 1 and "游戏发行运营专员" in content  # 进推送

    def test_direction_name_becomes_category_hit(self):
        config.apply_user_directions({"法务合规": ["法务", "合规"]})
        assert "法务合规" in config.CATEGORY_KEYWORDS

    def test_merge_not_override_builtin(self):
        before = list(config.KEYWORDS["运营"])
        config.apply_user_directions({"运营": ["直播中控"]})
        assert "直播中控" in config.KEYWORDS["运营"]
        assert all(k in config.KEYWORDS["运营"] for k in before)   # 原关键词都还在


class TestBrokenConfigIsolated:
    """坏配置必须被安全忽略——绝不抛异常、绝不影响引擎"""

    @pytest.mark.parametrize("bad", [
        None, "不是字典", 123, [],
        {"": ["空方向名"]},
        {"方向": "关键词得是列表不是字符串"},
        {"方向": [123, None]},        # 关键词非字符串
        {"方向": []},                 # 空关键词列表
        {123: ["方向名得是字符串"]},
    ])
    def test_malformed_never_raises(self, bad):
        added = config.apply_user_directions(bad)     # 不抛异常
        assert isinstance(added, list)                # 坏项被跳过，返回空或部分

    def test_partial_good_partial_bad(self):
        added = config.apply_user_directions({
            "有效方向": ["翻译", "本地化"],
            "": ["会被跳过"],
            "坏值": "不是列表",
        })
        assert added == ["有效方向"]                   # 只有合法项生效

    def test_scrapers_dont_depend_on_keywords(self):
        """隔离性硬证据：抓取器源码不读 KEYWORDS——所以改方向绝不影响'抓什么'。
        （抓取器只用 CATEGORY_KEYWORDS 给岗位标类别标签，那是标注不是筛选，抓的仍是全量。）"""
        offenders = []
        for path in glob.glob(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                           "scrapers", "*.py")):
            src = open(path, encoding="utf-8").read()
            # 精确匹配属性访问 .KEYWORDS（node.attr 对 CATEGORY_KEYWORDS 是全称，不会误报）
            if any(isinstance(n, ast.Attribute) and n.attr == "KEYWORDS"
                   for n in ast.walk(ast.parse(src))):
                offenders.append(os.path.basename(path))
        assert not offenders, f"抓取器不应依赖 KEYWORDS：{offenders}"
