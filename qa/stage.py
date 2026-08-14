"""账号阶段检测：读 cookie → GET /users/self → 判定 用户/顾问 阶段。

输出 StageInfo（等级/顾问状态/可用区域/并发/表达式语言/D0 可用性），
供 `qa status` 启动首查与后续动态配置使用（顾问解锁 12 区域、
PYTHON/ML 语言等；设计 §3.0）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from qa.paths import QaPaths

BASE_URL = "https://api.worldquantbrain.com"

# 非顾问 vs 顾问的变量映射（设计 §3.0）
_CONSULTANT_REGIONS = [
    "USA", "EUR", "ASI", "CHN", "GLB", "IND", "JPN",
    "KOR", "TWN", "AUS", "CAN", "BRA",
]


@dataclass(frozen=True)
class StageInfo:
    """账号阶段检测结果。"""

    level: str                       # BRONZE / SILVER / GOLD
    is_consultant: bool
    genius_level: str | None = None
    regions: list[str] = field(default_factory=lambda: ["USA"])
    max_concurrency: int = 3
    expression_languages: list[str] = field(default_factory=lambda: ["FASTEXPR"])
    d0_available: bool = False


def read_cookie(path: Path) -> str:
    """读取会话 cookie（secrets/worldquant_cookies.txt）。

    cookie 文件由 agent 维护：用户只需把 BRAIN 请求的 "Copy as cURL"
    内容发给 agent，agent 解析出 Cookie 后写入本文件（纯 Cookie 头值）。
    """
    if not path.exists():
        raise FileNotFoundError(
            f"未找到 cookie 文件: {path}。\n"
            "请把 api.worldquantbrain.com 请求的 Copy as cURL 内容发给 agent，\n"
            "由 agent 解析并写入本文件（详见 README）。"
        )
    return path.read_text(encoding="utf-8").strip()


def fetch_self(cookie: str, base_url: str = BASE_URL) -> dict[str, Any]:
    """GET /users/self —— 阶段检测的数据来源。"""
    resp = requests.get(
        f"{base_url}/users/self",
        headers={"Cookie": cookie, "Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def detect_stage(self_data: dict[str, Any]) -> StageInfo:
    """从 /users/self 响应判定阶段（实测：level/geniusLevel/consultant 字段）。"""
    is_consultant = (
        self_data.get("consultant") is not None
        or self_data.get("geniusLevel") is not None
    )
    genius = self_data.get("geniusLevel")
    genius_name = genius.get("name") if isinstance(genius, dict) else None
    regions = _CONSULTANT_REGIONS if is_consultant else ["USA"]
    langs = ["FASTEXPR", "PYTHON", "ML"] if is_consultant else ["FASTEXPR"]
    return StageInfo(
        level=self_data.get("level", "UNKNOWN"),
        is_consultant=is_consultant,
        genius_level=genius_name,
        regions=regions,
        max_concurrency=3,
        expression_languages=langs,
        d0_available=is_consultant or (self_data.get("level") in ("SILVER", "GOLD")),
    )


def get_stage(paths: QaPaths) -> StageInfo:
    """组合流程：读 cookie → 拉取 users/self → 判定阶段。"""
    cookie = read_cookie(paths.COOKIE)
    self_data = fetch_self(cookie)
    return detect_stage(self_data)
