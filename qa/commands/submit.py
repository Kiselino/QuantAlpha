"""qa submit 命令：人工确认后提交 alpha（提交前展示检查 + 回查 ACTIVE）。"""

from __future__ import annotations

from qa.brain_client import BrainClient, SubmissionRejected
from qa.commands._common import _remove_pending, _sediment_failure, _sediment_lesson
from qa.config import AppConfig
from qa.paths import QaPaths
from qa.stage import read_cookie
from qa.store import Store


def _cmd_submit(paths: QaPaths, alpha_id: str, yes: bool = False) -> int:
    """人工确认后提交 alpha（合规红线：必须展示检查结果 + 用户显式确认）。

    流程：读本地记录 → 展示全部检查 + 免费相关门 → 交互确认 → 提交 → 回查 ACTIVE。
    alpha_id 为本地 expr_hash（alphas 表主键）；平台 alpha_id 取自模拟结果。
    --yes 供 agent 代提交：用户已在对话中显式确认后传入；相关门检查不绕过。
    """
    try:
        cookie = read_cookie(paths.COOKIE)
    except FileNotFoundError as e:
        print(f"[submit] 错误: {e}")
        return 1
    store = Store(paths.DB)
    alpha = next((a for a in store.list_alphas() if a["id"] == alpha_id), None)
    if alpha is None:
        print(f"[submit] 未找到 alpha: {alpha_id}（可用 `qa report` 查看候选）")
        return 1

    sims = store.list_simulations(alpha_id)
    if not sims:
        print(f"[submit] 该候选尚无模拟记录（先 `qa run` 模拟）")
        return 1
    result = sims[0].get("result", {})
    platform_alpha_id = result.get("alpha")
    if not platform_alpha_id:
        print(f"[submit] 模拟结果缺少平台 alpha_id（status={sims[0].get('status')}）")
        return 1

    print(f"[submit] 候选: {alpha.get('description', '未命名')}")
    print(f"  表达式: {alpha.get('expression', '')}")
    if alpha.get("hypothesis"):
        print(f"  设计逻辑: {alpha.get('hypothesis')}")
    metrics = alpha.get("metrics", {})
    print(
        f"  指标: Sharpe={metrics.get('sharpe', '—')}  "
        f"Fitness={metrics.get('fitness', '—')}  Turnover={metrics.get('turnover', '—')}"
    )
    checks = sims[0].get("checks", [])
    if checks:
        print("  平台检查:")
        for c in checks:
            print(
                f"    {c.get('name', '?'):<38} {c.get('result', '?'):<8} value={c.get('value', '—')}"
            )

    client = BrainClient(cookie)
    try:
        corr = client.correlations_self(platform_alpha_id)
    except PermissionError:
        print("[submit] 登录失效：请 qa login 重新认证后重试")
        return 1
    except Exception as e:
        print(f"[submit] 免费相关门查询失败: {e}")
        return 1
    print(
        f"  提交前相关门: max_correlation = {corr:.3f}  {'✅ <0.7' if corr < 0.7 else '❌ ≥0.7 不可提交'}"
    )
    if corr >= 0.7:
        print("[submit] 与已提交 alpha 相关性过高，放弃提交。")
        _sediment_failure(
            paths,
            store,
            {
                "id": f"corr_{alpha_id}",
                "expression_hash": alpha_id,
                "failure_reason": f"提交前相关门未过: max_corr={corr:.2f}≥0.7（与现有组合饱和）",
            },
            alpha.get("description") or "相关门饱和",
            f"- 触发: 提交前相关门 FAIL（max_corr={corr:.2f}≥0.7）\n"
            f"- 表达式 hash: {alpha_id}\n"
            f"- 结论: 该方向与现有组合饱和，需换思路或降相关；"
            f"后续生成时避开该信号簇（同簇只保留最优版，被拒即弃不重试）",
        )
        return 1

    if yes:
        confirmed = True
        print("  确认: --yes（用户已在对话中显式确认）")
    else:
        confirmed = input("确认提交？(y/N): ").strip().lower() in ("y", "yes")
    if not confirmed:
        print("[submit] 已取消。")
        return 0

    try:
        resp = client.submit(platform_alpha_id)
        detail = _wait_for_active(client, platform_alpha_id)
    except PermissionError:
        print("[submit] 登录失效：请 qa login 重新认证后重试")
        return 1
    except SubmissionRejected as e:
        print(f"[submit] 提交被平台拒绝（检查未过，非会话问题）:")
        for c in e.checks:
            print(
                f"    {c.get('name', '?'):<38} {c.get('result', '?'):<8} value={c.get('value', '—')}"
            )
        reason = ";".join(
            c.get("name", "") for c in e.checks if c.get("result") == "FAIL"
        )
        _sediment_failure(
            paths,
            store,
            {
                "id": f"sub_{alpha_id}",
                "expression_hash": alpha_id,
                "failure_reason": f"提交检查未过: {reason}",
            },
            alpha.get("description") or "提交被拒",
            f"- 触发: 提交检查未过（{reason}）\n- 表达式 hash: {alpha_id}\n- 结论: 该方向未达提交门槛，避免重复",
        )
        return 1
    except Exception as e:
        print(f"[submit] 提交失败: {e}")
        _sediment_failure(
            paths,
            store,
            {
                "id": f"sub_{alpha_id}",
                "expression_hash": alpha_id,
                "failure_reason": f"提交失败: {e}",
            },
            alpha.get("description") or "提交失败",
            f"- 触发: 提交失败（{e}）\n- 表达式 hash: {alpha_id}\n- 结论: 平台拒绝，见错误信息",
        )
        return 1

    # 平台已接受提交（未抛 SubmissionRejected/异常）→ 从待提交暂存删除，
    # 无论回查状态是否 ACTIVE；被拒/异常时保留暂存供用户重试。
    _remove_pending(paths, alpha_id)

    current_status = detail.get("status", "?")
    confirmed_active = current_status == "ACTIVE"
    store.save_submission(
        {
            "id": f"sub_{alpha_id}",
            "alpha_id": alpha_id,
            "user_confirmed": True,
            "platform_response": resp,
            "current_status": current_status,
            "confirmed_active": confirmed_active,
        }
    )
    store.save_alpha(
        {**alpha, "status": "SUBMITTED" if confirmed_active else "REJECTED"}
    )
    store.append_audit(
        "submit",
        {
            "alpha_id": alpha_id,
            "platform_alpha_id": platform_alpha_id,
            "status": current_status,
        },
    )
    if confirmed_active:
        print(
            f"[submit] ✅ 提交成功并回查 ACTIVE！platform alpha_id={platform_alpha_id}"
        )
        _sediment_lesson(
            paths,
            store,
            {
                "id": f"lesson_{alpha_id}",
                "trigger": "submit_success",
                "hypothesis": alpha.get("hypothesis", ""),
                "verdict": f"ACTIVE sharpe={alpha.get('metrics', {}).get('sharpe')}",
                "lesson": f"提交成功（ACTIVE）：{alpha.get('description', '')}。该方向可行。",
                "raw_ref": alpha_id,
            },
            alpha.get("description") or "提交成功",
            f"- 触发: 提交 ACTIVE（相关门 max_corr={corr:.3f}）\n"
            f"- 假设: {alpha.get('hypothesis') or '—'}\n"
            f"- 结论: 该方向通过平台全部检查并激活，可考虑同簇扩展",
        )
        return 0
    print(
        f"[submit] ⚠️ 平台已接受提交，状态未同步 ACTIVE 属正常延迟（当前 {current_status}），"
        "请到平台核实"
    )
    return 1


def _wait_for_active(
    client: BrainClient, platform_alpha_id: str, timeout: float = 120.0
) -> dict:
    """提交后轮询平台状态直到 ACTIVE（状态更新有延迟，实测提交后需数秒）。"""
    import time as _time

    deadline = _time.time() + timeout
    last = {}
    while _time.time() < deadline:
        detail = client.get_alpha(platform_alpha_id)
        last = detail
        if detail.get("status") == "ACTIVE":
            return detail
        _time.sleep(5.0)
    return last


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa submit（argparse 分发）。"""
    return _cmd_submit(paths, args.alpha_id, args.yes)
