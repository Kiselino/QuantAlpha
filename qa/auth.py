"""账号密码登录：POST /authentication（HTTP Basic Auth）→ 提取 t= JWT cookie。

登录机制（调研实证）：
- 端点 POST /authentication，凭据走 HTTP Basic Auth（email 为用户名、password 为密码）
- 成功 201/200 → 响应 Set-Cookie 头携带会话 JWT（t=...），后续请求凭此认证
- 无验证码（Altcha PoW 仅用于注册 POST /users）；例外是 Persona 人机验证
  （401 + WWW-Authenticate: persona），需人工完成，本模块检测后抛异常
- 会话约 4 小时（token.expiry ≈ 14222s），过期后重新登录即可

安全约定：账号密码只通过参数/交互传入，永不写入磁盘或审计日志；
写入的 cookie 文件位于 gitignored 的 secrets/ 目录。
"""

from __future__ import annotations

import requests

BASE_URL = "https://api.worldquantbrain.com"


class AuthError(RuntimeError):
    """登录失败（凭据错误/网络/未知响应）。"""


class PersonaRequired(AuthError):
    """账号触发 Persona 人机验证（WWW-Authenticate: persona），无法全自动登录。"""


def login(email: str, password: str, base_url: str = BASE_URL) -> str:
    """账号密码登录，返回会话 Cookie 字符串（"t=<JWT>"）。

    凭据仅在请求时使用，不落盘。401 凭据错误抛 AuthError；
    触发 Persona 验证抛 PersonaRequired（需人工处理）。
    """
    resp = requests.post(
        f"{base_url}/authentication",
        auth=(email, password),
        timeout=60,
    )
    if resp.status_code in (200, 201):
        cookie = _extract_t_cookie(resp)
        if not cookie:
            raise AuthError(f"登录响应未携带 t= 会话 cookie（HTTP {resp.status_code}）")
        return cookie
    if resp.status_code == 401:
        auth_header = resp.headers.get("WWW-Authenticate", "").lower()
        if "persona" in auth_header:
            inquiry = ""
            try:
                inquiry = str((resp.json() or {}).get("inquiry", ""))
            except ValueError:
                pass  # Persona 响应无 inquiry 字段属正常（401 拒绝页非 JSON），按空串处理
            raise PersonaRequired(
                "账号触发 Persona 人机验证，无法全自动登录。"
                "请打开 https://inquiry.withpersona.com 完成身份验证后重试"
                + (f"（inquiry: {inquiry}）" if inquiry else "")
            )
        raise AuthError(
            f"登录失败：邮箱或密码错误（HTTP 401）。"
            f"请检查账号密码，或改用浏览器复制 Cookie 的方式（README）。"
        )
    resp.raise_for_status()
    raise AuthError(f"登录失败：未知响应 HTTP {resp.status_code}")


def _extract_t_cookie(resp: requests.Response) -> str:
    """从 Set-Cookie 头提取会话 JWT（t=...）；无则返回空串。

    requests 会把多个 Set-Cookie 合并为逗号分隔的单个值，
    但 JWT 不含逗号，按分号/逗号切分后找 t= 前缀即可。
    """
    raw = resp.headers.get("set-cookie", "")
    for part in raw.replace(",", ";").split(";"):
        part = part.strip()
        if part.startswith("t="):
            return part
    return ""
