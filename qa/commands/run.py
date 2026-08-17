"""qa run 命令：完整闭环（读入候选→预检→模拟→筛选→报告）。"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

import requests

from qa import knowledge
from qa.brain_client import BrainClient, SimulationResult
from qa.candidates import Candidate, load_candidates
from qa.commands._common import _append_pending, _sediment_failure, _sediment_lesson
from qa.config import AppConfig
from qa.knowledge import KnowledgeMissingError
from qa.paths import QaPaths
from qa.report import format_candidates, write_daily_summary
from qa.screener import apply_thresholds, dedupe_by_fields
from qa.stage import get_stage, read_cookie
from qa.store import Store
from qa.validate import (
    ValidationResult,
    expression_fields,
    validate_expression,
    validate_settings,
)


def _load_operators() -> set[str]:
    """算子白名单：平台官方 67 算子全集（与公开 knowledge/operators.md 一致，2026-08-14 API 实测）。"""
    return {
        # 算术
        "abs",
        "log",
        "min",
        "max",
        "add",
        "subtract",
        "multiply",
        "divide",
        "sqrt",
        "power",
        "sign",
        "inverse",
        "signed_power",
        "reverse",
        "densify",
        # 逻辑
        "if_else",
        "is_nan",
        "not",
        "and",
        "or",
        "greater",
        "less",
        "greater_equal",
        "less_equal",
        "equal",
        "not_equal",
        # 时间序列（与 knowledge/operators.md 一致）
        "ts_rank",
        "ts_mean",
        "ts_delta",
        "ts_decay_linear",
        "ts_backfill",
        "ts_zscore",
        "ts_delay",
        "ts_sum",
        "ts_std_dev",
        "ts_corr",
        "ts_scale",
        "ts_quantile",
        "ts_av_diff",
        "ts_arg_max",
        "ts_arg_min",
        "hump",
        "kth_element",
        "ts_step",
        "days_from_last_change",
        "ts_count_nans",
        "ts_covariance",
        "ts_product",
        "ts_regression",
        "last_diff_value",
        # 横截面
        "rank",
        "zscore",
        "scale",
        "quantile",
        "normalize",
        "winsorize",
        "vector_neut",
        # 向量
        "vec_avg",
        "vec_sum",
        # 变换（Transformational）
        "trade_when",
        "bucket",
        # 分组
        "group_rank",
        "group_neutralize",
        "group_mean",
        "group_scale",
        "group_zscore",
        "group_backfill",
    }


def _load_fields(paths: QaPaths) -> tuple[set[str], dict[str, str]]:
    """字段白名单 + 类型映射：读本地 experience/fields/fields.json（缺失抛错）。"""
    return knowledge.load_fields(paths)


def _settings(
    cfg: AppConfig, candidate_settings: dict[str, object] | None = None
) -> dict[str, str | int | float | bool]:
    """把 SimulationDefaults 转成 BRAIN 模拟 API 的 settings 载荷。

    平台实测要求：unitHandling 与 visualization 必填（见 brain_client.simulate）。
    candidate_settings：候选级覆盖（decay/neutralization/truncation，
    由 validate_settings 校验过；未知键忽略，防幻觉参数）。
    """
    d = cfg.defaults
    settings = {
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
    for key in ("decay", "neutralization", "truncation"):
        if candidate_settings and key in candidate_settings:
            settings[key] = candidate_settings[key]  # type: ignore[assignment]
    return settings


def _score(metrics: dict[str, float | None]) -> float:
    """组合视角近似评分：Sharpe 主导 + Fitness + 低换手。"""
    sharpe = metrics.get("sharpe") or 0.0
    fitness = metrics.get("fitness") or 0.0
    turnover = metrics.get("turnover") or 1.0
    return sharpe * 1.0 + fitness * 0.5 - min(turnover, 1.0) * 0.3


@dataclass
class _RunContext:
    """cmd_run 批处理上下文：worker 并发写标志，主线程串行消费结果。

    session_lost/done 由 worker 线程置位（GIL 下原子赋值），
    主线程在 chunk 循环中串行读取；results 仅主线程追加。
    """

    cfg: AppConfig
    paths: QaPaths
    store: Store
    client: BrainClient
    todo: list[tuple[Candidate, ValidationResult]]
    session_lost: bool = False
    done: int = 0
    total: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)

    def prog(self) -> str:
        return f"(已完成 {self.done}/{self.total})"


def _start_sim(
    ctx: _RunContext, pair: tuple[Candidate, ValidationResult]
) -> tuple[Candidate, ValidationResult, str | None, Exception | None]:
    """worker 阶段 1：发起模拟，返回平台 sim_id（不碰 DB）。"""
    cand, vr = pair
    try:
        sim_id = ctx.client.simulate(cand.expression, _settings(ctx.cfg, cand.settings))
        if not sim_id:
            return (
                cand,
                vr,
                None,
                RuntimeError("simulate 未返回 sim_id（Location 头缺失）"),
            )
        return cand, vr, sim_id, None
    except PermissionError as e:
        # 会话过期不是候选问题：置中断标志，不落 ERROR 记录（重跑会重新模拟）
        ctx.session_lost = True
        return cand, vr, None, e
    except Exception as e:
        return cand, vr, None, e


def _poll_sim(
    ctx: _RunContext, item: tuple[Candidate, ValidationResult, str, bool]
) -> tuple[
    Candidate,
    ValidationResult,
    SimulationResult | None,
    Exception | None,
    str,
    bool,
]:
    """worker 阶段 2：轮询模拟直到终态（不碰 DB）。"""
    cand, vr, sim_id, resumed = item
    try:
        sim = ctx.client.poll_simulation(sim_id, max_wait=ctx.cfg.sim_timeout_seconds)
        return cand, vr, sim, None, sim_id, resumed
    except PermissionError as e:
        ctx.session_lost = True
        return cand, vr, None, e, sim_id, resumed
    except Exception as e:
        return cand, vr, None, e, sim_id, resumed


def _is_404(err: Exception) -> bool:
    return (
        isinstance(err, requests.exceptions.HTTPError)
        and err.response is not None
        and err.response.status_code == 404
    )


def _record_sim_error(
    ctx: _RunContext,
    cand: Candidate,
    vr: ValidationResult,
    err: Exception,
    sim_id: str | None,
) -> None:
    """模拟发起失败的 ERROR 记录（无平台 sim_id，用 sim_{hash} 占位防重）。"""
    audit_ts = ctx.store.append_audit(
        "simulation_error", {"expr_hash": vr.expr_hash, "error": str(err)}
    )
    ctx.store.save_simulation(
        {
            "id": sim_id or f"sim_{vr.expr_hash}",
            "alpha_id": vr.expr_hash,
            "status": "ERROR",
            "result": {"error": str(err)},
            "audit_path": audit_ts,
        }
    )


def _record_poll_error(
    ctx: _RunContext, cand: Candidate, vr: ValidationResult, sim_id: str, err: Exception
) -> None:
    """轮询阶段失败：有平台 sim_id，超时标 TIMEOUT（重跑续查），其余标 ERROR。"""
    ctx.store.save_simulation(
        {
            "id": sim_id,
            "alpha_id": vr.expr_hash,
            "status": "TIMEOUT" if isinstance(err, TimeoutError) else "ERROR",
            "result": {"error": str(err)},
        }
    )


def _handle_failure(
    ctx: _RunContext,
    cand: Candidate,
    vr: ValidationResult,
    sim_id: str | None,
    err: Exception,
) -> None:
    """统一处理模拟/轮询失败（新模拟/续查/404 回退重提三处共用）。

    会话过期不是终态：只提示不计入已完成（重跑自动续查/重提）；
    其他失败计为已尝试并落 ERROR/TIMEOUT 记录（防重：重跑跳过或续查）。
    sim_id 为 None 表示发起阶段失败（无平台 sim_id）。
    """
    if ctx.session_lost and isinstance(err, PermissionError):
        print(f"    {ctx.prog()} ✗ 模拟失败（会话过期）: {cand.expression}: {err}")
        return
    ctx.done += 1
    print(f"    {ctx.prog()} ✗ 模拟失败: {cand.expression}: {err}")
    if sim_id is None:
        _record_sim_error(ctx, cand, vr, err, None)
    else:
        _record_poll_error(ctx, cand, vr, sim_id, err)


def _session_lost_prompt(ctx: _RunContext) -> bool:
    """会话过期中断提示：打印剩余未模拟数；返回 True 表示停止后续批次。"""
    if not ctx.session_lost:
        return False
    n_remaining = len(ctx.todo) - len(ctx.results)
    print(
        f"[run] 会话已过期，剩余 {n_remaining} 个候选未模拟。"
        "已模拟结果已保存（重跑自动跳过/续查），请 qa login 后重试。"
    )
    return True


def _quota_exhausted_prompt() -> None:
    """平台每日模拟配额耗尽提示（入口首查与批间截断共用文案）。"""
    print("[run] 平台每日模拟配额已耗尽（EST 日界重置），明天再试。")


def _finalize(
    ctx: _RunContext, cand: Candidate, vr: ValidationResult, sim: SimulationResult
) -> None:
    """主线程收尾：阈值判定 + 落库 + 经验沉淀 + 报告收集。"""
    verdict = apply_thresholds(sim.metrics, sim.checks, ctx.cfg.thresholds)
    ctx.results.append(
        {
            "id": vr.expr_hash,
            "description": cand.description,
            "hypothesis": cand.hypothesis,
            "expression": cand.expression,
            "verdict": verdict.verdict,
            "reason": verdict.reason,
            "sharpe": sim.metrics.get("sharpe"),
            "fitness": sim.metrics.get("fitness"),
            "turnover": sim.metrics.get("turnover"),
            "score": _score(sim.metrics),
            "platform_alpha_id": sim.alpha_id,
        }
    )
    ctx.store.save_alpha(
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
    # 经验自动沉淀（v1.4）：PASS→lessons、FAIL/FAIL_INFRA→failures（模拟 FAIL→failures 约定）
    if verdict.verdict == "PASS":
        _sediment_lesson(
            ctx.paths,
            ctx.store,
            {
                "id": f"lesson_{vr.expr_hash}",
                "trigger": "simulation_pass",
                "hypothesis": cand.hypothesis,
                "verdict": f"PASS sharpe={sim.metrics.get('sharpe')}",
                "lesson": f"模拟通过：{cand.description}。假设: {cand.hypothesis or '—'}",
                "raw_ref": vr.expr_hash,
            },
            cand.description or "模拟通过",
            f"- 触发: 模拟 PASS（Sharpe={sim.metrics.get('sharpe')}, "
            f"Fitness={sim.metrics.get('fitness')}）\n"
            f"- 假设: {cand.hypothesis or '—'}\n"
            f"- 结论: 该方向有效，可复用/组合",
        )
    elif verdict.verdict in ("FAIL", "FAIL_INFRA"):
        # FAIL_INFRA：平台返回 ERROR/FAILED（无指标），也沉淀 failures（重跑可能恢复）
        is_infra = verdict.verdict == "FAIL_INFRA"
        _sediment_failure(
            ctx.paths,
            ctx.store,
            {
                "id": f"f_{vr.expr_hash}",
                "expression_hash": vr.expr_hash,
                "failure_reason": (
                    f"模拟基础设施失败: {verdict.reason}"
                    if is_infra
                    else f"模拟未过: {verdict.reason}"
                ),
            },
            cand.description or "模拟失败",
            f"- 触发: 模拟 {'FAIL_INFRA' if is_infra else 'FAIL'}（{verdict.reason}）\n"
            f"- 表达式 hash: {vr.expr_hash}\n"
            f"- 结论: {('平台未返回指标（网络/平台侧异常），重跑可能恢复' if is_infra else '该方向已证伪，避免重复')}",
        )
    audit_ts = ctx.store.append_audit(
        "simulation", {"expr_hash": vr.expr_hash, "status": sim.status}
    )
    # UPDATE 同一条 PENDING 记录（id=平台 sim_id，started_at 保留首次发起时间）
    ctx.store.save_simulation(
        {
            "id": sim.sim_id,
            "alpha_id": vr.expr_hash,
            "request": {
                "settings": _settings(ctx.cfg, cand.settings),
                "regular": cand.expression,
            },
            "status": sim.status,
            "result": sim.raw,
            "checks": sim.checks,
            "audit_path": audit_ts,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    ctx.done += 1
    print(
        f"    {ctx.prog()} {verdict.verdict}: Sharpe={sim.metrics.get('sharpe') or '—'}"
    )


def _start_phase(
    ctx: _RunContext,
    pool: ThreadPoolExecutor,
    tasks: list[tuple[Candidate, ValidationResult]],
) -> list[tuple[Candidate, ValidationResult, str]]:
    """阶段 1（主线程串行）：并行发起 simulate → 落库 PENDING，返回已发起列表。"""
    started: list[tuple[Candidate, ValidationResult, str]] = []
    for cand, vr, sim_id, err in pool.map(partial(_start_sim, ctx), tasks):
        if err is not None:
            _handle_failure(ctx, cand, vr, None, err)
            continue
        assert sim_id is not None, "simulate 成功但 sim_id 为 None"
        ctx.store.save_simulation(
            {
                "id": sim_id,
                "alpha_id": vr.expr_hash,
                "request": {
                    "settings": _settings(ctx.cfg, cand.settings),
                    "regular": cand.expression,
                },
                "status": "PENDING",
            }
        )
        started.append((cand, vr, sim_id))
    return started


def _poll_phase(
    ctx: _RunContext,
    pool: ThreadPoolExecutor,
    poll_tasks: list[tuple[Candidate, ValidationResult, str, bool]],
) -> list[tuple[Candidate, ValidationResult, str]]:
    """阶段 2（主线程串行）：并行轮询 → 终态收尾；续查 404 返回回退重提列表。"""
    retries: list[tuple[Candidate, ValidationResult, str]] = []
    for cand, vr, sim, err, sim_id, resumed in pool.map(
        partial(_poll_sim, ctx), poll_tasks
    ):
        if err is not None:
            if resumed and _is_404(err):
                # 续查 404：平台已清理该模拟 → 删旧记录，回退重新 simulate
                retries.append((cand, vr, sim_id))
                continue
            _handle_failure(ctx, cand, vr, sim_id, err)
            continue
        assert sim is not None, "轮询成功但 sim 为 None"
        _finalize(ctx, cand, vr, sim)
    return retries


def _retry_phase(
    ctx: _RunContext,
    pool: ThreadPoolExecutor,
    retries: list[tuple[Candidate, ValidationResult, str]],
) -> None:
    """阶段 2 续：续查 404（平台已清理）→ 删旧记录，回退重新 simulate + 轮询。"""
    for cand, vr, stale_id in retries:
        ctx.store.delete_simulation(stale_id)
    retry_started = _start_phase(ctx, pool, [(c, v) for c, v, _ in retries])
    _poll_phase(ctx, pool, [(c, v, s, False) for c, v, s in retry_started])


def _quota_check(ctx: _RunContext) -> bool:
    """批间限流检查（主线程统一读 rate_limits，v1.6 修并发竞态）。

    每日配额耗尽返回 False（提前停止后续批次）；分钟剩余不足则等待后继续。
    """
    try:
        rl = ctx.client.rate_limits()
    except Exception:
        return True  # 限流头不可用时继续，靠平台错误码/429 退避兜底
    if rl.daily_remaining is not None and rl.daily_remaining <= 0:
        _quota_exhausted_prompt()
        return False
    if rl.remaining_minute <= ctx.cfg.min_remaining_minute:
        # 优先用平台 reset 头；缺失时按窗口消耗比例估算
        if rl.reset_seconds and rl.reset_seconds > 0:
            wait = min(max(int(rl.reset_seconds), 10), 60)
        else:
            ratio = 1 - rl.remaining_minute / max(rl.limit_minute, 1)
            wait = min(max(int(ratio * 60), 10), 60)
        print(f"[run] 分钟限流剩余 {rl.remaining_minute}，等待 {wait}s 后继续……")
        time.sleep(wait)
    return True


def cmd_run(
    paths: QaPaths,
    cfg: AppConfig,
    candidates_file: str | None,
    concurrency: int | None = None,
) -> int:
    """完整闭环：读入候选→预检→模拟→筛选→报告（不提交）。

    候选来源：--candidates-file 指定文件，或自动读当日 data/candidates/YYYY-MM-DD.json。
    concurrency：显式 --concurrency > stage.max_concurrency > cfg 默认。
    """
    try:
        cookie = read_cookie(paths.COOKIE)
    except FileNotFoundError as e:
        print(f"[run] 错误: {e}")
        return 1
    try:
        stage = get_stage(paths)
    except PermissionError:
        print("[run] 登录失效：请 qa login 后重试")
        return 1
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
        print(
            "[run] 提示：请先由 agent 根据 knowledge/ 生成候选并写入 "
            "data/candidates/YYYY-MM-DD.json（或使用 --candidates-file 指定文件）。"
        )
        return 1
    if not candidates:
        print(f"[run] 候选文件为空或无有效条目: {cand_path}")
        return 1
    print(f"[run] 读入 {len(candidates)} 个候选（{cand_path.name}）")

    try:
        operators = _load_operators()
        fields, field_types = _load_fields(paths)
    except KnowledgeMissingError as e:
        print(f"[run] 错误: {e}")
        return 1
    store = Store(paths.DB)
    client = BrainClient(cookie)

    # 每日模拟配额：纯平台配额头（x-ratelimit-remaining，无 -minute 后缀）
    # v1.6 删本地预算（daily_sim_budget/daily_sim_count）——头缺失（None）时不拦截，
    # 靠平台错误码/429 退避兜底；分钟限流层才是真正的防护层（保留不动）。
    remaining = None
    try:
        rl = client.rate_limits()
        remaining = rl.daily_remaining
        if remaining is not None:
            print(f"[run] 平台每日模拟剩余: {remaining}")
    except Exception:
        pass  # 平台配额头不可用时无预算拦截，靠平台错误码兜底
    if remaining is not None and remaining <= 0:
        _quota_exhausted_prompt()
        return 1

    validated: list[tuple[Candidate, ValidationResult]] = []
    for cand in candidates:
        vr = validate_expression(
            cand.expression, operators, fields, field_types, language=cand.language
        )
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
        s_errors = validate_settings(cand.settings)
        if s_errors:
            print(f"  ✗ 预检未过: {cand.expression}  {s_errors[:2]}")
            store.save_failure(
                {
                    "id": f"f_{vr.expr_hash}",
                    "expression_hash": vr.expr_hash,
                    "failure_reason": "; ".join(s_errors),
                }
            )
            continue
        if store.alpha_hash_exists(vr.expr_hash):
            print(f"  - 去重跳过（已存在）: {cand.expression}")
            continue
        if store.sim_failure_exists(vr.expr_hash):
            print(f"  - 去重跳过（此前模拟已失败，不重复模拟）: {cand.expression}")
            continue
        validated.append((cand, vr))
        print(f"  → 待模拟: {cand.expression}")

    # 同字段集簇去重：同信号簇只模拟最简者（省配额）
    keep, skipped = dedupe_by_fields([c.expression for c, _ in validated], operators)
    todo = [validated[i] for i in keep]
    for idx, reason in skipped:
        cand, _ = validated[idx]
        print(f"  - {reason}: {cand.expression}")

    if remaining is not None and len(todo) > remaining:
        print(f"[run] 配额剩余 {remaining}，只模拟前 {remaining} 个候选。")
        todo = todo[:remaining]

    if not todo:
        print("[run] 没有需要模拟的候选（全部预检未过/去重/配额受限）。")
        write_daily_summary([], paths.REPORTS_DIR)
        return 0

    # 并发：显式 --concurrency > stage.max_concurrency > cfg 默认
    workers = concurrency or stage.max_concurrency or cfg.concurrency
    max_workers = min(workers, len(todo))
    print(f"[run] 开始批量模拟：{len(todo)} 个候选，并发 {max_workers}")

    # 网络并发；写库回主线程串行（避免 sqlite 跨线程）
    # 会话过期中断标志：worker 捕获 PermissionError 置位，chunk 循环检测后停止
    # 后续批次（幂等设计保证重跑只补未模拟项，不重复耗配额）
    ctx = _RunContext(
        cfg=cfg, paths=paths, store=store, client=client, todo=todo, total=len(todo)
    )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for start in range(0, len(todo), max_workers):
            chunk = todo[start : start + max_workers]

            # 阶段 1（主线程先查续查记录）：有 PENDING/TIMEOUT 平台 sim_id → 续查；
            # 无记录 → 并行发起 simulate，成功后立即落库 PENDING（中断后重跑可续查）
            new_tasks: list[tuple[Candidate, ValidationResult]] = []
            resume_items: list[tuple[Candidate, ValidationResult, str]] = []
            for cand, vr in chunk:
                rid = store.find_pending_sim_id(vr.expr_hash)
                if rid:
                    resume_items.append((cand, vr, rid))
                else:
                    new_tasks.append((cand, vr))

            started = _start_phase(ctx, pool, new_tasks)
            if _session_lost_prompt(ctx):
                break

            # 阶段 2：并行轮询（新模拟 + 续查）
            poll_tasks = [(c, v, s, False) for c, v, s in started]
            poll_tasks += [(c, v, rid, True) for c, v, rid in resume_items]
            retries = _poll_phase(ctx, pool, poll_tasks)
            if retries and not ctx.session_lost:
                _retry_phase(ctx, pool, retries)

            if _session_lost_prompt(ctx):
                break
            if start + max_workers < len(todo) and not _quota_check(ctx):
                break

    # 组合视角（P3）：PASS 候选调免费相关门，按 max_corr 升序优先（低相关先提交）
    for r in ctx.results:
        if r["verdict"] == "PASS" and r.get("platform_alpha_id"):
            try:
                r["corr"] = client.correlations_self(r["platform_alpha_id"])
            except Exception as e:
                print(f"    相关门查询失败（保持原排序）: {r['expression']}: {e}")

    ranked = sorted(
        ctx.results,
        key=lambda r: (
            r.get("corr") if r.get("corr") is not None else float("inf"),
            -r.get("score", 0.0),
        ),
    )

    n_pending = 0
    for r in ranked:
        if r["verdict"] == "PASS":
            _append_pending(
                paths,
                {
                    "id": r["id"],
                    "description": r["description"],
                    "hypothesis": r.get("hypothesis"),
                    "expression": r["expression"],
                    "metrics": {
                        "sharpe": r["sharpe"],
                        "fitness": r["fitness"],
                        "turnover": r["turnover"],
                    },
                    # 阶段 6：相关门排序值随暂存写入，供 qa report --pending 展示
                    # （排序值是 run 时历史值，提交前需复查，submit 会实时重查）
                    "corr": r.get("corr"),
                },
            )
            n_pending += 1
    if n_pending:
        print(
            f"[run] 已暂存 {n_pending} 个达标 alpha 到待提交（secrets/pending_submits.json），"
            "新会话 agent 会提示确认提交。"
        )

    # 批次多样性统计（反馈 agent：同主题变体过多会浪费配额）
    n_sets = len(
        {frozenset(expression_fields(r["expression"], operators)) for r in ctx.results}
    )
    print(f"[run] 批次字段多样性: {n_sets} 个不同字段集 / {len(ctx.results)} 个候选")
    print()
    print(format_candidates(ranked))
    write_daily_summary(ranked, paths.REPORTS_DIR)
    print(
        f"[run] 完成。通过 {sum(1 for r in ranked if r['verdict'] == 'PASS')} / {len(ranked)} 个候选。"
        f"报告已写入 reports/daily/"
    )
    return 0


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa run（argparse 分发）。"""
    return cmd_run(paths, cfg, args.candidates_file, args.concurrency)
