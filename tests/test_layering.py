"""分层不变量测试：依赖只向上，关键层不反向/横向依赖（二轮审查精修后锁定）。

用 AST 静态扫描 import 关系，任何人破坏分层（如让 store 又依赖 filters）CI 立刻红。
"""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMPL_LAYERS = {"scrapers", "filters", "store", "report", "push", "main", "tracker", "scoring"}


def imports_of(rel_path):
    mods = set()
    tree = ast.parse(open(os.path.join(ROOT, rel_path), encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            mods.add(n.module.split(".")[0])
    return mods


def test_config_is_pure_data():
    """config 不依赖任何实现层（可含 user_profile，那是纯数据）"""
    assert not (imports_of("config.py") & (_IMPL_LAYERS | {"domain"}))


def test_domain_depends_only_on_config():
    """领域层只可依赖 config，不依赖任何实现层"""
    for m in ("models", "classify", "enrich", "results", "recruitment", "canonical"):
        assert not (imports_of(f"domain/{m}.py") & _IMPL_LAYERS), f"domain/{m}.py 反向依赖"


def test_store_not_depend_on_filters():
    """store 只依赖 domain（parse_recruit_year 已下沉），不再依赖 filters"""
    assert "filters" not in imports_of("store.py")


def test_report_not_depend_on_tracker():
    """report 是纯渲染器，投递数据由 main 传入，不 import tracker"""
    assert "tracker" not in imports_of("report.py")


def test_scrapers_dont_reach_over_domain():
    """抓取器不依赖 filters/store/report（只向上到 domain/config）"""
    import glob
    for path in glob.glob(os.path.join(ROOT, "scrapers", "*.py")):
        deps = imports_of(os.path.join("scrapers", os.path.basename(path)))
        assert not (deps & {"filters", "store", "report", "scoring", "tracker"}), path
