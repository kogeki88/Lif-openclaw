from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Sequence

from .base_strategy import BaseStrategy
from .contracts import ExecutionRules, RiskFilters, SignalLogic

_UTC_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass
class CompatibilityReport:
    strategy_name: str
    strategy_id: str
    strategy_version: str
    checked_at_utc: str
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategyName": self.strategy_name,
            "strategyId": self.strategy_id,
            "strategyVersion": self.strategy_version,
            "checkedAtUtc": self.checked_at_utc,
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _validate_signal_logic(signal_logic: SignalLogic, errors: List[str]) -> None:
    if not signal_logic.trigger:
        errors.append("SignalLogic.trigger is required.")
    if not signal_logic.timeframes:
        errors.append("SignalLogic.timeframes must contain at least one timeframe.")
    if not signal_logic.required_checks:
        errors.append("SignalLogic.required_checks must contain at least one gate.")


def _validate_risk_filters(risk: RiskFilters, errors: List[str]) -> None:
    if risk.tier1_risk_pct <= 0 or risk.tier2_risk_pct <= 0:
        errors.append("RiskFilters tier risk percentages must be positive.")
    if risk.tier2_risk_pct < risk.tier1_risk_pct:
        errors.append("RiskFilters.tier2_risk_pct cannot be below tier1.")
    if risk.dynamic_throttle_trigger_losses < 1:
        errors.append("RiskFilters.dynamic_throttle_trigger_losses must be >= 1.")
    if risk.dynamic_throttle_risk_pct <= 0:
        errors.append("RiskFilters.dynamic_throttle_risk_pct must be positive.")
    if risk.global_heat_cap_pct <= 0:
        errors.append("RiskFilters.global_heat_cap_pct must be positive.")
    if risk.usd_correlation_cap_pct <= 0:
        errors.append("RiskFilters.usd_correlation_cap_pct must be positive.")


def _validate_execution_rules(execution: ExecutionRules, errors: List[str]) -> None:
    if execution.execution_mode != "non_discretionary":
        errors.append("ExecutionRules.execution_mode must be 'non_discretionary'.")
    if execution.max_concurrent_positions < 1:
        errors.append("ExecutionRules.max_concurrent_positions must be >= 1.")
    if execution.breakeven_trigger_r <= 0:
        errors.append("ExecutionRules.breakeven_trigger_r must be positive.")
    if not _UTC_HHMM_RE.match(execution.sunset_rule_utc):
        errors.append("ExecutionRules.sunset_rule_utc must be HH:MM (UTC).")
    if not _UTC_HHMM_RE.match(execution.hard_flatten_utc):
        errors.append("ExecutionRules.hard_flatten_utc must be HH:MM (UTC).")
    if not execution.release_rule:
        errors.append("ExecutionRules.release_rule is required.")


def _validate_assets(assets: Sequence[str], errors: List[str], warnings: List[str]) -> None:
    if not assets:
        errors.append("get_assets() must return at least one symbol.")
        return

    for asset in assets:
        if not isinstance(asset, str) or not asset.strip():
            errors.append("All symbols from get_assets() must be non-empty strings.")
            continue
        if asset != asset.upper():
            warnings.append(f"Asset '{asset}' is not uppercase; expected canonical symbol format.")


def check_strategy_compatibility(strategy: BaseStrategy) -> CompatibilityReport:
    errors: List[str] = []
    warnings: List[str] = []

    if not strategy.strategy_id:
        errors.append("strategy_id is required.")
    if not strategy.strategy_version:
        errors.append("strategy_version is required.")
    if not strategy.strategy_name:
        warnings.append("strategy_name is empty; class name fallback will be used.")

    assets = strategy.get_assets()
    signal_logic = strategy.get_signal_logic()
    risk_filters = strategy.get_risk_filters()
    execution_rules = strategy.get_execution_rules()

    if not isinstance(assets, Sequence) or isinstance(assets, (str, bytes)):
        errors.append("get_assets() must return a sequence of symbols.")
    else:
        _validate_assets(assets, errors, warnings)

    if not isinstance(signal_logic, SignalLogic):
        errors.append("get_signal_logic() must return SignalLogic.")
    else:
        _validate_signal_logic(signal_logic, errors)

    if not isinstance(risk_filters, RiskFilters):
        errors.append("get_risk_filters() must return RiskFilters.")
    else:
        _validate_risk_filters(risk_filters, errors)

    if not isinstance(execution_rules, ExecutionRules):
        errors.append("get_execution_rules() must return ExecutionRules.")
    else:
        _validate_execution_rules(execution_rules, errors)

    return CompatibilityReport(
        strategy_name=strategy.strategy_name or strategy.__class__.__name__.lower(),
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        checked_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )
