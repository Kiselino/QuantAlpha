"""brain_client 单测：mock HTTP（限流头解析 / 模拟 Location / 轮询 / 相关性）。"""

from __future__ import annotations

import json

import pytest

from qa.brain_client import BrainClient, RateLimits, SimulationResult

BASE = "https://api.worldquantbrain.com"


def _fake_response(status_code, payload=None, headers=None):
    class Resp:
        def __init__(self):
            self.status_code = status_code
            self.headers = headers or {}
            self._payload = payload

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
            "checks": [{"name": "SHARPE", "result": "PASS", "limit": 1.25, "value": 1.5}],
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
            ["a1", None, "EQUITY", "USA", "TOP3000", 0.132, 1.62, 0.071, 0.12, 1.22, 0.002],
            ["a2", None, "EQUITY", "USA", "TOP3000", 0.064, 1.52, 0.09, 0.015, 1.31, 0.009],
        ],
        "min": 0.057,
        "max": 0.125,
    }

    def fake_get(path, headers=None, timeout=None, params=None):
        assert path == f"{BASE}/alphas/XYZ/correlations/self"
        return _fake_response(200, payload)

    monkeypatch.setattr(client.session, "get", fake_get)
    assert client.correlations_self("XYZ") == 0.125
