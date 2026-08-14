"""应用配置：模拟默认参数 + 提交门槛 + 批处理/并发设置。

- SimulationDefaults：对齐账号实测的平台模拟默认值（设计 §2.2）；
  顾问阶段可由 stage.py 检测结果覆盖 region/universe 等字段。
- Thresholds：提交门槛（对齐平台提交检查，设计 §2.3），
  供 screener 本地过滤与 MARGINAL 判定使用。
- AppConfig：聚合配置入口。无 LLM 配置——生成由对话层 agent 完成。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SimulationDefaults:
    """平台模拟默认设置（对齐账号实测默认值，见设计 §2.2）。"""

    region: str = "USA"
    universe: str = "TOP3000"
    delay: int = 1
    decay: int = 0
    neutralization: str = "INDUSTRY"
    truncation: float = 0.08
    pasteurization: str = "ON"
    nan_handling: str = "OFF"
    instrument_type: str = "EQUITY"
    language: str = "FASTEXPR"
    test_period: str = "P1Y"
    start_date: str = "2019-01-01"
    end_date: str = "2023-12-31"


@dataclass(frozen=True)
class Thresholds:
    """提交门槛（对齐平台提交检查，见设计 §2.3）。"""

    fitness_d1: float = 1.0
    fitness_d0: float = 1.3
    sharpe_d1: float = 1.25
    sharpe_d0: float = 2.0
    turnover_min: float = 0.01
    turnover_max: float = 0.70
    autocorr_max: float = 0.7
    sharpe_autocorr_exempt: float = 1.375  # Sharpe≥此值可豁免自相关
    sub_universe_factor: float = 0.75
    margin_marginal: float = 0.1  # 距门槛 10% 内视为 MARGINAL


@dataclass
class AppConfig:
    """应用级配置（默认值；阶段检测可覆盖字段）。

    无 LLM 配置——生成由对话层 agent 完成，项目内不调用 LLM API。
    """

    batch_size: int = 10
    concurrency: int = 3
    sim_timeout_seconds: float = 600.0
    defaults: SimulationDefaults = field(default_factory=SimulationDefaults)
    thresholds: Thresholds = field(default_factory=Thresholds)
