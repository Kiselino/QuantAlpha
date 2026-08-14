"""stage 单测：cookie 读取 / users/self 阶段判定（BRONZE / 顾问）/ 请求头。"""

from __future__ import annotations

import pytest

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
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return BRONZE_SELF

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    import requests

    def fake_get(url, headers, timeout):
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(requests, "get", fake_get)
    data = fetch_self("t=abc")
    assert data["level"] == "BRONZE"
    assert "Cookie" in captured["headers"]
    assert captured["headers"]["Cookie"] == "t=abc"
