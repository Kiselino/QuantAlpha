"""stage 单测：cookie 读取 / users/self 阶段判定（BRONZE / 顾问）/ 请求头 + 防御。"""

from __future__ import annotations

import pytest
import requests

from qa.paths import QaPaths
from qa.stage import detect_stage, fetch_self, read_cookie

BRONZE_SELF = {
    "id": "XX12345",
    "level": "BRONZE",
    "geniusLevel": None,
    "consultant": None,
    "onboarding": None,
}

CONSULTANT_SELF = {
    "id": "XX99999",
    "level": "GOLD",
    "geniusLevel": {"name": "Master"},
    "consultant": {"status": "ACTIVE"},
    "onboarding": {"stage": "COMPLETED"},
}


def _resp(status_code, payload=None, headers=None, raw=b""):
    """构造 mock GET 响应（含 transport.retry_get 依赖的 content/headers/text）。"""

    class Resp:
        def __init__(self):
            self.status_code = status_code
            self.headers = headers or {}
            self.content = raw if raw else (b"{}" if payload is not None else b"")

        @property
        def text(self):
            return self.content.decode("utf-8", errors="replace")

        def json(self):
            return payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    return Resp()


def _patch_requests_get(monkeypatch, responses: list) -> list:
    """monkeypatch requests.get 依序返回 responses（耗尽后重复最后一条）。"""
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers})
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


def test_read_cookie(tmp_qa):
    p = QaPaths(tmp_qa)
    p.COOKIE.write_text("t=abc123; session=x", encoding="utf-8")
    assert read_cookie(p.COOKIE) == "t=abc123; session=x"


def test_read_cookie_missing(tmp_qa):
    p = QaPaths(tmp_qa)
    with pytest.raises(FileNotFoundError):
        read_cookie(p.COOKIE)


def test_detect_stage_bronze():
    s = detect_stage(BRONZE_SELF)
    assert s.level == "BRONZE"
    assert s.is_consultant is False
    assert s.genius_level is None
    assert s.max_concurrency == 3
    assert s.regions == ["USA"]
    assert s.d0_available is False


def test_detect_stage_consultant():
    s = detect_stage(CONSULTANT_SELF)
    assert s.is_consultant is True
    assert s.genius_level == "Master"
    assert s.max_concurrency == 3
    assert len(s.regions) > 1
    assert s.d0_available is True
    assert "PYTHON" in s.expression_languages


def test_fetch_self_uses_cookie(monkeypatch):
    calls = _patch_requests_get(monkeypatch, [_resp(200, BRONZE_SELF)])
    data = fetch_self("t=abc")
    assert data["level"] == "BRONZE"
    assert "Cookie" in calls[0]["headers"]
    assert calls[0]["headers"]["Cookie"] == "t=abc"
    assert calls[0]["headers"]["Accept"] == "application/json"


def test_fetch_self_raises_permission_error_on_401(monkeypatch):
    """401 → PermissionError（与 brain_client 会话失效约定统一，供 status 分支）。"""
    _patch_requests_get(monkeypatch, [_resp(401)])
    with pytest.raises(PermissionError, match="会话"):
        fetch_self("t=expired")


def test_fetch_self_raises_permission_error_on_403(monkeypatch):
    """403 同样视为会话失效（部分账号阶段接口返回 403 而非 401）。"""
    _patch_requests_get(monkeypatch, [_resp(403)])
    with pytest.raises(PermissionError, match="会话"):
        fetch_self("t=expired")


# ---- 防御：与 brain_client._retry_get 相同的 429 退避 / 空 body 重试语义 ----


def test_fetch_self_retries_after_429(monkeypatch):
    """429 限流退避后重试成功（与 brain_client 同语义）。"""
    monkeypatch.setattr("qa.transport.time.sleep", lambda s: None)
    _patch_requests_get(
        monkeypatch,
        [
            _resp(429, headers={"Retry-After": "0"}),
            _resp(200, BRONZE_SELF),
        ],
    )
    data = fetch_self("t=abc")
    assert data["level"] == "BRONZE"


def test_fetch_self_retries_after_empty_body(monkeypatch):
    """空 body（平台瞬时异常）→ 重试而非抛 JSONDecodeError（实测偶发）。"""
    monkeypatch.setattr("qa.transport.time.sleep", lambda s: None)
    _patch_requests_get(
        monkeypatch,
        [
            _resp(200, raw=b""),  # 空 body
            _resp(200, BRONZE_SELF),
        ],
    )
    data = fetch_self("t=abc")
    assert data["level"] == "BRONZE"


def test_fetch_self_permission_error_on_persistent_401(monkeypatch):
    """持续 401（会话过期）→ PermissionError，不因重试循环吞掉。"""
    monkeypatch.setattr("qa.transport.time.sleep", lambda s: None)
    _patch_requests_get(monkeypatch, [_resp(401)])
    with pytest.raises(PermissionError, match="会话无效或已过期"):
        fetch_self("t=expired")


def test_fetch_self_raises_timeout_after_retries_exhausted(monkeypatch):
    """空 body 重试耗尽 → TimeoutError（不再静默返回残缺数据）。"""
    monkeypatch.setattr("qa.transport.time.sleep", lambda s: None)
    _patch_requests_get(monkeypatch, [_resp(200, raw=b"")])
    with pytest.raises(TimeoutError, match="重试"):
        fetch_self("t=abc")
