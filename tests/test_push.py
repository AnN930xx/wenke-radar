"""推送层测试：不碰真实网络，mock requests，锁定"回执→PushResult"的映射契约，
以及 store.push_health 落库。确保"推送成不成功"被如实回报、可观测。
"""
import sqlite3

import pytest

import push
import store
from domain.delivery import summarize_push


class _FakeResp:
    def __init__(self, payload, text=""):
        self._payload = payload
        self.text = text or str(payload)

    def json(self):
        return self._payload


@pytest.fixture
def no_delay(monkeypatch):
    # 保证测试不发真实请求
    monkeypatch.setenv("PUSH_KEY", "")
    monkeypatch.setenv("WECOM_KEY", "")


class TestServerchanMapping:
    def test_success(self, monkeypatch):
        monkeypatch.setattr(push.requests, "post", lambda *a, **k: _FakeResp(
            {"code": 0, "data": {"error": "SUCCESS", "pushid": "PID123"}}))
        r = push._push_serverchan("k", "Server酱", "t", "c")
        assert r.success and r.code == 0 and r.pushid == "PID123"

    def test_non_success_code(self, monkeypatch):
        monkeypatch.setattr(push.requests, "post", lambda *a, **k: _FakeResp(
            {"code": 40001, "data": {"error": "BAD_KEY"}}, text="bad"))
        r = push._push_serverchan("k", "Server酱", "t", "c")
        assert not r.success and r.code == 40001 and "BAD_KEY" in r.error

    def test_exception_is_failure(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("network down")
        monkeypatch.setattr(push.requests, "post", boom)
        r = push._push_serverchan("k", "Server酱", "t", "c")
        assert not r.success and "network down" in r.error


class TestSendBriefStructured:
    def test_multi_key_returns_per_channel(self, monkeypatch):
        monkeypatch.setenv("PUSH_KEY", "k1,k2")
        monkeypatch.setenv("WECOM_KEY", "")
        monkeypatch.setattr(push.requests, "post", lambda *a, **k: _FakeResp(
            {"code": 0, "data": {"error": "SUCCESS", "pushid": "P"}}))
        results = push.send_brief("hello", title="t")
        assert len(results) == 2
        assert [r.channel for r in results] == ["Server酱#1", "Server酱#2"]
        assert summarize_push(results).succeeded == 2

    def test_no_channels_returns_empty(self, monkeypatch):
        monkeypatch.setenv("PUSH_KEY", "")
        monkeypatch.setenv("WECOM_KEY", "")
        assert push.send_brief("x") == []

    def test_all_failed_detected(self, monkeypatch):
        monkeypatch.setenv("PUSH_KEY", "k1,k2")
        monkeypatch.setenv("WECOM_KEY", "")
        monkeypatch.setattr(push.requests, "post", lambda *a, **k: _FakeResp(
            {"code": 40001, "data": {"error": "X"}}, text="x"))
        results = push.send_brief("hello")
        assert summarize_push(results).all_failed


class TestPushHealthPersistence:
    def test_save_push_health(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))
        from domain.delivery import PushResult
        store.save_push_health([
            PushResult("Server酱#1", True, code=0, pushid="P1"),
            PushResult("Server酱#2", False, code=40001, error="bad")])
        conn = sqlite3.connect(store.DB_PATH)
        rows = conn.execute(
            "SELECT channel, success, code, pushid, error FROM push_health "
            "ORDER BY channel").fetchall()
        conn.close()
        assert rows == [("Server酱#1", 1, 0, "P1", ""),
                        ("Server酱#2", 0, 40001, "", "bad")]

    def test_empty_results_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))
        store.save_push_health([])   # 不建库、不报错
