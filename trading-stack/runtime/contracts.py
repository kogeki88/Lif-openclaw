from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Sequence


@dataclass(frozen=True)
class SignalLogic:
    """What Vanilmirth should evaluate for signal viability."""

    trigger: str
    timeframes: Sequence[str]
    required_checks: Sequence[str]
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dict(asdict(self))


@dataclass(frozen=True)
class RiskFilters:
    """What Filir must enforce before forwarding an entry alert."""

    tier1_risk_pct: float
    tier2_risk_pct: float
    min_tdi_slope_deg: float
    min_h1_adx: float
    dynamic_throttle_trigger_losses: int
    dynamic_throttle_risk_pct: float
    global_heat_cap_pct: float
    usd_correlation_cap_pct: float
    max_daily_drawdown_pct: float
    max_total_drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return dict(asdict(self))


@dataclass(frozen=True)
class ExecutionRules:
    """What Amistr must apply when executing and managing trades."""

    execution_mode: str
    execute_only_when_all_layers_pass: bool
    dormant_when_misaligned: bool
    breakeven_trigger_r: float
    sunset_rule_utc: str
    hard_flatten_utc: str
    max_concurrent_positions: int
    release_rule: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(asdict(self))


@dataclass(frozen=True)
class StrategyBundle:
    """Resolved strategy payload consumed by all three execution agents."""

    strategy_name: str
    strategy_id: str
    strategy_version: str
    signal_logic: SignalLogic
    risk_filters: RiskFilters
    execution_rules: ExecutionRules
    loaded_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        return dict(payload)
