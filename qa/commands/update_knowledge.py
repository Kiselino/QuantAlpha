"""qa update-knowledge 命令：按账户抓取字段知识 → 写本地 experience/fields/。

命名避让 qa/knowledge.py（模块名冲突），故子包文件名为 update_knowledge.py。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from qa import knowledge
from qa.brain_client import BrainClient
from qa.commands._common import _require_cookie
from qa.config import AppConfig
from qa.knowledge import KnowledgeMissingError
from qa.paths import QaPaths
from qa.stage import get_stage


def cmd_update_knowledge(
    paths: QaPaths,
    regions_arg: str | None,
    pace: float = knowledge.BASE_PACE_SECONDS,
    force: bool = False,
) -> int:
    """按账户阶段抓取字段知识 → 写 experience/fields/（本地，gitignored 不上传）。

    force=False 且 24h 内已生成时跳过抓取（省配额与时间；顾问 12 区域重抓很贵）。
    """
    try:
        meta = knowledge.knowledge_status(paths)
    except KnowledgeMissingError:
        # meta.json 损坏（knowledge 统一抛错契约）：视为未生成，直接重抓自愈
        print("[update-knowledge] 本地知识库 meta 已损坏，重新抓取重建……")
        meta = None
    if meta and not force:
        generated = meta.get("generated_at")
        if generated:
            try:
                generated_dt = datetime.fromisoformat(generated)
                if datetime.now(timezone.utc) - generated_dt < timedelta(hours=24):
                    print(
                        f"[update-knowledge] 本地知识库 {generated[:16]} 已生成（24 小时内），"
                        "跳过抓取（--force 强制刷新）。"
                    )
                    return 0
            except ValueError:
                pass
    try:
        stage = get_stage(paths)
    except PermissionError:
        print("[update-knowledge] 登录失效：请 qa login 重新认证后重试")
        return 1
    except Exception as e:
        print(f"[update-knowledge] 阶段检测失败（需有效登录）: {e}")
        return 1
    regions = (
        [r.strip().upper() for r in regions_arg.split(",") if r.strip()]
        if regions_arg
        else list(stage.regions)
    )
    if not regions:
        print("[update-knowledge] 无可抓取区域。")
        return 1
    cookie = _require_cookie(paths, "update-knowledge")
    if cookie is None:
        return 1
    client = BrainClient(cookie)
    print(
        f"[update-knowledge] 按账户阶段（{'顾问' if stage.is_consultant else '用户'}）"
        f"抓取区域 {', '.join(regions)} 字段（限流节流，约 2 秒/请求）……"
    )
    try:
        meta = knowledge.build_local_knowledge(
            paths, client, regions, stage_info=stage, pace=pace
        )
    except PermissionError:
        print("[update-knowledge] 登录失效：请 qa login 重新认证后重试")
        return 1
    except (TimeoutError, RuntimeError) as e:
        print(f"[update-knowledge] 抓取失败: {e}")
        return 1
    print(
        f"[update-knowledge] ✅ 完成: {meta['field_count']} 字段 / "
        f"{meta['dataset_count']} 数据集 → {paths.KNOWLEDGE_FIELDS_DIR}"
    )
    print("[update-knowledge] 数据位于 gitignored 的 experience/，不会上传公开仓库。")
    return 0


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa update-knowledge（argparse 分发）。"""
    return cmd_update_knowledge(paths, args.regions, force=args.force)
