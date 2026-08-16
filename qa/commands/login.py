"""qa login 命令：账号密码登录 → 写入会话 cookie。"""

from __future__ import annotations

from qa import auth
from qa.commands.status import _save_account_info
from qa.config import AppConfig
from qa.paths import QaPaths
from qa.stage import get_stage


def _cmd_login(paths: QaPaths, username: str | None, password: str | None) -> int:
    """账号密码登录 → 写入 secrets/worldquant_cookies.txt。

    账号密码支持 --username/--password 参数或交互输入（getpass 不回显）。
    凭据不落盘、不进审计；仅写入的 cookie 存于 gitignored 的 secrets/。
    """
    try:
        import getpass

        email = username or input("BRAIN 账号邮箱: ").strip()
        pwd = password or getpass.getpass("BRAIN 账号密码: ")
        if not email or not pwd:
            print("[login] 账号或密码为空。")
            return 1
        cookie = auth.login(email, pwd)
    except auth.PersonaRequired as e:
        print(f"[login] {e}")
        return 1
    except auth.AuthError as e:
        print(f"[login] {e}")
        return 1
    except Exception as e:
        print(f"[login] 登录失败: {e}")
        return 1

    paths.COOKIE.parent.mkdir(parents=True, exist_ok=True)
    paths.COOKIE.write_text(cookie, encoding="utf-8")
    print(f"[login] 登录成功，会话 cookie 已写入 {paths.COOKIE}")
    print("[login] 验证会话……")
    try:
        stage = get_stage(paths)
        _save_account_info(paths, stage)
        # 等级与资格分离展示（level 是分数段位，非顾问资格）
        print(f"  等级: {stage.level}（分数段位，非顾问资格）")
        print(f"  资格: {'顾问' if stage.is_consultant else '用户'}")
        return 0
    except Exception as e:
        print(f"[login] cookie 已写入但阶段检测失败: {e}")
        return 1


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa login（argparse 分发）。"""
    return _cmd_login(paths, args.username, args.password)
