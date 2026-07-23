"""录制真实 API 响应样本 → tests/fixtures/<源名>.json（供离线契约测试）。

原理：把每个抓取器实例的 _parse 包一层，抓取过程中捕获前 N 个真实入参
（原始 item dict + 附加参数如类别字典），JSON 落盘。之后 CI 里不碰网络，
拿样本回放 _parse，锁定字段映射契约。

手动运行（接口改版后重录对应源）：
    PYTHONUTF8=1 python tests/record_fixtures.py           # 录全部（约一轮抓取时长）
    PYTHONUTF8=1 python tests/record_fixtures.py 京东 快手  # 只录指定源

不读写 jobs.db；HTML 解析型源（bs4 对象不可序列化）自动跳过。
"""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                      # noqa: E402
from scrapers import SCRAPERS      # noqa: E402
from main import build_http_session  # noqa: E402

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SAMPLES_PER_SOURCE = 2


def record(names=None):
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    session = build_http_session()
    targets = {k: v for k, v in SCRAPERS.items() if not names or k in names}
    done, skipped = [], []

    for name, cls in targets.items():
        if not config.ENABLED_COMPANIES.get(name, True):
            continue
        if not hasattr(cls, "_parse"):
            skipped.append((name, "无 _parse 方法"))
            continue
        scraper = cls(session)
        captured = []
        orig_parse = scraper._parse

        def wrapper(*args, _orig=orig_parse, _cap=captured, **kw):
            if len(_cap) < SAMPLES_PER_SOURCE and not kw:
                _cap.append(args)
            return _orig(*args, **kw)

        scraper._parse = wrapper
        try:
            scraper.fetch()
        except Exception as e:
            if not captured:
                skipped.append((name, f"抓取失败 {e}"))
                continue
        samples = []
        for args in captured:
            try:
                json.dumps(args)
                samples.append(list(args))
            except TypeError:
                pass   # bs4 节点等不可序列化入参
        if not samples:
            skipped.append((name, "无可序列化样本"))
            continue
        with open(os.path.join(FIXTURE_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump({"source": name, "recorded_at": date.today().isoformat(),
                       "samples": samples}, f, ensure_ascii=False, indent=1)
        print(f"[{name}] ✅ 已录 {len(samples)} 个样本")
        done.append(name)

    print(f"\n== 录制完成：{len(done)} 个源 ==")
    for name, reason in skipped:
        print(f"  跳过 [{name}]: {reason}")


if __name__ == "__main__":
    record(sys.argv[1:] or None)
