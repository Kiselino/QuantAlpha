"""brain_client 单测：mock HTTP（限流头解析 / 模拟 Location / 轮询 / 相关性）。"""

from __future__ import annotations

import pytest

from qa.brain_client import (
    BrainClient,
    RateLimits,
    SimulationResult,
    SubmissionRejected,
)

BASE = "https://api.worldquantbrain.com"


def _fake_response(status_code, payload=None, headers=None):
    class Resp:
        def __init__(self):
            self.status_code = status_code
            self.headers = headers or {}
            self._payload = payload
            self.content = b"" if payload is None else b"{}"

        @property
        def text(self):
            return self.content.decode("utf-8", errors="replace")

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    return Resp()


def test_rate_limits_parse(monkeypatch):
    client = BrainClient("t=abc")
    resp_headers = {
        "x-ratelimit-limit-minute": "30",
        "x-ratelimit-remaining-minute": "29",
        "ratelimit-reset": "6",
    }

    def fake_get(path, headers=None, timeout=None, params=None):
        assert path == f"{BASE}/users/self"
        return _fake_response(200, {}, resp_headers)

    monkeypatch.setattr(client.session, "get", fake_get)
    rl = client.rate_limits()
    assert rl.limit_minute == 30
    assert rl.remaining_minute == 29


def test_retry_get_retries_empty_body(monkeypatch):
    """空 body（平台瞬时异常）时重试而非抛 JSONDecodeError（实测偶发）。"""
    client = BrainClient("t=abc")
    calls = {"n": 0}

    def fake_get(path, headers=None, timeout=None, params=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _fake_response(200, None)  # 空 body
        return _fake_response(200, {"max": 0.5})

    monkeypatch.setattr(client.session, "get", fake_get)
    _, data, _ = client._retry_get("/alphas/A1/correlations/self")
    assert calls["n"] == 2
    assert isinstance(data, dict) and data["max"] == 0.5


def test_simulate_returns_location(monkeypatch):
    client = BrainClient("t=abc")

    def fake_post(path, headers=None, json=None, timeout=None):
        assert path == f"{BASE}/simulations"
        return _fake_response(
            201, {"some": "data"}, {"Location": "/simulations/sim123"}
        )

    monkeypatch.setattr(client.session, "post", fake_post)
    sim_id = client.simulate("rank(close)", {})
    assert sim_id == "sim123"


def test_poll_simulation_completed(monkeypatch):
    client = BrainClient("t=abc")
    completed = {
        "status": "COMPLETE",
        "alpha": "0mKGJoWr",
    }
    alpha_detail = {
        "id": "0mKGJoWr",
        "is": {
            "sharpe": 1.5,
            "fitness": 1.2,
            "turnover": 0.2,
            "returns": 0.05,
            "drawdown": 0.1,
            "checks": [
                {"name": "SHARPE", "result": "PASS", "limit": 1.25, "value": 1.5}
            ],
        },
    }

    def fake_get(path, headers=None, timeout=None, params=None):
        if path == f"{BASE}/simulations/sim123":
            return _fake_response(200, completed)
        if path == f"{BASE}/alphas/0mKGJoWr":
            return _fake_response(200, alpha_detail)
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(client.session, "get", fake_get)
    r = client.poll_simulation("sim123", max_wait=1.0)
    assert r.status == "COMPLETE"
    assert r.alpha_id == "0mKGJoWr"
    assert r.metrics["sharpe"] == 1.5
    assert len(r.checks) == 1


def test_poll_simulation_timeout(monkeypatch):
    client = BrainClient("t=abc")
    pending = {"status": "PENDING"}

    def fake_get(path, headers=None, timeout=None, params=None):
        return _fake_response(200, pending)

    monkeypatch.setattr(client.session, "get", fake_get)
    with pytest.raises(TimeoutError):
        client.poll_simulation("sim123", max_wait=0.1)


def test_correlations_self_max(monkeypatch):
    client = BrainClient("t=abc")
    payload = {
        "schema": {"name": "selfCorrelation"},
        "records": [
            [
                "a1",
                None,
                "EQUITY",
                "USA",
                "TOP3000",
                0.132,
                1.62,
                0.071,
                0.12,
                1.22,
                0.002,
            ],
            [
                "a2",
                None,
                "EQUITY",
                "USA",
                "TOP3000",
                0.064,
                1.52,
                0.09,
                0.015,
                1.31,
                0.009,
            ],
        ],
        "min": 0.057,
        "max": 0.125,
    }

    def fake_get(path, headers=None, timeout=None, params=None):
        assert path == f"{BASE}/alphas/XYZ/correlations/self"
        return _fake_response(200, payload)

    monkeypatch.setattr(client.session, "get", fake_get)
    assert client.correlations_self("XYZ") == 0.125


def test_correlations_self_missing_max_raises(monkeypatch):
    """fail-closed：响应异常时抛错，不允许静默放行提交（禁止返回 0.0）。"""
    client = BrainClient("t=abc")

    def fake_get(path, headers=None, timeout=None, params=None):
        return _fake_response(200, {"schema": "junk", "records": []})

    monkeypatch.setattr(client.session, "get", fake_get)
    with pytest.raises(RuntimeError, match="相关门"):
        client.correlations_self("XYZ")


def test_submit_returns_json(monkeypatch):
    client = BrainClient("t=abc")

    def fake_post(path, headers=None, json=None, timeout=None):
        assert path == f"{BASE}/alphas/A1/submit"
        return _fake_response(200, {"status": "SUBMITTED", "message": "ok"})

    monkeypatch.setattr(client.session, "post", fake_post)
    resp = client.submit("A1")
    assert resp["status"] == "SUBMITTED"


def test_get_alpha_returns_detail(monkeypatch):
    client = BrainClient("t=abc")

    def fake_get(path, headers=None, timeout=None, params=None):
        assert path == f"{BASE}/alphas/A1"
        return _fake_response(200, {"id": "A1", "status": "ACTIVE"})

    monkeypatch.setattr(client.session, "get", fake_get)
    detail = client.get_alpha("A1")
    assert detail["status"] == "ACTIVE"


# ---- 合规核心：提交被拒（403 + is.checks）判定与解析 ----


def test_submit_403_rejection_parses_checks(monkeypatch):
    """提交被拒（403 + is.checks 载荷）→ 抛 SubmissionRejected 且解析出全部 FAIL 检查。"""
    client = BrainClient("t=abc")
    payload = {
        "is": {
            "checks": [
                {"name": "SHARPE", "result": "FAIL", "value": 1.0},
                {"name": "FITNESS", "result": "FAIL", "value": 0.8},
                {"name": "TURNOVER", "result": "PASS", "value": 0.2},
            ]
        }
    }

    def fake_post(path, headers=None, json=None, timeout=None):
        assert path == f"{BASE}/alphas/A1/submit"
        return _fake_response(403, payload)

    monkeypatch.setattr(client.session, "post", fake_post)
    with pytest.raises(SubmissionRejected) as excinfo:
        client.submit("A1")
    assert [c["name"] for c in excinfo.value.checks] == [
        "SHARPE",
        "FITNESS",
        "TURNOVER",
    ]
    assert [c["result"] for c in excinfo.value.checks if c["result"] == "FAIL"] == [
        "FAIL",
        "FAIL",
    ]


def test_submit_403_without_checks_payload_is_session_error(monkeypatch):
    """403 但不含 is.checks 载荷（纯会话过期）→ 抛 PermissionError 而非 SubmissionRejected。"""
    client = BrainClient("t=abc")

    def fake_post(path, headers=None, json=None, timeout=None):
        return _fake_response(403, {"message": "unauthorized"})

    monkeypatch.setattr(client.session, "post", fake_post)
    with pytest.raises(PermissionError, match="会话无效"):
        client.submit("A1")


# ---- 限流：429 退避 / THROTTLED / Retry-After 解析 ----


def test_post_with_retry_backs_off_on_429(monkeypatch):
    """429 常规限流：按 Retry-After 退避后重试，最终成功。"""
    client = BrainClient("t=abc")
    calls = {"n": 0}

    def fake_post(path, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return _fake_response(429, {}, {"Retry-After": "1"})
        return _fake_response(201, {"ok": True})

    monkeypatch.setattr(client.session, "post", fake_post)
    monkeypatch.setattr("qa.brain_client.time.sleep", lambda s: None)
    resp = client._post_with_retry("/simulations", {})
    assert calls["n"] == 3  # 前两次 429 重试，第三次成功
    assert resp.status_code == 201


def test_post_with_retry_throttled_raises(monkeypatch):
    """平台相关性子系统 THROTTLED：非普通限流，立即抛错停止批处理。"""
    client = BrainClient("t=abc")

    class ThrottledResp:
        status_code = 429
        headers = {}
        content = b'{"error": "THROTTLED: correlation subsystem busy"}'

        @property
        def text(self):
            return self.content.decode("utf-8", errors="replace")

    monkeypatch.setattr(
        client.session,
        "post",
        lambda path, headers=None, json=None, timeout=None: ThrottledResp(),
    )
    with pytest.raises(RuntimeError, match="THROTTLED"):
        client._post_with_retry("/simulations", {})


def test_parse_retry_after_branches():
    """Retry-After 三分支：浮点秒数原样返回；日期/None 回落 5.0 默认退避。"""
    from qa.brain_client import _parse_retry_after

    assert _parse_retry_after("12.5") == 12.5
    assert _parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 5.0
    assert _parse_retry_after(None) == 5.0
    assert _parse_retry_after("") == 5.0
