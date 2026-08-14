"""QuantAlpha CLI：qa status / run / report。

生成由对话层 agent 完成（agent 读 knowledge/ 后写候选到 data/candidates/）。
本项目只执行：读入候选 → 预检 → 模拟 → 筛选 → 报告。合规：run 只到报告，不自动提交。
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
        "rank", "ts_rank", "ts_mean", "ts_delta", "ts_decay_linear",
        "group_rank", "vec_avg", "vec_count", "is_nan", "ts_backfill",
        "group_neutralize", "vector_neut", "pasteurize", "abs", "log",
        "min", "max", "sum", "mean", "stddev", "zscore", "correlation",
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


def cmd_status(paths: QaPaths, cfg: AppConfig) -> int:
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
    print(f"[run] 开始批量模拟：{len(todo)} 个候选，并发 {max_workers}")

    def _simulate(
        pair: tuple[Candidate, ValidationResult],
    ) -> tuple[Candidate, ValidationResult, SimulationResult | None, Exception | None]:
        cand, vr = pair
        try:
            sim = client.poll_simulation(
                client.simulate(cand.expression, _settings(cfg)),
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
                    "request": {"settings": _settings(cfg), "regular": cand.expression},
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
    p_status.set_defaults(func=lambda a: cmd_status(paths, cfg))

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
