"""HTTP 传输层：BASE_URL / 会话过期文案 / 带退避的重试 GET 单点实现。

auth（登录）、brain_client（模拟/知识库抓取/相关门）、stage（阶段检测）
共用同一 BASE_URL 与会话过期判定，避免三处常量与文案漂移。
行为语义以 brain_client 原 _retry_get 为准（429 退避 + 空 body/非 JSON
重试防御，见下注释；平台相关门等端点偶发空 body，直接调用正常）。
"""

from __future__ import annotations

import time
from typing import Any, Callable

import requests

BASE_URL = "https://api.worldquantbrain.com"

SESSION_EXPIRED_MESSAGE = "BRAIN 会话无效或已过期，请更新 cookie 文件。"

_THROTTLED_MESSAGE = "平台相关性子系统繁忙（THROTTLED），请稍后重试。"


def parse_retry_after(value: str | None) -> float:
    """Retry-After 可能是浮点秒数字符串（实测）或 HTTP 日期。"""
    if not value:
        return 5.0
    try:
        return float(value)
    except ValueError:
        return 5.0


def sleep_on_429(resp: requests.Response) -> None:
    """429 限流处理（GET/POST 共用）：THROTTLED 抛错，常规限流按 Retry-After 退避。

    实测区分：平台相关性子系统卡死时响应体含 THROTTLED → 非普通限流，暂停批处理。
    """
    if "THROTTLED" in resp.text:
        raise RuntimeError(_THROTTLED_MESSAGE)
    time.sleep(min(parse_retry_after(resp.headers.get("Retry-After")), 120.0))


def retry_get(
    get: Callable[..., requests.Response],
    path: str,
    base_url: str = BASE_URL,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
    timeout: int = 30,
    retry_delay: float = 5.0,
) -> tuple[int, Any, dict[str, Any]]:
    """带 429 退避的 GET（区分常规限流与 THROTTLED），返回 (状态码, JSON, 头)。

    空响应/非 JSON body 视为平台瞬时异常，重试而非抛 JSONDecodeError
    （实测：相关门等端点偶发空 body，直接调用正常）。
    401/403 抛 PermissionError（会话过期，文案单点）；耗尽 attempts 抛 TimeoutError。
    `get` 为执行 GET 的可调用（如 requests.get 或 session.get），便于调用方注入头/cookie。
    """
    for _ in range(attempts):
        kwargs: dict[str, Any] = {"timeout": timeout}
        if headers:
            kwargs["headers"] = headers
        if params:
            kwargs["params"] = params
        resp = get(f"{base_url}{path}", **kwargs)
        if resp.status_code == 429:
            sleep_on_429(resp)
            continue
        if resp.status_code in (401, 403):
            raise PermissionError(SESSION_EXPIRED_MESSAGE)
        resp.raise_for_status()
        if not resp.content:
            time.sleep(retry_delay)
            continue
        try:
            return resp.status_code, resp.json(), dict(resp.headers)
        except ValueError:
            time.sleep(retry_delay)
    raise TimeoutError(f"GET {path} 重试 {attempts} 次后仍失败")
