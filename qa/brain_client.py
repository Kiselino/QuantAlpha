"""BRAIN API 客户端：模拟 / 轮询 / 限流 / 相关性。

本地零回测：所有性能测试通过本客户端调用平台 API（P1）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests

BASE_URL = "https://api.worldquantbrain.com"


@dataclass
class RateLimits:
    """分钟级限流状态（来自响应头；实测 30 请求/分钟）。"""

    remaining_minute: int = 30
    limit_minute: int = 30
    reset_seconds: int = 0


@dataclass
class SimulationResult:
    """一次模拟的最终结果（轮询完成后组装）。

    status：平台状态值（实测为 COMPLETE，非 COMPLETED）。
    alpha_id：COMPLETE 后存在，用于拉取 alpha 详情（is 数据）。
    """

    sim_id: str
    status: str                     # PENDING / COMPLETE / ERROR / FAILED
    alpha_id: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class BrainClient:
    """BRAIN API 封装。cookie 读自 secrets/worldquant_cookies.txt。"""

    def __init__(
        self,
        cookie: str,
        base_url: str = BASE_URL,
        timeout: int = 30,
        poll_interval: float = 5.0,
    ):
        self.cookie = cookie
        self.base_url = base_url
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.session = requests.Session()
        self.session.headers.update(
            {"Cookie": cookie, "Accept": "application/json"}
        )

    # ---- 基础请求 ----
    def _retry_get(
        self, path: str, params: dict[str, Any] | None = None, attempts: int = 3
    ) -> tuple[int, dict[str, Any] | list[Any], dict[str, Any]]:
        """带 429 退避的 GET（区分常规限流与 THROTTLED）。"""
        for attempt in range(attempts):
            resp = self.session.get(
                f"{self.base_url}{path}", params=params, timeout=self.timeout
            )
            if resp.status_code == 429:
                body = resp.text
                if "THROTTLED" in body:
                    raise RuntimeError(
                        "平台相关性子系统繁忙（THROTTLED），请稍后重试。"
                    )
                retry = _parse_retry_after(resp.headers.get("Retry-After"))
                time.sleep(min(retry, 120.0))
                continue
            if resp.status_code in (401, 403):
                raise PermissionError(
                    "BRAIN 会话无效或已过期，请更新 cookie 文件。"
                )
            resp.raise_for_status()
            return resp.status_code, resp.json(), dict(resp.headers)
        raise TimeoutError(f"GET {path} 重试 {attempts} 次后仍被限流")

    # ---- 模拟 ----
    def simulate(self, code: str, settings: dict[str, Any]) -> str:
        """POST /simulations → 返回 sim_id（来自 Location 头）。

        平台实测要求：regular 为字符串；settings 必含 unitHandling/visualization。
        429 常规限流按 Retry-After 退避重试（并发模拟时易触发）；THROTTLED 抛错。
        """
        payload = {"type": "REGULAR", "settings": settings, "regular": code}
        for attempt in range(3):
            resp = self.session.post(
                f"{self.base_url}/simulations", json=payload, timeout=self.timeout
            )
            if resp.status_code == 429:
                body = resp.text
                if "THROTTLED" in body:
                    raise RuntimeError("平台相关性子系统繁忙（THROTTLED），请稍后重试。")
                time.sleep(min(_parse_retry_after(resp.headers.get("Retry-After")), 120.0))
                continue
            if resp.status_code in (401, 403):
                raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")
            if resp.status_code == 400:
                raise ValueError(f"模拟参数被平台拒绝: {resp.text[:300]}")
            resp.raise_for_status()
            location = resp.headers.get("Location", "")
            return location.rsplit("/", 1)[-1]
        raise TimeoutError(f"POST /simulations 重试 3 次后仍被限流")

    def poll_simulation(self, sim_id: str, max_wait: float = 600.0) -> SimulationResult:
        """轮询模拟直到 COMPLETE/ERROR 或超时。

        平台状态值为 COMPLETE（非 COMPLETED）；is 数据在返回的 alpha 详情中。
        """
        deadline = time.time() + max_wait
        while time.time() < deadline:
            _, data, _ = self._retry_get(f"/simulations/{sim_id}")
            if not isinstance(data, dict):  # 防御：平台异常响应（非对象）按 PENDING 继续轮询
                time.sleep(self.poll_interval)
                continue
            status = data.get("status", "PENDING")
            if status in ("COMPLETE", "COMPLETED", "ERROR", "FAILED"):
                alpha_id = data.get("alpha")
                is_data = {}
                if status in ("COMPLETE", "COMPLETED") and alpha_id:
                    _, alpha_detail, _ = self._retry_get(f"/alphas/{alpha_id}")
                    if isinstance(alpha_detail, dict):
                        is_data = alpha_detail.get("is") or {}
                return SimulationResult(
                    sim_id=sim_id,
                    status=status,
                    alpha_id=alpha_id,
                    checks=is_data.get("checks", []),
                    metrics={
                        k: is_data.get(k)
                        for k in (
                            "sharpe",
                            "fitness",
                            "turnover",
                            "returns",
                            "drawdown",
                            "margin",
                        )
                    },
                    raw=data,
                )
            time.sleep(self.poll_interval)
        raise TimeoutError(f"模拟 {sim_id} 在 {max_wait}s 内未完成")

    # ---- 限流 ----
    def rate_limits(self) -> RateLimits:
        """读取限流头（实测：x-ratelimit-*-minute，30/分）。"""
        _, _, headers = self._retry_get("/users/self")
        return RateLimits(
            remaining_minute=_int_or(headers.get("x-ratelimit-remaining-minute"), 30),
            limit_minute=_int_or(headers.get("x-ratelimit-limit-minute"), 30),
            reset_seconds=_int_or(headers.get("ratelimit-reset"), 0),
        )

    # ---- 相关性（提交前免费门）----
    def correlations_self(self, alpha_id: str) -> float:
        """GET /alphas/{id}/correlations/self → 返回 max correlation。

        实测返回 {schema, records, min, max}；max<0.7 才应提交。
        """
        _, data, _ = self._retry_get(f"/alphas/{alpha_id}/correlations/self")
        if isinstance(data, dict) and data.get("max") is not None:
            return float(data["max"])
        return 0.0


def _parse_retry_after(value: str | None) -> float:
    """Retry-After 可能是浮点秒数字符串（实测）或 HTTP 日期。"""
    if not value:
        return 5.0
    try:
        return float(value)
    except ValueError:
        return 5.0


def _int_or(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
