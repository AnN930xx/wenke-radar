"""触发守卫薄入口 —— 供 GitHub workflow 在跑抓取前判定"这次触发该不该继续"。

薄：只做 I/O（读环境变量 + 判断当天日报文件在不在），判定规则全在 domain/delivery.py（纯、可测）。
这样 workflow 的去重/防抢跑不再是散在 YAML 里的 shell，与代码共用**同一套被测试锁定的规则**。

约定退出码（daily.yml 据此分流）：
   0  继续正常跑
  10  定时去重命中：当天已推过，跳过本次
  20  防抢跑拦截：手动触发但当天日报未出（会抢跑定时推送），需 force=true

环境变量：EVENT=github.event_name，FORCE=inputs.force（"true"/其它）。
"""
import glob
import os
import sys
from datetime import date

from domain.delivery import (should_skip_scheduled_run,
                             should_block_manual_dispatch)

SKIP_EXIT = 10
BLOCK_EXIT = 20


def main() -> int:
    event = os.environ.get("EVENT", "")
    force = os.environ.get("FORCE", "").lower() == "true"
    report_exists = os.path.exists(
        os.path.join("reports", f"{date.today().isoformat()}.md"))
    # 有没有"既有的每日节奏"可被抢占——新部署者首次试跑时 reports/ 为空，应放行
    has_history = bool(glob.glob(os.path.join("reports", "*.md")))

    if should_skip_scheduled_run(event, report_exists):
        print("定时去重：当天日报已存在，跳过本次触发（避免重复推送）。")
        return SKIP_EXIT
    if should_block_manual_dispatch(event, report_exists, force, has_history):
        print("防抢跑：当天日报还没出，手动跑会抢占定时推送名额；"
              "确需补跑（如定时被 GitHub 丢弃）请带 force=true。")
        return BLOCK_EXIT
    return 0


if __name__ == "__main__":
    sys.exit(main())
