"""送达域 —— "把日报可靠地送到用户手里，且只送一次"的纯逻辑。

单一职责：只做**数据结构 + 判定规则**，不做任何 I/O（不发网络、不读文件、不碰 DB、不读环境变量）。
调用方（push 层发请求、main 层编排、ops_guard 薄入口）把 I/O 结果作为参数传进来，
本模块给出结论。好处：这些"安全保障"的规则可以脱离网络/云端被单元测试锁定。

两类关注点：
  1) 送达检测：PushResult(单渠道结果) + summarize_push(整体成败) —— 供 main 判断"要不要告警/标红"。
  2) 触发去重：should_skip_scheduled_run / should_block_manual_dispatch —— workflow 两道守卫的判定，
     从 YAML shell 上收到这里，成为**单一真源**并可被测试（避免 shell 与代码各写一套、悄悄漂移）。
"""
from dataclasses import dataclass


# ==================== 送达检测 ====================
@dataclass
class PushResult:
    """一次单渠道推送的结果（推送层产出，编排层消费，存储层落库）。不含密钥明文。"""
    channel: str                # 渠道标签，如 "Server酱#1" / "企业微信"
    success: bool               # 该渠道是否确认接受成功
    code: int = None            # 服务端返回码（Server酱 code / 企业微信 errcode）
    error: str = ""             # 失败原因（成功为空）
    pushid: str = ""            # 服务端回执 id（可回查，成功才有）

    def describe(self) -> str:
        if self.success:
            tail = f"（pushid={self.pushid}）" if self.pushid else ""
            return f"{self.channel}: 成功{tail}"
        return f"{self.channel}: 失败 code={self.code} {self.error}".rstrip()


@dataclass
class PushSummary:
    """一轮推送的整体结论。all_failed 是编排层"要不要标红告警"的开关。"""
    total: int          # 尝试的渠道数（0 = 没配置渠道，本地跑常见）
    succeeded: int
    failed: int

    @property
    def any_success(self) -> bool:
        return self.succeeded > 0

    @property
    def all_failed(self) -> bool:
        """有渠道可推却全军覆没 —— 用户大概率没收到，必须告警。
        没配置渠道（total=0）不算失败：本地无 key 跑通流程是正常场景。"""
        return self.total > 0 and self.succeeded == 0


def summarize_push(results) -> PushSummary:
    """把逐渠道 PushResult 汇总成整体结论（纯统计，不做副作用）。"""
    results = list(results or [])
    ok = sum(1 for r in results if r.success)
    return PushSummary(total=len(results), succeeded=ok, failed=len(results) - ok)


# ==================== 触发去重 / 防抢跑（workflow 两道守卫的判定真源） ====================
# report_exists = "当天日报文件是否已存在（=当天是否已成功产出并推送过）"，由调用方做文件判断后传入。
# 时间不参与判断：GitHub cron 常延迟数小时，"几点了"不可靠，"当天有没有推过"才是铁证（错误日志#29）。

def should_skip_scheduled_run(event_name: str, report_exists: bool) -> bool:
    """定时触发去重：早间三连 + 兜底共 5 个定时点，谁先成功产出当天日报，
    其余定时点看到日报已存在就跳过 —— 保证一天只推一次。手动触发不走此路。"""
    return event_name == "schedule" and report_exists


def should_block_manual_dispatch(event_name: str, report_exists: bool,
                                 force: bool, has_history: bool = True) -> bool:
    """手动触发防抢跑：当天日报还没出时手动跑，会成为当天首份并推送、抢占随后定时推送的名额。
    → 拦截，除非显式 force=true（用于定时确实被 GitHub 丢弃时的补跑）。

    has_history=False（reports/ 里一份日报都没有）→ 放行：这是新部署者的首次试跑，
    此时没有"既有的每日节奏"可抢占，拦截只会让人以为没配置成功。守卫只保护已在跑的系统。
    """
    if event_name != "workflow_dispatch" or force:
        return False
    return has_history and not report_exists
