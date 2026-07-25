"""送达域纯逻辑测试：推送结果汇总 + 两道触发守卫的真值表。

这些是"安全保障"的规则本身，脱离网络/云端在这里被锁定——
任何人改坏"全失败才告警""当天已推就跳过""手动未出日报要拦截"CI 立刻红。
"""
from domain.delivery import (
    PushResult, PushSummary, summarize_push,
    should_skip_scheduled_run, should_block_manual_dispatch)


class TestPushResult:
    def test_describe_success(self):
        r = PushResult(channel="Server酱#1", success=True, code=0, pushid="abc")
        assert "成功" in r.describe() and "abc" in r.describe()

    def test_describe_failure(self):
        r = PushResult(channel="Server酱", success=False, code=40001, error="bad key")
        d = r.describe()
        assert "失败" in d and "40001" in d and "bad key" in d


class TestSummarizePush:
    def test_no_channels_is_not_failure(self):
        """没配置渠道（本地无 key）不算失败，只是没推。"""
        s = summarize_push([])
        assert s == PushSummary(0, 0, 0)
        assert not s.all_failed and not s.any_success

    def test_all_success(self):
        s = summarize_push([PushResult("a", True), PushResult("b", True)])
        assert s.succeeded == 2 and s.failed == 0
        assert s.any_success and not s.all_failed

    def test_partial_failure_not_all_failed(self):
        """一个成功一个失败 → 至少送达一个，不触发告警。"""
        s = summarize_push([PushResult("a", True), PushResult("b", False)])
        assert s.succeeded == 1 and s.failed == 1
        assert s.any_success and not s.all_failed

    def test_all_failed_triggers_alarm(self):
        """有渠道可推却全挂 → all_failed=True（编排层据此标红告警）。"""
        s = summarize_push([PushResult("a", False), PushResult("b", False)])
        assert s.all_failed and not s.any_success


class TestScheduledDedup:
    """定时去重：一天多个触发点，谁先出报告谁推，其余跳过。"""
    def test_skip_when_report_exists(self):
        assert should_skip_scheduled_run("schedule", True) is True

    def test_run_when_no_report(self):
        assert should_skip_scheduled_run("schedule", False) is False

    def test_manual_never_skips_here(self):
        # 手动触发不走定时去重（它走防抢跑守卫）
        assert should_skip_scheduled_run("workflow_dispatch", True) is False


class TestManualAntiPreempt:
    """防抢跑：手动触发在当天定时推送前跑会抢名额。"""
    def test_block_when_no_report_no_force(self):
        assert should_block_manual_dispatch("workflow_dispatch", False, False) is True

    def test_force_overrides(self):
        assert should_block_manual_dispatch("workflow_dispatch", False, True) is False

    def test_allow_when_report_exists(self):
        # 当天已推过，手动再跑由定时去重兜底、不会重复，放行
        assert should_block_manual_dispatch("workflow_dispatch", True, False) is False

    def test_schedule_not_subject_to_antipreempt(self):
        assert should_block_manual_dispatch("schedule", False, False) is False
