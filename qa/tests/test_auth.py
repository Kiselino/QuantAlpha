"""auth 单测：登录成功（提取 t= cookie）/ 凭据错误 / Persona 验证 / 无 cookie。"""

from __future__ import annotations

import pytest
import requests

from qa import auth


def _fake_post(status: int, *, set_cookie: str = "", headers: dict | None = None, json_body: dict | None = None):
    """构造 mock 登录响应。"""

    def fake_post(url, auth=None, timeout=60):
        resp = requests.Response()
        resp.status_code = status
        resp.url = url
        resp.request = requests.Request("POST", url).prepare()
        if set_cookie:
            resp.headers["set-cookie"] = set_cookie
        if headers:
            resp.headers.update(headers)
        resp._content = (
            __import__("json").dumps(json_body or {}).encode()
        )
        return resp

    return fake_post


def test_login_success_extracts_t_cookie(monkeypatch):
    monkeypatch.setattr(
        requests, "post",
        _fake_post(201, set_cookie="t=eyJhbGciOiJIUzI1NiJ9; Path=/; Secure"),
    )
    cookie = auth.login("user@example.com", "secret")
    assert cookie == "t=eyJhbGciOiJIUzI1NiJ9"


def test_login_200_also_accepted(monkeypatch):
    monkeypatch.setattr(
        requests, "post",
        _fake_post(200, set_cookie="t=abc123; Path=/; HttpOnly"),
    )
    cookie = auth.login("user@example.com", "secret")
    assert cookie == "t=abc123"


def test_login_multiple_set_cookie_headers(monkeypatch):
    """多 Set-Cookie（逗号合并）时仍能提取 t=。"""
    monkeypatch.setattr(
        requests, "post",
        _fake_post(
            201,
            set_cookie="__ga=GA1.1.1.1; Path=/; Domain=x.com, t=eyJ0eXAiOiJKV1Q; Path=/",
        ),
    )
    cookie = auth.login("user@example.com", "secret")
    assert cookie == "t=eyJ0eXAiOiJKV1Q"


def test_login_invalid_credentials_raises(monkeypatch):
    monkeypatch.setattr(
        requests, "post",
        _fake_post(401, json_body={"detail": "INVALID_CREDENTIALS"}),
    )
    with pytest.raises(auth.AuthError, match="邮箱或密码错误"):
        auth.login("user@example.com", "wrong")


def test_login_persona_raises(monkeypatch):
    monkeypatch.setattr(
        requests, "post",
        _fake_post(
            401,
            headers={"WWW-Authenticate": "persona"},
            json_body={"inquiry": "inq_2ABC123XYZdummy"},
        ),
    )
    with pytest.raises(auth.PersonaRequired, match="Persona"):
        auth.login("user@example.com", "secret")


def test_login_missing_cookie_raises(monkeypatch):
    monkeypatch.setattr(
        requests, "post",
        _fake_post(201, set_cookie="__ga=GA1.1.1.1; Path=/"),
    )
    with pytest.raises(auth.AuthError, match="未携带 t="):
        auth.login("user@example.com", "secret")
