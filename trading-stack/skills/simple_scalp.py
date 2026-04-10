from __future__ import annotations

from runtime.base_strategy import BaseStrategy
from runtime.contracts import ExecutionRules, RiskFilters, SignalLogic


class SimpleScalpStrategy(BaseStrategy):
    strategy_name = "simple_scalp"
    strategy_id = "simple-scalp"
    strategy_version = "1.0.0"

    def get_signal_logic(self) -> SignalLogic:
        return SignalLogic(
            trigger="EMA_PULLBACK_CONTINUATION",
            timeframes=("M5", "M15", "H1"),
            required_checks=(
                "h1_trend_aligned",
                "m15_pullback_touch_fast_ema",
                "m5_reclaim_confirmation",
            ),
            parameters={
                "emaFast": 9,
                "emaSlow": 21,
                "confirmationBars": 1,
            },
        )

    def get_risk_filters(self) -> RiskFilters:
        return RiskFilters(
            tier1_risk_pct=0.5,
            tier2_risk_pct=0.9,
            min_tdi_slope_deg=22.0,
            min_h1_adx=18.0,
            dynamic_throttle_trigger_losses=2,
            dynamic_throttle_risk_pct=0.3,
            global_heat_cap_pct=2.5,
            usd_correlation_cap_pct=2.0,
            max_daily_drawdown_pct=2.0,
            max_total_drawdown_pct=5.0,
        )

    def get_execution_rules(self) -> ExecutionRules:
        return ExecutionRules(
            execution_mode="non_discretionary",
            execute_only_when_all_layers_pass=True,
            dormant_when_misaligned=True,
            breakeven_trigger_r=0.4,
            sunset_rule_utc="17:30",
            hard_flatten_utc="19:00",
            max_concurrent_positions=2,
            release_rule="after_two_consecutive_wins",
        )
