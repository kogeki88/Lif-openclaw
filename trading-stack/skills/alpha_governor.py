from __future__ import annotations

from runtime.base_strategy import BaseStrategy
from runtime.contracts import ExecutionRules, RiskFilters, SignalLogic


class AlphaGovernorStrategy(BaseStrategy):
    strategy_name = "alpha_governor"
    strategy_id = "alpha-governor-protocol"
    strategy_version = "4.5.0"

    def get_assets(self) -> tuple[str, ...]:
        return ("XAUUSD", "GBPUSD", "EURUSD", "BTCUSD")

    def get_signal_logic(self) -> SignalLogic:
        return SignalLogic(
            trigger="M15_CAMARILLA_R3_S3_BREAKOUT",
            timeframes=("M15", "H1", "H4"),
            required_checks=(
                "m15_camarilla_breakout_confirmed",
                "h4_ema20_ema50_directional_alignment",
                "h1_ema20_ema50_directional_alignment",
                "volume_zscore_gt_2_0",
                "atr_is_rising",
            ),
            parameters={
                "emaFast": 20,
                "emaSlow": 50,
                "volumeZScoreMin": 2.0,
                "atrPeriod": 14,
                "atrRisingLookbackBars": 3,
            },
        )

    def get_risk_filters(self) -> RiskFilters:
        return RiskFilters(
            tier1_risk_pct=1.0,
            tier2_risk_pct=1.875,
            min_tdi_slope_deg=30.0,
            min_h1_adx=25.0,
            dynamic_throttle_trigger_losses=3,
            dynamic_throttle_risk_pct=0.5,
            global_heat_cap_pct=4.5,
            usd_correlation_cap_pct=3.0,
            max_daily_drawdown_pct=3.0,
            max_total_drawdown_pct=8.0,
        )

    def get_execution_rules(self) -> ExecutionRules:
        return ExecutionRules(
            execution_mode="non_discretionary",
            execute_only_when_all_layers_pass=True,
            dormant_when_misaligned=True,
            breakeven_trigger_r=0.6,
            sunset_rule_utc="18:00",
            hard_flatten_utc="19:55",
            max_concurrent_positions=3,
            release_rule="after_first_net_positive_closed_trade",
        )
