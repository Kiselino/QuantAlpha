"""qa status 命令：启动首查（环境判定 + cookie 验证 + 阶段检测）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from qa import knowledge
from qa.brain_client import BrainClient
from qa.config import AppConfig
from qa.paths import QaPaths
from qa.stage import StageInfo, get_stage, read_cookie


def _env_checks(paths: QaPaths) -> dict[str, bool]:
    """本地运行时依赖文件存在性检查（status 环境判定的输入）。"""
    return {
        "meta": paths.KNOWLEDGE_META_JSON.exists(),
        "fields": paths.KNOWLEDGE_FIELDS_JSON.exists(),
        "playbook": paths.PLAYBOOK.exists(),
        "failures": paths.FAILURES.exists(),
        "db": paths.DB.exists(),
        "cookie": paths.COOKIE.exists(),
    }


def _env_verdict(checks: dict[str, bool]) -> str:
    """本地环境四态判定（new_user / partial / reset / ready）。

    - meta 缺失 → new_user：首次运行引导 login → update-knowledge → run
    - meta 在但 cookie 缺 → partial：知识库已生成，补登录即可
    - meta+cookie 在但 db 缺 → reset：经验已清除（qa reset 后），无需重拉知识库
    - 其余 → ready
    """
    if not checks["meta"]:
        return "new_user"
    if not checks["cookie"]:
        return "partial"
    if not checks["db"]:
        return "reset"
    return "ready"


def _load_account_info(paths: QaPaths) -> dict[str, Any] | None:
    """读 secrets/account_info.json 离线阶段缓存（缺失/损坏返回 None）。"""
    if not paths.ACCOUNT_INFO.exists():
        return None
    try:
        data = json.loads(paths.ACCOUNT_INFO.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def _show_cached_stage(paths: QaPaths) -> None:
    """cookie 失效时展示 account_info.json 离线阶段缓存（标注来源）。"""
    cached = _load_account_info(paths)
    if cached:
        print(
            f"  账号阶段(离线缓存): 等级 {cached.get('level', '?')} / "
            f"资格 {'顾问' if cached.get('is_consultant') else '用户'} "
            f"（更新于 {str(cached.get('updated_at', ''))[:10]}）"
        )


def _save_account_info(paths: QaPaths, stage: StageInfo) -> None:
    """登录成功后写账户阶段摘要到 secrets/account_info.json。

    只存阶段摘要（level/资格/区域/语言/时间），不含密码与分数明细；
    status 在 cookie 失效时读作离线阶段缓存。
    """
    info = {
        "level": stage.level,
        "is_consultant": stage.is_consultant,
        "regions": list(stage.regions),
        "languages": list(stage.expression_languages),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    paths.ACCOUNT_INFO.parent.mkdir(parents=True, exist_ok=True)
    paths.ACCOUNT_INFO.write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def cmd_status(paths: QaPaths) -> int:
    """启动首查：本地环境判定 + cookie 验证 + 阶段检测 + 知识库一致性。

    status 只提示不代做登录——引导动作（qa login 等）由 agent 会话中执行。
    返回 1 仅当 cookie 检查失败（缺失/过期/网络不可达）。
    """
    checks = _env_checks(paths)
    verdict = _env_verdict(checks)
    guides = {
        "new_user": "首次运行：请依次运行 qa login → qa update-knowledge → qa run",
        "partial": "知识库已生成，请先 qa login",
        "reset": "经验已清除，可重新开始（无需重拉知识库）",
        "ready": "环境就绪",
    }
    print(f"[status] {guides[verdict]}")

    if not checks["meta"]:
        print(
            "  知识库: ❌ 未生成 → 请运行 `qa update-knowledge` "
            "按账户抓取字段知识（首次必做，数据仅存本地不上传）"
        )
    else:
        meta = knowledge.knowledge_status(paths)
        if meta is None or not checks["fields"]:
            print(
                "  知识库: ⚠️ meta 存在但 fields.json 缺失 → "
                "请运行 `qa update-knowledge --force` 重建"
            )
        else:
            print(
                f"  知识库: ✅ {meta.get('field_count', '?')} 字段 / "
                f"{meta.get('dataset_count', '?')} 数据集 / "
                f"区域 {', '.join(meta.get('regions', []))} "
                f"（生成于 {str(meta.get('generated_at', ''))[:10]}）"
            )

    if not checks["cookie"]:
        print("  cookie: ❌ cookie 不存在：请运行 qa login 或提供 Copy as cURL")
        return 1
    try:
        stage = get_stage(paths)
    except PermissionError:
        print("  cookie: ❌ cookie 已过期：请运行 qa login 重新认证")
        _show_cached_stage(paths)
        return 1
    except Exception as e:
        print(f"  cookie: ⚠️ 网络不可达，cookie 有效性未验证（已检查文件存在）: {e}")
        _show_cached_stage(paths)
        return 1

    # 等级与资格分离展示：level 是分数段位，非顾问资格（二者正交）
    print(f"  等级: {stage.level}（分数段位，非顾问资格）")
    print(f"  资格: {'顾问' if stage.is_consultant else '用户'}")
    print(f"  Genius 等级: {stage.genius_level or '—'}")
    print(f"  可用区域: {', '.join(stage.regions)}")
    print(f"  表达式语言: {', '.join(stage.expression_languages)}")
    print(f"  并发上限: {stage.max_concurrency}")
    print(f"  D0 可用: {'是' if stage.d0_available else '否'}")

    # 配额状态（六项检查之一）：网络异常时静默跳过该行，不改变 status 返回码
    try:
        rl = BrainClient(read_cookie(paths.COOKIE)).rate_limits()
    except Exception:
        pass
    else:
        daily = (
            f"每日剩余 {rl.daily_remaining}"
            if rl.daily_remaining is not None
            else "每日配额头缺失"
        )
        print(f"  配额: 分钟剩余 {rl.remaining_minute}/{rl.limit_minute}，{daily}")

    # 知识库一致性：fields meta 的资格快照 vs 当前资格，不符提示刷新。
    # 只比 is_consultant（决定字段/区域可用性的维度）——用户阶段内 BRONZE/SILVER/GOLD
    # 只是分数段位，不改变字段可用性，等级变化无需刷新知识库。
    if checks["meta"]:
        meta = knowledge.knowledge_status(paths) or {}
        meta_stage = meta.get("stage") or {}
        if bool(meta_stage.get("is_consultant")) != stage.is_consultant:
            print(
                "  知识库一致性: ⚠️ 与当前账号资格不符 → 建议 `qa update-knowledge --force` 刷新"
            )

    if paths.PENDING_SUBMITS.exists():
        try:
            n_pending = len(
                json.loads(paths.PENDING_SUBMITS.read_text(encoding="utf-8"))
            )
        except ValueError:
            n_pending = 0
        if n_pending:
            print(f"  待提交暂存: ⚠️ 有 {n_pending} 个已达标 alpha 暂存待提交")
    return 0


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa status（argparse 分发）。"""
    return cmd_status(paths)
