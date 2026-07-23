"""
秋招雷达 · 抓取器压力测试工具

对每个数据源做多轮 + 并发压测，评估：
  - 可靠性：多轮是否稳定成功（偶发失败率）
  - 延迟：单次抓取耗时
  - 抓取量稳定性：多轮之间原始条数是否一致（波动大=接口不稳）
  - 命中量：经关键词/城市/届别过滤后的对口岗位数
  - 限流/封禁：并发猛打时是否开始报错

用法：
    python stress_test.py                # 全部数据源，3 轮顺序 + 1 轮并发
    python stress_test.py --rounds 5     # 自定义轮数
    python stress_test.py 腾讯 字节跳动   # 只测指定公司
    python stress_test.py --new          # 只测本次改造新增的公司
"""
import sys
import time
import statistics
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
from scrapers import SCRAPERS
import filters

# 最近一轮改造新增的公司（批次11-15：快消第二批 + 大厂社招 + 滴滴/伊利社招）
NEW_COMPANIES = [
    "蒙牛", "伊利", "元气森林",
    "蒙牛(社招)", "字节跳动(社招)", "腾讯(社招)", "滴滴(社招)", "伊利(社招)",
]


def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT})
    retry = Retry(total=config.MAX_RETRIES, backoff_factor=1,
                  status_forcelist=[500, 502, 503, 504],
                  allowed_methods=["GET", "POST"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def run_once(name):
    """跑一次某公司的抓取，返回 (耗时秒, 原始条数, 命中数, 错误信息)"""
    cls = SCRAPERS[name]
    session = make_session()
    t0 = time.time()
    try:
        jobs = cls(session).fetch()
        elapsed = time.time() - t0
        hits = len(filters.filter_jobs(list(jobs)))
        return (elapsed, len(jobs), hits, None)
    except Exception as e:
        elapsed = time.time() - t0
        err = f"{type(e).__name__}: {e}"
        return (elapsed, None, None, err)


def sequential_test(companies, rounds):
    """顺序多轮：每家连跑 rounds 轮，评估可靠性与稳定性"""
    print("=" * 78)
    print(f"阶段一 · 顺序可靠性测试（每家 {rounds} 轮，独立 session）")
    print("=" * 78)
    results = {}
    for name in companies:
        runs = [run_once(name) for _ in range(rounds)]
        results[name] = runs
        ok = [r for r in runs if r[3] is None]
        fail = [r for r in runs if r[3] is not None]
        lat = [r[0] for r in runs]
        counts = [r[1] for r in ok]
        hits = [r[2] for r in ok]
        status = "✅" if not fail else ("⚠️" if ok else "❌")
        count_str = ""
        if counts:
            cmin, cmax = min(counts), max(counts)
            count_str = f"{cmin}" if cmin == cmax else f"{cmin}~{cmax}⚠波动"
        hit_str = f"{max(hits)}" if hits else "-"
        print(f"{status} {name:<8} | 成功 {len(ok)}/{rounds} | "
              f"延迟 {min(lat):.1f}~{max(lat):.1f}s | 原始 {count_str or '-':<10} | 命中 {hit_str}")
        if fail:
            print(f"      └─ 失败样例: {fail[0][3][:120]}")
    return results


def concurrent_test(companies):
    """并发压测：所有公司同时开抓，模拟高负载，检测限流/session 冲突"""
    print()
    print("=" * 78)
    print(f"阶段二 · 并发压测（{len(companies)} 家同时开抓）")
    print("=" * 78)
    t0 = time.time()
    outcomes = {}
    with ThreadPoolExecutor(max_workers=len(companies)) as ex:
        futs = {ex.submit(run_once, name): name for name in companies}
        for fut in as_completed(futs):
            name = futs[fut]
            outcomes[name] = fut.result()
    total = time.time() - t0
    ok = sum(1 for r in outcomes.values() if r[3] is None)
    print(f"并发总耗时 {total:.1f}s ｜ 成功 {ok}/{len(companies)}")
    fails = {n: r for n, r in outcomes.items() if r[3] is not None}
    if fails:
        print("并发下失败的公司（可能限流/session 冲突）：")
        for n, r in fails.items():
            print(f"  ❌ {n}: {r[3][:120]}")
    else:
        print("✅ 并发下无失败，未发现限流/session 冲突")
    return outcomes


def compare_seq_vs_concurrent(seq_results, conc_results):
    """对比顺序 vs 并发的原始条数，条数骤降可能是限流软失败"""
    print()
    print("-" * 78)
    print("一致性检查（顺序 vs 并发原始条数，骤降可能是限流软失败）：")
    anomaly = False
    for name in seq_results:
        seq_ok = [r[1] for r in seq_results[name] if r[3] is None]
        conc = conc_results.get(name)
        if not seq_ok or not conc or conc[3] is not None:
            continue
        seq_max = max(seq_ok)
        c = conc[1]
        if seq_max > 0 and c is not None and c < seq_max * 0.5:
            print(f"  ⚠️ {name}: 顺序 {seq_max} → 并发骤降到 {c}")
            anomaly = True
    if not anomaly:
        print("  ✅ 未发现并发下抓取量骤降")


def main():
    rounds = 3
    # 先取 --rounds 的值，并记下它的位置，避免把这个数字当成公司名
    rounds_val_idx = None
    if "--rounds" in sys.argv:
        idx = sys.argv.index("--rounds")
        rounds = int(sys.argv[idx + 1])
        rounds_val_idx = idx + 1
    # 位置参数=公司名：排除所有 --flag 以及 --rounds 后面那个数值
    args = [a for i, a in enumerate(sys.argv[1:], start=1)
            if not a.startswith("--") and i != rounds_val_idx]
    if "--new" in sys.argv:
        companies = [c for c in NEW_COMPANIES if c in SCRAPERS]
    elif args:
        companies = [c for c in args if c in SCRAPERS]
    else:
        companies = list(SCRAPERS.keys())

    if not companies:
        print("⚠️ 没有匹配到任何公司，请检查参数（公司名要和 config 里的完全一致）")
        return
    print(f"压测目标：{len(companies)} 家 · {', '.join(companies)}\n")
    seq = sequential_test(companies, rounds)
    conc = concurrent_test(companies)
    compare_seq_vs_concurrent(seq, conc)

    # 总评
    print()
    print("=" * 78)
    print("总评")
    print("=" * 78)
    flaky, slow, unstable, dead = [], [], [], []
    for name, runs in seq.items():
        ok = [r for r in runs if r[3] is None]
        if not ok:
            dead.append(name)
            continue
        if len(ok) < len(runs):
            flaky.append(name)
        lat = [r[0] for r in runs]
        if max(lat) > 30:
            slow.append(f"{name}({max(lat):.0f}s)")
        counts = [r[1] for r in ok]
        if counts and min(counts) < max(counts) * 0.9 and max(counts) > 5:
            unstable.append(name)
    print(f"完全失败（需修）：{dead or '无'}")
    print(f"偶发失败（不稳）：{flaky or '无'}")
    print(f"抓取量波动>10%：{unstable or '无'}")
    print(f"慢（>30s）：{slow or '无'}")
    verdict = "全部健康 ✅" if not (dead or flaky) else "有问题需关注 ⚠️"
    print(f"\n结论：{verdict}")


if __name__ == "__main__":
    main()
