from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .base_strategy import BaseStrategy
from .contracts import ExecutionRules, RiskFilters, SignalLogic, StrategyBundle


@dataclass
class VanilmirthAgent:
    role: str = "quant_validation"
    signal_logic: SignalLogic | None = None
    strategy_id: str | None = None
    strategy_version: str | None = None

    def inject(self, strategy: BaseStrategy) -> None:
        # Strategy-agnostic: consume only strategy-provided hook output.
        self.signal_logic = strategy.get_signal_logic()
        self.strategy_id = strategy.strategy_id
        self.strategy_version = strategy.strategy_version

    def snapshot(self) -> Dict[str, object]:
        return {
            "agent": "vanilmirth",
            "role": self.role,
            "strategyId": self.strategy_id,
            "strategyVersion": self.strategy_version,
            "signalLogicLoaded": self.signal_logic is not None,
        }


@dataclass
class FilirAgent:
    role: str = "market_scout"
    risk_filters: RiskFilters | None = None
    strategy_id: str | None = None
    strategy_version: str | None = None

    def inject(self, strategy: BaseStrategy) -> None:
        # Strategy-agnostic: consume only strategy-provided hook output.
        self.risk_filters = strategy.get_risk_filters()
        self.strategy_id = strategy.strategy_id
        self.strategy_version = strategy.strategy_version

    def snapshot(self) -> Dict[str, object]:
        return {
            "agent": "filir",
            "role": self.role,
            "strategyId": self.strategy_id,
            "strategyVersion": self.strategy_version,
            "riskFiltersLoaded": self.risk_filters is not None,
        }


@dataclass
class AmistrAgent:
    role: str = "execution_risk_guard"
    execution_rules: ExecutionRules | None = None
    strategy_id: str | None = None
    strategy_version: str | None = None

    def inject(self, strategy: BaseStrategy) -> None:
        # Strategy-agnostic: consume only strategy-provided hook output.
        self.execution_rules = strategy.get_execution_rules()
        self.strategy_id = strategy.strategy_id
        self.strategy_version = strategy.strategy_version

    def snapshot(self) -> Dict[str, object]:
        return {
            "agent": "amistr",
            "role": self.role,
            "strategyId": self.strategy_id,
            "strategyVersion": self.strategy_version,
            "executionRulesLoaded": self.execution_rules is not None,
        }


@dataclass
class AgentFleet:
    vanilmirth: VanilmirthAgent
    filir: FilirAgent
    amistr: AmistrAgent

    @classmethod
    def default(cls) -> "AgentFleet":
        return cls(vanilmirth=VanilmirthAgent(), filir=FilirAgent(), amistr=AmistrAgent())

    def inject(self, strategy: BaseStrategy) -> StrategyBundle:
        self.vanilmirth.inject(strategy)
        self.filir.inject(strategy)
        self.amistr.inject(strategy)
        return strategy.build_bundle()

    def snapshot(self) -> Dict[str, object]:
        return {
            "vanilmirth": self.vanilmirth.snapshot(),
            "filir": self.filir.snapshot(),
            "amistr": self.amistr.snapshot(),
        }
