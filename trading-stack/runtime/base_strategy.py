from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from .contracts import ExecutionRules, RiskFilters, SignalLogic, StrategyBundle


class BaseStrategy(ABC):
    """
    Universal strategy interface for Strategy-as-a-Skill architecture.

    Every skill must implement these mandatory hooks:
    - get_assets()
    - get_signal_logic()
    - get_risk_filters()
    - get_execution_rules()
    """

    strategy_name: str = ""
    strategy_id: str = ""
    strategy_version: str = ""

    @abstractmethod
    def get_assets(self) -> Sequence[str]:
        """Return symbols to evaluate for this strategy (dynamic discovery hook)."""

    @abstractmethod
    def get_signal_logic(self) -> SignalLogic:
        """Return Vanilmirth-facing signal logic and confluence requirements."""

    @abstractmethod
    def get_risk_filters(self) -> RiskFilters:
        """Return Filir-facing risk filters and risk-tier authorization gates."""

    @abstractmethod
    def get_execution_rules(self) -> ExecutionRules:
        """Return Amistr-facing execution and trade-management rules."""

    def build_bundle(self) -> StrategyBundle:
        """Canonical contract object injected into all execution agents."""
        return StrategyBundle(
            strategy_name=self.strategy_name or self.__class__.__name__.lower(),
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            signal_logic=self.get_signal_logic(),
            risk_filters=self.get_risk_filters(),
            execution_rules=self.get_execution_rules(),
        )
