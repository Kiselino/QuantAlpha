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
    """限流状态（来自响应头）。

    minute：分钟级（实测 30 请求/分钟，x-ratelimit-*-minute）。
    daily：每日模拟配额（x-ratelimit-limit/-remaining/-reset，无 -minute 后缀；
    社区工具实测存在，数值随账户阶段变化；缺失时 None，不拦截——靠平台
    错误码/429 兜底，v1.6 起无本地预算）。
    """

    remaining_minute: int = 30
    limit_minute: int = 30
    reset_seconds: int = 0
    daily_limit: int | None = None
    daily_remaining: int | None = None
    daily_reset: int | None = None


@dataclass
class SimulationResult:
    """一次模拟的最终结果（轮询完成后组装）。

    status：平台状态值（实测为 COMPLETE，非 COMPLETED）。
    alpha_id：COMPLETE 后存在，用于拉取 alpha 详情（is 数据）。
    """

    sim_id: str
    status: str  # PENDING / COMPLETE / ERROR / FAILED
    alpha_id: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class SubmissionRejected(Exception):
    """平台提交检查未过（HTTP 403 + is.checks 载荷），非会话问题。"""

    def __init__(self, checks: list[dict[str, Any]]):
        self.checks = checks
        super().__init__("提交被平台拒绝（检查未过）")


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
        self.session.headers.update({"Cookie": cookie, "Accept": "application/json"})

    # ---- 基础请求 ----
    def get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        """GET 并返回 JSON 载荷（带 429 退避/空响应防御）。供知识库抓取等批量读操作。"""
        _, data, _ = self._retry_get(path, params=params)
        return data

    def _retry_get(
        self, path: str, params: dict[str, Any] | None = None, attempts: int = 3
    ) -> tuple[int, dict[str, Any] | list[Any], dict[str, Any]]:
        """带 429 退避的 GET（区分常规限流与 THROTTLED）。

        空响应/非 JSON body 视为平台瞬时异常，重试而非抛 JSONDecodeError
        （实测：相关门等端点偶发空 body，直接调用正常）。
        """
        for attempt in range(attempts):
            resp = self.session.get(
                f"{self.base_url}{path}", params=params, timeout=self.timeout
            )
            if resp.status_code == 429:
                _sleep_on_429(resp)
                continue
            if resp.status_code in (401, 403):
                raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")
            resp.raise_for_status()
            if not resp.content:
                time.sleep(self.poll_interval)
                continue
            try:
                return resp.status_code, resp.json(), dict(resp.headers)
            except ValueError:
                time.sleep(self.poll_interval)
        raise TimeoutError(f"GET {path} 重试 {attempts} 次后仍失败")

    # ---- 模拟 ----
    def _post_with_retry(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        rejection_ok: bool = False,
    ) -> requests.Response:
        """带 429 退避的 POST（THROTTLED 抛错 / 401-403 抛 PermissionError）。

        返回成功（非限流/非鉴权错误）响应对象；重试 3 次仍被限流抛 TimeoutError。
        调用方负责 4xx 语义处理（如 400 参数拒绝）与成功响应解析。
        rejection_ok=True：提交等业务端点 403 携带检查载荷（is.checks）时返回响应
        由调用方解析拒绝原因，而非误报会话过期。
        """
        for _ in range(3):
            resp = self.session.post(
                f"{self.base_url}{path}", json=payload, timeout=self.timeout
            )
            if resp.status_code == 429:
                _sleep_on_429(resp)
                continue
            if resp.status_code in (401, 403):
                if rejection_ok and resp.status_code == 403 and _has_is_checks(resp):
                    return resp
                raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")
            return resp
        raise TimeoutError(f"POST {path} 重试 3 次后仍被限流")

    def simulate(self, code: str, settings: dict[str, Any]) -> str:
        """POST /simulations → 返回 sim_id（来自 Location 头）。

        平台实测要求：regular 为字符串；settings 必含 unitHandling/visualization。
        每日配额头由调用方统一通过 rate_limits() 读取（v1.6：不在此写共享状态，
        避免并发写竞态）。
        """
        resp = self._post_with_retry(
            "/simulations", {"type": "REGULAR", "settings": settings, "regular": code}
        )
        if resp.status_code == 400:
            raise ValueError(f"模拟参数被平台拒绝: {resp.text[:300]}")
        resp.raise_for_status()
        location = resp.headers.get("Location", "")
        return location.rsplit("/", 1)[-1]

    def poll_simulation(self, sim_id: str, max_wait: float = 600.0) -> SimulationResult:
        """轮询模拟直到 COMPLETE/ERROR 或超时。

        平台状态值为 COMPLETE（非 COMPLETED）；is 数据在返回的 alpha 详情中。
        """
        deadline = time.time() + max_wait
        while time.time() < deadline:
            _, data, _ = self._retry_get(f"/simulations/{sim_id}")
            if not isinstance(
                data, dict
            ):  # 防御：平台异常响应（非对象）按 PENDING 继续轮询
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
        """读取限流头（分钟级实测：x-ratelimit-*-minute 30/分；每日配额无后缀头）。"""
        _, _, headers = self._retry_get("/users/self")
        return RateLimits(
            remaining_minute=_int_or(headers.get("x-ratelimit-remaining-minute"), 30),
            limit_minute=_int_or(headers.get("x-ratelimit-limit-minute"), 30),
            reset_seconds=_int_or(headers.get("ratelimit-reset"), 0),
            daily_limit=_int_or_none(headers.get("x-ratelimit-limit")),
            daily_remaining=_int_or_none(headers.get("x-ratelimit-remaining")),
            daily_reset=_int_or_none(headers.get("x-ratelimit-reset")),
        )

    # ---- 相关性（提交前免费门）----
    def correlations_self(self, alpha_id: str) -> float:
        """GET /alphas/{id}/correlations/self → 返回 max correlation。

        实测返回 {schema, records, min, max}；max<0.7 才应提交。
        fail-closed：响应缺少 max 时抛错，不允许静默返回 0.0 放行提交。
        """
        _, data, _ = self._retry_get(f"/alphas/{alpha_id}/correlations/self")
        if isinstance(data, dict) and data.get("max") is not None:
            return float(data["max"])
        raise RuntimeError(
            f"相关门响应异常（缺少 max correlation），中止提交流程: {str(data)[:200]}"
        )

    # ---- 提交 ----
    def submit(self, alpha_id: str) -> dict[str, Any]:
        """POST /alphas/{id}/submit → 提交 alpha，返回平台响应。

        需先经 correlations_self 免费相关门确认（max<0.7）再提交。
        平台以 403 + is.checks 载荷拒绝未过检查的提交 → 抛 SubmissionRejected。
        """
        resp = self._post_with_retry(f"/alphas/{alpha_id}/submit", rejection_ok=True)
        if resp.status_code == 403:
            try:
                body = resp.json()
                checks = (body.get("is") or {}).get("checks", [])
            except ValueError:
                checks = []
            raise SubmissionRejected(checks)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"status": resp.status_code, "text": resp.text}

    def get_alpha(self, alpha_id: str) -> dict[str, Any]:
        """GET /alphas/{id} → alpha 详情（提交后回查 status 是否 ACTIVE）。"""
        _, data, _ = self._retry_get(f"/alphas/{alpha_id}")
        return data if isinstance(data, dict) else {}


def _has_is_checks(resp: requests.Response) -> bool:
    """提交拒绝载荷判定：403 + JSON body 含 is.checks 键。

    比嗅探 '"is"' 子串稳定：必须能解析出 is.checks 结构才判为
    SubmissionRejected（否则按会话过期处理），避免误判误报。
    """
    try:
        body = resp.json()
    except ValueError:
        return False
    checks = (body.get("is") or {}) if isinstance(body, dict) else None
    return isinstance(checks, dict) and "checks" in checks


def _sleep_on_429(resp: requests.Response) -> None:
    """429 限流处理（GET/POST 共用）：THROTTLED 抛错，常规限流按 Retry-After 退避。

    实测区分：平台相关性子系统卡死时响应体含 THROTTLED → 非普通限流，暂停批处理。
    """
    if "THROTTLED" in resp.text:
        raise RuntimeError("平台相关性子系统繁忙（THROTTLED），请稍后重试。")
    time.sleep(min(_parse_retry_after(resp.headers.get("Retry-After")), 120.0))


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


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
