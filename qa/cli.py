"""QuantAlpha CLI：qa login / status / run / report / submit / reset。

生成由对话层 agent 完成（agent 读 knowledge/ 后写候选到 data/candidates/）。
本项目只执行：读入候选 → 预检 → 模拟 → 筛选 → 报告 →（确认后）提交。
合规：提交/清除必须等待用户显式确认（--yes 仅限用户对话中确认后由 agent 代执行）。
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from qa import auth
from qa.brain_client import BrainClient, SimulationResult
from qa.candidates import Candidate, load_candidates
from qa.config import AppConfig
from qa.paths import QaPaths
from qa.report import format_candidates, write_daily_summary
from qa.screener import apply_thresholds, rank_candidates
from qa.stage import get_stage, read_cookie
from qa.store import Store
from qa.validate import ValidationResult, validate_expression


def _load_operators_and_fields() -> tuple[set[str], set[str]]:
    """从 knowledge/ 加载算子与字段白名单。

    算子：内置核心集（67 算子的常用子集）。
    字段：knowledge/fields/TOP_FIELDS.json（295 个精选字段），
    与 agent 生成候选时使用的知识库一致，避免误拦。
    """
    operators = {
        # 算术
        "abs", "log", "min", "max", "add", "subtract", "multiply", "divide",
        "sqrt", "power", "sign", "inverse",
        # 逻辑
        "if_else", "is_nan", "not", "and", "or",
        "greater", "less", "greater_equal", "less_equal", "equal", "not_equal",
        # 时间序列（与 knowledge/operators.md 一致）
        "ts_rank", "ts_mean", "ts_delta", "ts_decay_linear", "ts_backfill",
        "ts_zscore", "ts_delay", "ts_sum", "ts_std_dev", "ts_corr",
        "ts_scale", "ts_quantile", "ts_av_diff", "ts_arg_max", "ts_arg_min",
        # 横截面
        "rank", "zscore", "scale", "quantile", "normalize", "winsorize",
        # 向量
        "vec_avg", "vec_sum",
        # 分组
        "group_rank", "group_neutralize", "group_mean", "group_scale",
        "group_zscore", "group_backfill",
    }
    fields = {
        "close", "open", "high", "low", "volume", "adv20", "cap",
        "assets", "liabilities", "equity", "cashflow", "sales",
        "earnings_est", "cashflow_flag", "est_eps", "free_cash_flow",
    }
    fields_file = QaPaths().root / "knowledge" / "fields" / "TOP_FIELDS.json"
    if fields_file.exists():
        import json

        data = json.loads(fields_file.read_text(encoding="utf-8"))
        fields.update(x["id"] for x in data if isinstance(x, dict) and x.get("id"))
    return operators, fields


def cmd_status(paths: QaPaths) -> int:
    """启动首查：cookie 验证 + 阶段检测 + 配额状态。"""
    try:
        stage = get_stage(paths)
    except FileNotFoundError as e:
        print(f"[status] 错误: {e}")
        return 1
    except PermissionError as e:
        print(f"[status] 错误: {e}")
        return 1
    except Exception as e:  # 网络等
        print(f"[status] 无法连接 BRAIN: {e}")
        return 1
    print(f"账号阶段: {stage.level}  {'顾问' if stage.is_consultant else '用户'}")
    print(f"Genius 等级: {stage.genius_level or '—'}")
    print(f"可用区域: {', '.join(stage.regions)}")
    print(f"表达式语言: {', '.join(stage.expression_languages)}")
    print(f"并发上限: {stage.max_concurrency}")
    print(f"D0 可用: {'是' if stage.d0_available else '否'}")
    return 0


def cmd_run(
    paths: QaPaths,
    cfg: AppConfig,
    candidates_file: str | None,
    idea: str | None,
) -> int:
    """完整闭环：读入候选→预检→模拟→筛选→报告（不提交）。

    候选来源：--candidates-file 指定文件，或自动读当日 data/candidates/YYYY-MM-DD.json。
    idea 参数仅用于提示（agent 生成候选时使用），本项目不生成。
    """
    try:
        cookie = read_cookie(paths.COOKIE)
    except FileNotFoundError as e:
        print(f"[run] 错误: {e}")
        return 1
    try:
        stage = get_stage(paths)
    except Exception as e:
        print(f"[run] 阶段检测失败: {e}")
        return 1

    if candidates_file:
        cand_path = Path(candidates_file)
    else:
        cand_path = paths.CANDIDATES_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    try:
        candidates = load_candidates(cand_path)
    except FileNotFoundError as e:
        print(f"[run] 错误: {e}")
        print("[run] 提示：请先由 agent 根据 knowledge/ 生成候选并写入 "
              "data/candidates/YYYY-MM-DD.json（或使用 --candidates-file 指定文件）。")
        return 1
    if not candidates:
        print(f"[run] 候选文件为空或无有效条目: {cand_path}")
        return 1
    print(f"[run] 读入 {len(candidates)} 个候选（{cand_path.name}）"
          + (f"，研究想法: {idea}" if idea else ""))

    operators, fields = _load_operators_and_fields()
    store = Store(paths.DB)
    client = BrainClient(cookie)

    todo: list[tuple[Candidate, ValidationResult]] = []
    for cand in candidates:
        vr = validate_expression(cand.expression, operators, fields)
        if not vr.ok:
            print(f"  ✗ 预检未过: {cand.expression}  {vr.errors[:2]}")
            store.save_failure(
                {
                    "id": f"f_{vr.expr_hash}",
                    "expression_hash": vr.expr_hash,
                    "failure_reason": "; ".join(vr.errors),
                }
            )
            continue
        if store.alpha_hash_exists(vr.expr_hash):
            print(f"  - 去重跳过（已存在）: {cand.expression}")
            continue
        todo.append((cand, vr))
        print(f"  → 待模拟: {cand.expression}")

    if not todo:
        print("[run] 没有需要模拟的候选（全部预检未过或已存在）。")
        write_daily_summary([], paths.REPORTS_DIR)
        return 0

    # 并发模拟（网络并发；写库回主线程串行，避免 sqlite 跨线程）
    max_workers = min(stage.max_concurrency or cfg.concurrency, len(todo))
    settings = _settings(cfg)
    print(f"[run] 开始批量模拟：{len(todo)} 个候选，并发 {max_workers}")

    def _simulate(
        pair: tuple[Candidate, ValidationResult],
    ) -> tuple[Candidate, ValidationResult, SimulationResult | None, Exception | None]:
        cand, vr = pair
        try:
            sim = client.poll_simulation(
                client.simulate(cand.expression, settings),
                max_wait=cfg.sim_timeout_seconds,
            )
            return cand, vr, sim, None
        except Exception as e:
            return cand, vr, None, e

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for cand, vr, sim, err in pool.map(_simulate, todo):
            if err is not None:
                print(f"    ✗ 模拟失败: {cand.expression}: {err}")
                audit_ts = store.append_audit(
                    "simulation_error", {"expr_hash": vr.expr_hash, "error": str(err)}
                )
                store.save_simulation(
                    {"id": f"sim_{vr.expr_hash}", "alpha_id": vr.expr_hash,
                     "status": "ERROR", "result": {"error": str(err)},
                     "audit_path": audit_ts}
                )
                continue
            assert sim is not None, "模拟失败但 err 为 None"
            verdict = apply_thresholds(sim.metrics, sim.checks, cfg.thresholds)
            results.append(
                {
                    "id": vr.expr_hash,
                    "description": cand.description,
                    "expression": cand.expression,
                    "verdict": verdict.verdict,
                    "reason": verdict.reason,
                    "sharpe": sim.metrics.get("sharpe"),
                    "fitness": sim.metrics.get("fitness"),
                    "turnover": sim.metrics.get("turnover"),
                    "score": _score(sim.metrics),
                }
            )
            store.save_alpha(
                {
                    "id": vr.expr_hash,
                    "expression": cand.expression,
                    "description": cand.description,
                    "hypothesis": cand.hypothesis,
                    "dataset_ids": cand.dataset_ids,
                    "ast_hash": vr.expr_hash,
                    "metrics": sim.metrics,
                    "status": "COMPLETE",
                }
            )
            audit_ts = store.append_audit("simulation", {"expr_hash": vr.expr_hash, "status": sim.status})
            store.save_simulation(
                {
                    "id": f"sim_{vr.expr_hash}",
                    "alpha_id": vr.expr_hash,
                    "request": {"settings": settings, "regular": cand.expression},
                    "status": sim.status,
                    "result": sim.raw,
                    "checks": sim.checks,
                    "audit_path": audit_ts,
                }
            )
            print(f"    {verdict.verdict}: Sharpe={sim.metrics.get('sharpe') or '—'}")

    ranked = rank_candidates(results)
    print()
    print(format_candidates(ranked))
    write_daily_summary(ranked, paths.REPORTS_DIR)
    print(f"[run] 完成。通过 {sum(1 for r in ranked if r['verdict']=='PASS')} / {len(ranked)} 个候选。"
          f"报告已写入 reports/daily/")
    return 0


def _settings(cfg: AppConfig) -> dict[str, str | int | float | bool]:
    """把 SimulationDefaults 转成 BRAIN 模拟 API 的 settings 载荷。

    平台实测要求：unitHandling 与 visualization 必填（见 brain_client.simulate）。
    """
    d = cfg.defaults
    return {
        "instrumentType": d.instrument_type,
        "region": d.region,
        "universe": d.universe,
        "delay": d.delay,
        "decay": d.decay,
        "neutralization": d.neutralization,
        "truncation": d.truncation,
        "pasteurization": d.pasteurization,
        "nanHandling": d.nan_handling,
        "unitHandling": "VERIFY",
        "visualization": False,
        "language": d.language,
        "testPeriod": d.test_period,
        "startDate": d.start_date,
        "endDate": d.end_date,
    }


def _score(metrics: dict[str, float | None]) -> float:
    """组合视角近似评分：Sharpe 主导 + Fitness + 低换手。"""
    sharpe = metrics.get("sharpe") or 0.0
    fitness = metrics.get("fitness") or 0.0
    turnover = metrics.get("turnover") or 1.0
    return sharpe * 1.0 + fitness * 0.5 - min(turnover, 1.0) * 0.3


def main(argv: list[str] | None = None) -> int:
    paths = QaPaths(Path.cwd())
    cfg = AppConfig()
    parser = argparse.ArgumentParser(prog="qa", description="QuantAlpha CLI")
    sub = parser.add_subparsers(dest="command")

    p_status = sub.add_parser("status", help="启动首查（阶段检测/配额）")
    p_status.set_defaults(func=lambda a: cmd_status(paths))

    p_login = sub.add_parser(
        "login", help="账号密码登录，写入会话 cookie（替代浏览器复制 cURL）"
    )
    p_login.add_argument("--username", type=str, default=None, help="BRAIN 账号邮箱")
    p_login.add_argument("--password", type=str, default=None, help="BRAIN 账号密码（也可交互输入）")
    p_login.set_defaults(func=lambda a: _cmd_login(paths, a.username, a.password))

    p_run = sub.add_parser("run", help="完整闭环（读入候选→预检→模拟→筛选→报告）")
    p_run.add_argument("--candidates-file", type=str, default=None,
                       help="候选 JSON 文件路径（默认读当日 data/candidates/YYYY-MM-DD.json）")
    p_run.add_argument("--idea", type=str, default=None, help="研究方向/点子（提示用）")
    p_run.set_defaults(func=lambda a: cmd_run(paths, cfg, a.candidates_file, a.idea))

    p_report = sub.add_parser("report", help="查看候选清单/每日汇总")
    p_report.add_argument("--daily", action="store_true", help="显示每日汇总")
    p_report.set_defaults(func=lambda a: _cmd_report(paths, a))

    p_submit = sub.add_parser(
        "submit", help="人工确认后提交 alpha（提交前展示检查 + 回查 ACTIVE）"
    )
    p_submit.add_argument("alpha_id", type=str, help="本地 alpha id（alphas 表主键）")
    p_submit.add_argument("--yes", action="store_true",
                          help="跳过交互确认（仅限用户在对话中已显式确认后，由 agent 代提交）")
    p_submit.set_defaults(func=lambda a: _cmd_submit(paths, a.alpha_id, a.yes))

    p_reset = sub.add_parser(
        "reset", help="清除积累的经验，回到初始状态（保留登录凭证与知识库）"
    )
    p_reset.add_argument("--yes", action="store_true",
                         help="跳过交互确认（仅限用户在对话中已显式确认后，由 agent 执行）")
    p_reset.set_defaults(func=lambda a: _cmd_reset(paths, a.yes))

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


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
        print(f"账号阶段: {stage.level}  {'顾问' if stage.is_consultant else '用户'}")
        return 0
    except Exception as e:
        print(f"[login] cookie 已写入但阶段检测失败: {e}")
        return 1


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
    metrics = alpha.get("metrics", {})
    print(f"  指标: Sharpe={metrics.get('sharpe', '—')}  "
          f"Fitness={metrics.get('fitness', '—')}  Turnover={metrics.get('turnover', '—')}")
    checks = sims[0].get("checks", [])
    if checks:
        print("  平台检查:")
        for c in checks:
            print(f"    {c.get('name', '?'):<38} {c.get('result', '?'):<8} value={c.get('value', '—')}")

    client = BrainClient(cookie)
    try:
        corr = client.correlations_self(platform_alpha_id)
    except Exception as e:
        print(f"[submit] 免费相关门查询失败: {e}")
        return 1
    print(f"  提交前相关门: max_correlation = {corr:.3f}  {'✅ <0.7' if corr < 0.7 else '❌ ≥0.7 不可提交'}")
    if corr >= 0.7:
        print("[submit] 与已提交 alpha 相关性过高，放弃提交。")
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
    except Exception as e:
        print(f"[submit] 提交失败: {e}")
        store.save_failure(
            {"id": f"sub_{alpha_id}", "expression_hash": alpha_id,
             "failure_reason": f"提交失败: {e}"}
        )
        return 1

    current_status = detail.get("status", "?")
    confirmed_active = current_status == "ACTIVE"
    store.save_submission(
        {"id": f"sub_{alpha_id}", "alpha_id": alpha_id,
         "user_confirmed": True, "platform_response": resp,
         "current_status": current_status, "confirmed_active": confirmed_active}
    )
    store.save_alpha({**alpha, "status": "SUBMITTED" if confirmed_active else "REJECTED"})
    store.append_audit(
        "submit",
        {"alpha_id": alpha_id, "platform_alpha_id": platform_alpha_id,
         "status": current_status},
    )
    if confirmed_active:
        print(f"[submit] ✅ 提交成功并回查 ACTIVE！platform alpha_id={platform_alpha_id}")
        return 0
    print(f"[submit] ⚠️ 提交返回但状态为 {current_status}（未确认 ACTIVE，请到平台核实）")
    return 1


def _wait_for_active(client: BrainClient, platform_alpha_id: str, timeout: float = 120.0) -> dict:
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


def _cmd_reset(paths: QaPaths, yes: bool = False) -> int:
    """清除积累的经验，回到项目初始状态（合规：保留登录凭证与静态知识库）。

    清除：qa.db、audit/、candidates/、reports/daily/、pending_submits.json、
    playbook/failures 的沉淀段落（恢复模板）。
    保留：secrets/ 下 cookie 与 account_info（登录凭证）、knowledge/ 静态知识库。
    """
    targets = {
        "qa.db（模拟/提交/经验全部记录）": paths.DB,
        "审计日志 data/audit/": paths.AUDIT_DIR,
        "候选文件 data/candidates/": paths.CANDIDATES_DIR,
        "每日汇总 reports/daily/": paths.REPORTS_DIR / "daily",
    }
    pending = paths.COOKIE.parent / "pending_submits.json"
    if pending.exists():
        targets["待提交暂存 pending_submits.json"] = pending

    print("[reset] 将清除以下经验积累（回到初始状态）：")
    for label, p in targets.items():
        print(f"  - {label} ({p})")
    if pending.exists():
        print("  ⚠️ 待提交暂存含未提交 alpha，清除后需重新模拟生成")
    print("[reset] 保留：secrets/ 登录凭证、knowledge/ 静态知识库、qa/ 代码")

    if yes:
        confirmed = True
    else:
        try:
            confirmed = input("确认清除？(y/N): ").strip().lower() in ("y", "yes")
        except EOFError:
            print("[reset] 非交互环境请使用 --yes（确认后由 agent 执行）。")
            return 1
    if not confirmed:
        print("[reset] 已取消。")
        return 0

    for label, p in targets.items():
        if p.is_dir():
            for f in p.glob("*"):
                f.unlink(missing_ok=True)
            print(f"  ✓ 已清空 {label}")
        elif p.exists():
            p.unlink()
            print(f"  ✓ 已删除 {label}")
    _restore_template(paths.root / "knowledge" / "playbook.md", "playbook")
    _restore_template(paths.root / "knowledge" / "failures.md", "failures")
    print("[reset] 完成。项目已回到初始状态，可重新开始生成/模拟。")
    return 0


def _restore_template(path, kind: str) -> None:
    """把 playbook/failures 恢复为初始模板（去掉沉淀段落，保留自动追加区）。"""
    if kind == "playbook":
        template = (
            "# 经验 Playbook（脱敏）\n"
            "\n"
            "> 从每次 alpha 的研究/模拟/提交中沉淀的可复用经验。\n"
            "> 当前沉淀落 SQLite（`qa/store.py` save_lesson 表）；本文件自动追加属第二批规划（`qa submit` 后接线）。**脱敏**：不含真实表达式/账号数据。\n"
            "\n"
            "## 格式\n"
            "\n"
            "每条经验：触发条件 → 假设 → 结论。\n"
            "\n"
            "<!-- 自动追加区（第二批接线） -->\n"
        )
    else:
        template = (
            "# 证伪库（已证伪路径）\n"
            "\n"
            "> 记录已验证失败的方向，避免 LLM 重复走死路。\n"
            "> 当前沉淀落 SQLite（`qa/store.py` failures 表）；本文件自动追加属第二批规划。\n"
            "\n"
            "<!-- 自动追加区（第二批接线） -->\n"
        )
    if path.exists():
        path.write_text(template, encoding="utf-8")
        print(f"  ✓ {path.name} 已恢复模板")


def _cmd_report(paths: QaPaths, args) -> int:
    daily_dir = paths.REPORTS_DIR / "daily"
    if not daily_dir.exists():
        print("[report] 尚无每日汇总。先运行 qa run。")
        return 0
    import glob

    files = sorted(glob.glob(str(daily_dir / "*.md")), reverse=True)
    if not files:
        print("[report] 尚无每日汇总。先运行 qa run。")
        return 0
    if args.daily:
        for f in files[:1]:
            print(Path(f).read_text(encoding="utf-8"))
    else:
        print("近期每日汇总:")
        for f in files[:7]:
            print(f"  {Path(f).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
